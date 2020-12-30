#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main file of Tracker component. It tries to access each specified URL, generate status and push it to a specified
Kafka server under its associated topic.

usage: tracker.py [-h] [-l LOCATION] [-w WEBSITES] [-t TIMEOUT] [-p PERIOD] [-k KAFKA] [-c CA] [-e CERT] [-y KEY]

Websites Availability Tracker

optional arguments:
  -h, --help            show this help message and exit
  -l LOCATION, --location LOCATION
                        The location to tell where this tracker runs from. This is important to tell the availability
                        from a specific location.
  -w WEBSITES, --websites WEBSITES
                        A list of websites URLs to be watched with their optional regular expression to match for the
                        returned page. Separated by comma.
                        Note: URL and its regular expression is separated with spaces.
                        Like 'https://aiven.io <svg\\s+,https://www.google.com',
                        which means:
                        1. https://aiven.io will be watched and loaded page is expected to match regexp '<svg\\s+'
                        2. https://www.google.com will be watched
                        It can be overridden by the environment variable WEBSITES.
  -t TIMEOUT, --timeout TIMEOUT
                        The timeout in seconds to determine connection timeout. Default is 10 seconds.
                        It can be overridden by the environment variable TIMEOUT.
  -p PERIOD, --period PERIOD
                        Period time in seconds at least which all Websites Availability will be monitored.
                        Default is 300 seconds. It can be overridden by environment variable PERIOD.
  -k KAFKA, --kafka KAFKA
                        Kafka bootstrap server. It can be overridden by the environment variable KAFKA.
  -c CA, --ca CA        Kafka server CA(Certificate Authority) file path.
                        The CA content's can be overridden by the environment variable CA.
  -e CERT, --cert CERT  This client certificate file path.
                        The certificate's content can be overridden by the environment variable CERT.
  -y KEY, --key KEY     This client private key file path.
                        The private key's content can be overridden by the environment variable KEY.


:copyright: (c) 2020 by Liang Hou.
:license: Apache-2.0  License, see LICENSE for more details.
"""

import os
import time
from urllib.parse import urlparse
import argparse

from kafka import KafkaProducer
from kafka import errors as KafkaErrors
from kafka.admin import KafkaAdminClient, NewTopic
from libs.webtracker import WebTracker
from libs.log import Logger


def main():
    parser = argparse.ArgumentParser(description='Websites Availability Tracker')
    parser.add_argument('-l', '--location', help='''
    The location to tell where this tracker runs from. This is important to tell the availability from a specific
    location.''')
    parser.add_argument('-w', '--websites', help='''
    A list of websites URLs to be watched with their optional regular expression to match for the returned page.
    Separated by comma. Note: URL and its regular expression is separated with spaces.
    Like 'https://aiven.io <svg\\s+,https://www.google.com', which means:
    1. https://aiven.io will be watched and loaded page is expected to match regexp '<svg\\s+'
    2. https://www.google.com will be watched
    It can be overridden by the environment variable WEBSITES.
    ''')
    parser.add_argument('-t', '--timeout', type=int, default=5, help='''
    The timeout in seconds to determine connection timeout. Default is 10 seconds. It can be overridden by the
    environment variable TIMEOUT.
    ''')
    parser.add_argument('-p', '--period', type=int, default=300, help='''
    Period time in seconds at least which all Websites Availability will be monitored. Default is 300 seconds.
    It can be overridden by environment variable PERIOD.
    ''')
    parser.add_argument('-k', '--kafka', help='''
    Kafka bootstrap server. It can be overridden by the environment variable KAFKA.
    ''')
    parser.add_argument('-c', '--ca', help='''
    Kafka server CA(Certificate Authority) file path. It can be overridden by the environment variable CA.
    ''')
    parser.add_argument('-e', '--cert', help='''
    This client certificate file path. It can be overridden by the environment variable CERT.
    ''')
    parser.add_argument('-y', '--key', help='''
    This client private key file path. It can be overridden by the environment variable KEY.
    ''')

    args = parser.parse_args()

    location = os.getenv('LOCATION') if os.getenv('LOCATION') else args.location
    websites = os.getenv('WEBSITES') if os.getenv('WEBSITES') else args.websites
    urls = {}
    for website in websites.split(','):
        splits = website.split(' ')
        if len(splits) < 2:
            urls[splits[0]] = ''
            continue
        url = splits[0]
        reg_exp = website.lstrip(url).strip()
        urls[url] = reg_exp

    timeout = int(os.getenv('TIMEOUT')) if os.getenv('TIMEOUT') else args.timeout
    period = int(os.getenv('PERIOD')) if os.getenv('PERIOD') else args.period
    kafka = os.getenv('KAFKA') if os.getenv('KAFKA') else args.kafka
    ca = os.getenv('CA') if os.getenv('CA') else args.ca
    cert = os.getenv('CERT') if os.getenv('CERT') else args.cert
    key = os.getenv('KEY') if os.getenv('KEY') else args.key

    # Kafka topics to be created
    # The topics are in the format of 'webactivity-{domain}'
    topics = {}
    for url in urls:
        if not urlparse(url).scheme:
            print(f'Invalid URL {url}, ignored')
            continue
        topics[url] = f'webactiviity-{urlparse(url).netloc}'

    # Create Kafka admin client
    admin = KafkaAdminClient(
        bootstrap_servers=kafka,
        security_protocol="SSL",
        ssl_cafile=ca,
        ssl_certfile=cert,
        ssl_keyfile=key
    )

    # Create Kafka producer
    producer = KafkaProducer(
        bootstrap_servers=kafka,
        security_protocol="SSL",
        ssl_cafile=ca,
        ssl_certfile=cert,
        ssl_keyfile=key
    )

    if os.getenv('PRODUCTION'):
        logger = Logger('tracker', producer, admin)
    else:
        logger = Logger('tracker')

    # Every website's corresponding Kafka topic name is in the following format
    # webactivity-<domain>
    # For example, for https://aiven.io, its topic is: webactivity-aiven.io
    for url in urls.keys():
        # Todo: Make num_partitions and replication_factor for each domain configurable.
        topic_list = [NewTopic(name=topics[url], num_partitions=1, replication_factor=2)]
        try:
            admin.create_topics(new_topics=topic_list, validate_only=False)
        except KafkaErrors.TopicAlreadyExistsError:
            logger.info(f'Topic {topics[url]} already exists')

    # Close admin now since it is not used any more
    admin.close()

    tracker = WebTracker(location, urls, timeout)

    # Forever loop to monitor the websites
    while True:
        stime = time.time()
        for status in tracker.status():
            producer.send(topics[status["url"]], status.serialize())
            logger.info(f'Sending {status}')
            logger.debug(f'Sending {status} with serialized data: {status.serialize()}')
        producer.flush()

        etime = time.time()
        if etime < stime + period:
            logger.info(f'Sleeping for {stime + period - etime} seconds')
            time.sleep(stime + period - etime)


if __name__ == '__main__':
    main()
