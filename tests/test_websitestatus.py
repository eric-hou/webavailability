# -*- coding: utf-8 -*-
"""
unittest for WebsiteStatus

:copyright: (c) 2020 by Liang Hou.
:license: MIT License, see LICENSE for more details.
"""
from contextlib import contextmanager
from http import HTTPStatus
import msgpack
import libs.status
from libs.status import WebsiteStatus


class MockDB:
    """
    A mock DB Connection to verify SQl statement.
    """
    def __init__(self, somethingfetch=False):
        self.sqls = []
        self.somethingfetch = somethingfetch

    class MockCursor:
        def __init__(self, somethingfetch=False):
            self.sqls = []
            self.somethingfetch = somethingfetch

        def execute(self, sql):
            self.sqls.append(sql)

        def fetchone(self):
            if self.somethingfetch:
                return True
            else:
                return False

    @contextmanager
    def cursor(self):
        curs = MockDB.MockCursor(self.somethingfetch)
        yield curs
        self.sqls = curs.sqls

    def commit(self):
        pass


def test_type_schema():
    """
    Verify WebsiteStatus::create_type_schema
    Note: since it is just SQL statement comparison, every whitespace counts. Sigh!
    """
    response_status_type_select_sql = "select 1 from pg_type where typname = 'response_status'"
    response_status_type_sql = "CREATE TYPE response_status AS ENUM ('responsive', 'unresponsive');"
    # A complete phrases include all HTTP status codes and three additional ones.
    phrases = [getattr(x, 'phrase').lower() for x in HTTPStatus] + ['domain not exist', 'ssl error',
                                                                    'connection timeout', 'Page content not expected']
    phrases_type_select_sql = "select 1 from pg_type where typname = 'phrase_status'"
    phrases = tuple(phrases)
    phrase_type_sql = f'CREATE TYPE phrase_status AS ENUM {phrases};'

    db = MockDB()
    WebsiteStatus.create_type_schema(db)
    # Verify 'CREATE TYPE' statement if TYPE phrase_status doesn't exit
    assert db.sqls == [response_status_type_select_sql, response_status_type_sql,
                       phrases_type_select_sql, phrase_type_sql]
    db = MockDB(True)
    WebsiteStatus.create_type_schema(db)
    # Verify no 'CREATE TYPE' statement is executed if TYPE phrase_status exits
    assert db.sqls == [response_status_type_select_sql, phrases_type_select_sql]


def test_table_schema():
    """
    Verify WebsiteStatus::create_table_schema
    Note: since it is just SQL statement comparison, every whitespace counts. Sigh!
    """
    table_sql = '''
        CREATE TABLE IF NOT EXISTS web_activity_aiven_io (
        id SERIAL PRIMARY KEY,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        topic_offset BIGINT DEFAULT -1,
        test_from varchar(32) NOT NULL,
        url varchar(256) NOT NULL,
        event_time BIGINT,
        status response_status,
        phrase phrase_status,
        dns integer DEFAULT -1,
        response integer DEFAULT -1,
        detail varchar(128)
        );
        '''
    index_sql = '''
        CREATE INDEX IF NOT EXISTS web_activity_url_index_aiven_io ON web_activity_aiven_io (url);
        '''
    db = MockDB()
    WebsiteStatus.create_table_schema('aiven.io', db)
    assert db.sqls == [table_sql, index_sql]


def test_insert_status():
    """
    Verify WebsiteStatus::insert_status by checking a correct INSERT SQL is submitted to DB.
    Note: since it is just SQL statement comparison, every whitespace counts. Sigh!
    """
    webstatus = WebsiteStatus('Sydney', 'https://aiven.io', 'responsive', 'ok', 10, 300)
    sql = f'''INSERT INTO web_activity_aiven_io (topic_offset, test_from, url,
        event_time, status, phrase, dns, response, detail) VALUES (
        {webstatus["offset"]}, '{webstatus["from"]}', '{webstatus["url"]}', {webstatus["timestamp"]},
        '{webstatus["status"]}', '{webstatus["phrase"]}', {webstatus["dns"] if webstatus["dns"] else -1},
        {webstatus["response"] if webstatus["response"] else -1}, '{webstatus["detail"] if webstatus["detail"] else ""}'
        );'''

    db = MockDB()
    webstatus.insert_status(db)
    assert db.sqls == [sql]


def test_serialize():
    """
    Test WebsiteStatus::serialize
    """
    webstatus = WebsiteStatus('Sydney', 'https://aiven.io', 'responsive', 'ok', 10, 300, '', 100)
    s1 = webstatus.serialize()
    s2 = {'from': 'sydney', 'url': 'https://aiven.io', 'timestamp': webstatus['timestamp'],
          'status': 'responsive', 'phrase': 'ok', 'dns': 10, 'response': 300, 'detail': '', 'offset': 100}
    # webstatus is a dictionary
    assert s1 == msgpack.packb(s2, use_bin_type=True)

    webstatus = WebsiteStatus('Sydney', 'https://aiven.io', 'responsive', 'Page content not expected',
                              10, 300, '<svg\\s+', 100)
    s1 = webstatus.serialize()
    s2 = {'from': 'sydney', 'url': 'https://aiven.io', 'timestamp': webstatus['timestamp'],
          'status': 'responsive', 'phrase': 'Page content not expected', 'dns': 10, 'response': 300,
          'detail': '<svg\\s+', 'offset': 100}
    # webstatus is a dictionary
    assert s1 == msgpack.packb(s2, use_bin_type=True)


def test_deserialize():
    """
    Test WebsiteStatus::deserialize
    """
    # This raw is a msgpack.packb result from WebsiteStatus(15, 'Sydney', 'https://aiven.io', 'responsive',
    #                                                       'forbidden', 10, 300)
    raw = b'\x89\xa4from\xa6sydney\xa3url\xb0https://aiven.io\xa9timestamp\xcbA\xd7\xf9L\x02d.\xa1\xa6status\xaa'\
          b'responsive\xa6phrase\xa9forbidden\xa3dns\n\xa8response\xcd\x01,\xa6detail\xa0\xa6offset\x0f'
    status = WebsiteStatus('Sydney', 'https://aiven.io', 'responsive', 'forbidden', 10, 300, '', 15)
    # Reset timestamp to expected value since timestamp is created lively for every instance.
    # Therefore, it has to be reset to the value for raw
    status['timestamp'] = 1608855561.565346
    assert WebsiteStatus.deserialize(raw) == status
