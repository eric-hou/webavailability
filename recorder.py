#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main file of Recorder component. It tries to pull messages from the specific Kafka Server for its interested domains
and insert them into the specific tables on specific PostgreSQL server.

usage: recorder.py [-h] [-d DOMAIN] [-p POSTGRES] [-g PGCA] [-k KAFKA] [-c CA] [-e CERT] [-y KEY]

Websites Availability Recorder

optional arguments:
  -h, --help            show this help message and exit
  -d DOMAIN, --domain DOMAIN
                        A list of domains to be watched, separated by comma. Like 'aiven.io,google.com'.
                        It will be overridden by the environment variable DOMAIN.
  -p POSTGRES, --postgres POSTGRES
                        PostgresSQL server URI. A sample like
                        postgres://avnadmin:tvezg@pg-9971643.aivencloud.com:20274/defaultdb?sslmode=require
                        It can be overridden by the environment variable POSTGRES.
  -g PGCA, --pgca PGCA  PostgresSQL server CA file. It can be overridden by the environment variable PGCA.
  -k KAFKA, --kafka KAFKA
                        Kafka bootstrap server. It can be overridden by the environment variable KAFKA.
  -c CA, --ca CA        Kafka server CA(Certificate Authority) file path.
                        The CA content's can be overridden by the environment variable CA.
  -e CERT, --cert CERT  This client certificate file path.
                        The certificate's content can be overridden by the environment variable CERT.
  -y KEY, --key KEY     This client private key file path.
                        The private key's content can be overridden by the environment variable KEY.
  -s, --smart           Smart mode. In this mode, continuous healthy records are merged into one with event time
                        updated. It saves a lot of DB space since most of records are healthy. It can be overridden by
                        the environment variable SMART.

:copyright: (c) 2020 by Liang Hou.
:license: Apache-2.0 License, see LICENSE for more details.
"""

import os
import argparse

from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient
from kafka.structs import TopicPartition
import psycopg2
from libs.status import WebsiteStatus
from libs.log import Logger


def main():
    parser = argparse.ArgumentParser(description='Websites Availability Recorder')
    parser.add_argument('-d', '--domain', help='''
    A list of domains to be watched, separated by comma. Like 'aiven.io,google.com'. It will be overridden by the
    environment variable DOMAIN.
    ''')
    parser.add_argument('-p', '--postgres', help='''
    PostgresSQL server URI.
    A sample like postgres://avnadmin:rbb8en66jn7tvezg@pg-9971643.aivencloud.com:20274/defaultdb?sslmode=require
    It can be overridden by the environment variable POSTGRES.
    ''')
    parser.add_argument('-g', '--pgca', help='''
    PostgresSQL server CA file. It can be overridden by the environment variable PGCA.
    ''')
    parser.add_argument('-k', '--kafka', help='''
    Kafka bootstrap server. It can be overridden by the environment variable KAFKA.
    ''')
    parser.add_argument('-c', '--ca', help='''
    Kafka server CA(Certificate Authority) file path. The CA content's can be overridden by the environment
    variable CA.
    ''')
    parser.add_argument('-e', '--cert', help='''
    This client certificate file path. The certificate's content can be overridden by the environment variable CERT.
    ''')
    parser.add_argument('-y', '--key', help='''
    This client private key file path. The private key's content can be overridden by the environment variable KEY.
    ''')
    parser.add_argument('-s', '--smart', action='store_true', default=False, help='''
    Smart mode. In this mode, continuous healthy records are merged into one with event time updated. It saves a lot
    of DB space since most of records are healthy. It can be overridden by the environment variable SMART.
    ''')

    args = parser.parse_args()

    domains = os.getenv('DOMAIN') if os.getenv('DOMAIN') else args.domain
    domains = domains.split(',')
    pguri = os.getenv('POSTGRES') if os.getenv('POSTGRES') else args.postgres
    pgca = os.getenv('PGCA') if os.getenv('PGCA') else args.pgca
    kafka = os.getenv('KAFKA') if os.getenv('KAFKA') else args.kafka
    ca = os.getenv('CA') if os.getenv('CA') else args.ca
    cert = os.getenv('CERT') if os.getenv('CERT') else args.cert
    key = os.getenv('KEY') if os.getenv('KEY') else args.key
    smart = os.getenv('SMART') if os.getenv('SMART') else args.smart

    conn = None
    try:
        conn = psycopg2.connect(pguri, sslrootcert=pgca)
    except Exception as e:
        print(f'Could not connect postgreSQL - {e}')
        exit(-1)

    consumer = KafkaConsumer(
        auto_offset_reset="earliest",
        bootstrap_servers=kafka,
        value_deserializer=WebsiteStatus.deserialize,
        enable_auto_commit=True,
        security_protocol="SSL",
        ssl_cafile=ca,
        ssl_certfile=cert,
        ssl_keyfile=key
    )

    if os.getenv('PRODUCTION'):
        # Create Kafka producer for logging
        producer = KafkaProducer(
            bootstrap_servers=kafka,
            security_protocol="SSL",
            ssl_cafile=ca,
            ssl_certfile=cert,
            ssl_keyfile=key
        )
        # Create Kafka admin client
        admin = KafkaAdminClient(
            bootstrap_servers=kafka,
            security_protocol="SSL",
            ssl_cafile=ca,
            ssl_certfile=cert,
            ssl_keyfile=key
        )
        logger = Logger('recorder', producer, admin)
        # admin client is used once for creating logging topic
        admin.close()
    else:
        logger = Logger('recorder')

    # Add related type schema if necessary
    WebsiteStatus.create_type_schema(conn)

    tps = {}
    for domain in domains:
        # Create table schema for this domain
        WebsiteStatus.create_table_schema(domain, conn)
        tp = TopicPartition(f'webactiviity-{domain}', 0)
        tps[domain] = tp

    # Assign topics
    consumer.assign(tps.values())

    # Now seek to last positions
    for domain, tp in tps.items():
        # retrieve next position for the topic/domain
        consumer.seek(tp, WebsiteStatus.get_last_offset(domain, conn) + 1)
        logger.info(f'Starting position for {domain}: {consumer.position(tp)}')

    count = 0
    while True:
        msg_pack = consumer.poll(timeout_ms=2000)
        for tp, messages in msg_pack.items():
            for message in messages:
                status = message.value
                status['offset'] = message.offset
                logger.info("count: %d - %s:%d:%d: key=%s value=%s" % (count, tp.topic, tp.partition,
                                                                       message.offset, message.key,
                                                                       message.value))
                if smart:
                    status.insert_status_smart(conn)
                else:
                    status.insert_status(conn)
                count += 1


if __name__ == '__main__':
    main()
