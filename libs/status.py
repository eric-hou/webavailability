# -*- coding: utf-8 -*-
"""
libs.status
~~~~~~~~~~~~~~~

This module implements WebsiteStatus.

:copyright: (c) 2020 by Liang Hou.
:license: MIT License, see LICENSE for more details.
"""
from http import HTTPStatus
from datetime import datetime
from urllib.parse import urlparse
import msgpack


class WebsiteStatus(dict):
    def __init__(self, status_from, url, status, phrase, dns_time=None, response_time=None, detail='', offset=-1):
        """
        Constructor
        :param status_from: where this test status is from, always transferred to lower cases.
        :param url: Website URL, like https://aiven.io
        :param status: One of "responsive, "unresponsive"
        :param phrase: Status description. This includes all HTTP status code phrases like 'ok', 'forbidden', etc, and
        three additional phrases: 'domain not exist', 'ssl error', and 'connection timeout'.
        :param dns_time: Time in ms taken to resolve DNS.
        :param response_time: Time in ms taken totally to load the Website page.
        :param detail: When phrase is 'Page content not expected', detail shows regular expression for this match.
        :param offset: offset of Kafka message in the corresponding topic
        """
        # Status' UTC timestamp
        timestamp = datetime.utcnow().timestamp()
        # Domain is used as the topic
        self.topic = urlparse(url).netloc.replace('.', '_')
        super().__init__({'from': status_from.lower(), 'url': url, 'timestamp': timestamp,
                          'status': status, 'phrase': phrase, 'dns': dns_time,
                          'response': response_time, 'detail': detail, 'offset': offset})

    @classmethod
    def create_type_schema(cls, db):
        """
        Given a PostgreSQL connection, create enum type for response status and phrases.
        The intention is to save space by using enum type instead of strings directly in DB.
        :param db: A PostgresSQL DB connection instance.
        :return:
        """
        response_status_type_sql = "CREATE TYPE response_status AS ENUM ('responsive', 'unresponsive');"
        # A complete phrases include all HTTP status codes and three additional ones.
        phrases = [getattr(x, 'phrase').lower() for x in HTTPStatus] + ['domain not exist', 'ssl error',
                                                                        'connection timeout',
                                                                        'Page content not expected']
        phrases = tuple(phrases)
        phrase_type_sql = f'CREATE TYPE phrase_status AS ENUM {phrases};'

        with db.cursor() as curs:
            for typename, sql in [('response_status', response_status_type_sql), ('phrase_status', phrase_type_sql)]:
                # Firstly check whether this type exits
                curs.execute(f"select 1 from pg_type where typname = '{typename}'")
                if curs.fetchone():  # Defined already, do nothing
                    continue
                curs.execute(sql)
        db.commit()

    @classmethod
    def create_table_schema(cls, topic, db):
        """
        Given a DB connection, create a corresponding PostgreSQL table for the specific topic.
        :param topic: The specific topic to be created for
        :param db: A PostgresSQL DB connection instance.
        """
        topic = topic.replace('.', '_')
        table_sql = f'''
        CREATE TABLE IF NOT EXISTS web_activity_{topic} (
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
        index_sql = f'''
        CREATE INDEX IF NOT EXISTS web_activity_url_index_{topic} ON web_activity_{topic} (url);
        '''
        with db.cursor() as curs:
            curs.execute(table_sql)
            curs.execute(index_sql)
        db.commit()

    @classmethod
    def get_last_offset(cls, topic, db):
        """
        Get the last offset received for the specific topic
        :param topic: the topic to get offset for
        :param db: DB connection
        :return: The last offset received from Kafka. -1 if nothing received yet
        """
        topic = topic.replace('.', '_')
        sql = f'''
        SELECT topic_offset from web_activity_{topic} order by id DESC LIMIT 1;
        '''
        with db.cursor() as curs:
            curs.execute(sql)
            r = curs.fetchone()
            if r:
                return r[0]
            else:
                return -1

    def insert_status(self, db):
        """
        Insert this instance to DB as a new row
        :param db: DB connection
        """
        sql = f'''INSERT INTO web_activity_{self.topic} (topic_offset, test_from, url,
        event_time, status, phrase, dns, response, detail) VALUES (
        {self["offset"]}, '{self["from"]}', '{self["url"]}', {self["timestamp"]},
        '{self["status"]}', '{self["phrase"]}', {self["dns"] if self["dns"] else -1},
        {self["response"] if self["response"] else -1}, '{self["detail"] if self["detail"] else ""}'
        );'''
        with db.cursor() as curs:
            curs.execute(sql)
        db.commit()

    def serialize(self):
        """
        Return a serialized bytes
        :return: bytes
        """
        return msgpack.packb(self, use_bin_type=True)

    @classmethod
    def deserialize(cls, raw_bytes):
        """
        Deserialize raw bytes into WebsiteStatus instance
        :param raw_bytes: bytes content
        :return: WebsiteStatus instance
        """
        dictv = msgpack.unpackb(raw_bytes, raw=False)
        reborn = WebsiteStatus(dictv['from'], dictv['url'], dictv['status'], dictv['phrase'], dictv['dns'],
                               dictv['response'], dictv['detail'], dictv['offset'])
        # timestamp has to be set to the original value since reborn comes with a newly created timestamp
        reborn['timestamp'] = dictv['timestamp']
        return reborn
