# -*- coding: utf-8 -*-
"""
unittest for WebsiteStatus

:copyright: (c) 2020 by Liang Hou.
:license: Apache-2.0 License, see LICENSE for more details.
"""
from contextlib import contextmanager
from http import HTTPStatus
from random import randint
import msgpack
from libs.status import WebsiteStatus


# A complete phrases include all HTTP status codes and four additional.
phrases = [getattr(x, 'phrase').lower() for x in HTTPStatus] + ['domain not exist', 'ssl error',
                                                                'connection timeout', 'page content not expected']


class MockDB:
    """
    A mock DB Connection to verify SQl statement.
    """
    def __init__(self, something_to_fetch=[]):
        self.sqls = []
        self.curs = None
        self.something_to_fetch = something_to_fetch

    class MockCursor:
        def __init__(self, something_to_fetch=[]):
            self.sqls = []
            self.something_to_fetch = something_to_fetch

        def execute(self, sql):
            self.sqls.append(sql)

        def fetchone(self):
            try:
                return self.something_to_fetch.pop(0)
            except IndexError:
                return None

    @contextmanager
    def cursor(self):
        if self.curs is None:
            self.curs = MockDB.MockCursor(self.something_to_fetch)
        yield self.curs
        self.sqls = self.curs.sqls

    def commit(self):
        pass


def sqls_compare(sql_list1, sql_list2):
    """
    To compare two sql statements lists. Two sql lists are equal only when
    1. Contains the list has the same number of sql statements
    2. The tokens in every corresponding statement are the same in the order
    """
    sql1_tokens = [sql.split() for sql in sql_list1]
    sql2_tokens = [sql.split() for sql in sql_list2]
    return sql1_tokens == sql2_tokens


def test_type_schema():
    """
    Verify WebsiteStatus::create_type_schema
    """
    response_status_type_select_sql = "select 1 from pg_type where typname = 'response_status'"
    response_status_type_sql = "CREATE TYPE response_status AS ENUM ('responsive', 'unresponsive');"
    phrases_type_select_sql = "select 1 from pg_type where typname = 'phrase_status'"
    phrases_tuple = tuple(phrases)
    phrase_type_sql = f'CREATE TYPE phrase_status AS ENUM {phrases_tuple};'

    db = MockDB()
    WebsiteStatus.create_type_schema(db)
    # Verify 'CREATE TYPE' statement if TYPE phrase_status doesn't exit
    assert sqls_compare(db.sqls, [response_status_type_select_sql, response_status_type_sql,
                                  phrases_type_select_sql, phrase_type_sql])
    db = MockDB([[1], [1]])
    WebsiteStatus.create_type_schema(db)
    # Verify no 'CREATE TYPE' statement is executed if TYPE phrase_status exits
    assert sqls_compare(db.sqls, [response_status_type_select_sql, phrases_type_select_sql])


def test_table_schema():
    """
    Verify WebsiteStatus::create_table_schema
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
    assert sqls_compare(db.sqls, [table_sql, index_sql])


def test_get_last_offset():
    """
    Verify WebsiteStatus::get_last_offset by checking a correct SELECT SQL is invoked and a correct
    offset is returned.
    """
    sql = '''
        SELECT topic_offset from web_activity_aiven_io order by id DESC LIMIT 1;
        '''
    # Verify returning -1 when there is nothing
    db = MockDB()
    r = WebsiteStatus.get_last_offset('aiven.io', db)
    assert db.sqls == [sql]
    assert r == -1
    # Verify returning the correct number for an existing last offset
    rnum = randint(1, 0xFFFFFFFF)
    db = MockDB([[rnum]])
    r = WebsiteStatus.get_last_offset('aiven.io', db)
    assert sqls_compare(db.sqls, [sql])
    assert r == rnum


def test_healthy():
    """
    Verify WebsiteStatus::healthy
    """
    # All cases' verification
    for status in ['responsive', 'unresponsive']:
        for phrase in phrases:
            web_status = WebsiteStatus('Sydney', 'https://aiven.io', status, phrase, 10, 300)
            if status == 'responsive' and phrase == 'ok':
                assert web_status.healthy() is True
            else:
                assert web_status.healthy() is False


def test_insert_status():
    """
    Verify WebsiteStatus::insert_status by checking a correct INSERT SQL is submitted to DB.
    """
    last_id_sql = 'SELECT LASTVAL();'

    # All cases' verification
    for status in ['responsive', 'unresponsive']:
        for phrase in phrases:
            web_status = WebsiteStatus('Sydney', 'https://aiven.io', status, phrase, 10, 300)
            sql = f'''INSERT INTO web_activity_aiven_io (topic_offset, test_from, url,
            event_time, status, phrase, dns, response, detail) VALUES (
            {web_status["offset"]}, '{web_status["from"]}', '{web_status["url"]}', {int(web_status["timestamp"])},
            '{web_status["status"]}', '{web_status["phrase"]}', {web_status["dns"] if web_status["dns"] else -1},
            {web_status["response"] if web_status["response"] else -1},
            '{web_status["detail"]}'
            );'''
            # A random number to emulate last insert ID
            rnum = randint(1, 0xFFFFFFFF)
            db = MockDB([[rnum]])
            web_status.insert_status(db)
            # Verify executed statements
            assert sqls_compare(db.sqls, [sql, last_id_sql])
            # Verify WebsiteStatus::insert_status updated
            if status == 'responsive' and phrase == 'ok':
                assert WebsiteStatus.last_url_status['https://aiven.io'] == (True, rnum)
            else:
                assert WebsiteStatus.last_url_status['https://aiven.io'] == (False, rnum)


def test_insert_status_smart():
    """
    Test WebsiteStatus::insert_status_smart
    """
    last_status_sql = '''
        SELECT id, status, phrase from web_activity_aiven_io WHERE url = 'https://aiven.io'
        ORDER BY id DESC LIMIT 1;
    '''
    insert_sql = '''INSERT INTO web_activity_aiven_io (topic_offset, test_from, url,
    event_time, status, phrase, dns, response, detail) VALUES (
    %d, 'sydney', 'https://aiven.io', %d, '%s', '%s', %d, %d, '%s'
    );'''
    last_id_sql = 'SELECT LASTVAL();'
    # Case 1: Verify a new status record is inserted when table is empty
    WebsiteStatus.last_url_status = {}
    web_status = WebsiteStatus('Sydney', 'https://aiven.io', 'responsive', 'ok', 10, 300, '', 200)
    rnum = randint(1, 0xFFFFFFFF)
    db = MockDB([None, [rnum]])
    web_status.insert_status_smart(db)
    insert_sql_value = insert_sql % (web_status['offset'], web_status['timestamp'], 'responsive', 'ok', 10, 300, '')
    # Verify SQLs
    assert sqls_compare(db.sqls, [last_status_sql, insert_sql_value, last_id_sql])
    # Verify WebsiteStatus.last_url_status cache's content
    assert WebsiteStatus.last_url_status['https://aiven.io'] == (True, rnum)

    # Case 2: Verify a healthy record updates the existing record if the table is not empty
    WebsiteStatus.last_url_status = {}
    web_status = WebsiteStatus('Sydney', 'https://aiven.io', 'responsive', 'ok', 10, 300, '', 200)
    rnum1 = randint(1, 0xFFFFFFFF)
    rnum2 = randint(1, 0xFFFFFFFF)
    db = MockDB([[rnum1, 'responsive', 'ok'], [rnum2]])
    update_sql = f'''
    UPDATE web_activity_aiven_io SET (created_at, topic_offset, event_time) = (CURRENT_TIMESTAMP,
    {web_status['offset']}, {web_status['timestamp']}) WHERE id = {rnum1};
    '''
    web_status.insert_status_smart(db)
    # Verify SQLs
    assert sqls_compare(db.sqls, [last_status_sql, update_sql])
    # Verify WebsiteStatus.last_url_status contains lasting healthy record from table
    assert WebsiteStatus.last_url_status['https://aiven.io'] == (True, rnum1)

    # Case 3: Verify a healthy record updates the existing record if it is healthy too
    web_status = WebsiteStatus('Sydney', 'https://aiven.io', 'responsive', 'ok', 10, 300, '', 201)
    db = MockDB()
    update_sql = f'''
    UPDATE web_activity_aiven_io SET (created_at, topic_offset, event_time) = (CURRENT_TIMESTAMP,
    {web_status['offset']}, {web_status['timestamp']}) WHERE id = {WebsiteStatus.last_url_status[web_status['url']][1]};
    '''
    # Insert another record, which is supposed to update the last one only
    web_status.insert_status_smart(db)
    assert sqls_compare(db.sqls, [update_sql])
    # Verify WebsiteStatus.last_url_status cache keeps unchanged since it is an update
    assert WebsiteStatus.last_url_status['https://aiven.io'] == (True, rnum1)

    # Case 4: Verify an unhealthy record is inserted when the last record is healthy
    rnum = randint(1, 0xFFFFFFFF)
    web_status = WebsiteStatus('Sydney', 'https://aiven.io', 'unresponsive', 'connection timeout', 10, 300, '', rnum)
    db = MockDB([[rnum]])
    web_status.insert_status_smart(db)
    insert_sql_value = insert_sql % (web_status['offset'], web_status['timestamp'], web_status['status'],
                                     web_status['phrase'], 10, 300, '')
    assert sqls_compare(db.sqls, [insert_sql_value, last_id_sql])
    # Verify WebsiteStatus.last_url_status cache is updated
    assert WebsiteStatus.last_url_status['https://aiven.io'] == (False, rnum)

    # Case 5: Verify a healthy record is inserted if the last record is unhealthy
    rnum = randint(1, 0xFFFFFFFF)
    web_status = WebsiteStatus('Sydney', 'https://aiven.io', 'responsive', 'ok', 10, 300, '', rnum)
    db = MockDB([[rnum]])
    web_status.insert_status_smart(db)
    insert_sql_value = insert_sql % (web_status['offset'], web_status['timestamp'], web_status['status'],
                                     web_status['phrase'], 10, 300, '')
    assert sqls_compare(db.sqls, [insert_sql_value, last_id_sql])
    # Verify WebsiteStatus.last_url_status cache is updated
    assert WebsiteStatus.last_url_status['https://aiven.io'] == (True, rnum)

    # Case 6: Verify an unhealthy status record is inserted when the last record is unhealthy too
    rnum = randint(1, 0xFFFFFFFF)
    web_status = WebsiteStatus('Sydney', 'https://aiven.io', 'responsive', 'ssl error', 10, 300, '', rnum)
    db = MockDB([[rnum]])
    web_status.insert_status_smart(db)
    insert_sql_value = insert_sql % (web_status['offset'], web_status['timestamp'], web_status['status'],
                                     web_status['phrase'], 10, 300, '')
    assert sqls_compare(db.sqls, [insert_sql_value, last_id_sql])
    # Verify WebsiteStatus.last_url_status cache is updated
    assert WebsiteStatus.last_url_status['https://aiven.io'] == (False, rnum)


def test_serialize():
    """
    Test WebsiteStatus::serialize
    """
    # All cases' verification
    for status in ['responsive', 'unresponsive']:
        for phrase in phrases:
            if phrase == 'page content not expected':
                detail = '<svg\\s+'
            else:
                detail = ''
            webstatus = WebsiteStatus('Sydney', 'https://aiven.io', status, phrase, 10, 300, detail, 100)
            s1 = webstatus.serialize()
            s2 = {'from': 'sydney', 'url': 'https://aiven.io', 'timestamp': webstatus['timestamp'],
                  'status': status, 'phrase': phrase, 'dns': 10, 'response': 300, 'detail': detail, 'offset': 100}
            # webstatus is a dictionary
            assert s1 == msgpack.packb(s2, use_bin_type=True)


def test_deserialize():
    """
    Test WebsiteStatus::deserialize
    """
    # This raw is a msgpack.packb result from WebsiteStatus('Sydney', 'https://aiven.io', 'responsive',
    #                                                       'forbidden', 10, 300, '', 15)
    raw = b'\x89\xa4from\xa6sydney\xa3url\xb0https://aiven.io\xa9timestamp\xcbA\xd7\xf9L\x02d.\xa1\xa6status\xaa'\
          b'responsive\xa6phrase\xa9forbidden\xa3dns\n\xa8response\xcd\x01,\xa6detail\xa0\xa6offset\x0f'
    # Create the original WebsiteStatus object for this serialized bytes.
    status = WebsiteStatus('Sydney', 'https://aiven.io', 'responsive', 'forbidden', 10, 300, '', 15)
    # Reset timestamp to expected value since timestamp is created lively for every instance.
    # Therefore, it has to be reset to the value for raw
    status['timestamp'] = 1608855561.565346
    # Verify the deserialized one equals to the original one
    assert WebsiteStatus.deserialize(raw) == status
