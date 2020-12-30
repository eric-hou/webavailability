# -*- coding: utf-8 -*-
"""
Logging implementation.
This is a logging module which enables you local logging or remote logging to a Kafka Server under a specific topic.

:copyright: (c) 2020 by Liang Hou.
:license: Apache-2.0, see LICENSE for more details.
"""

import logging

from kafka.admin import NewTopic
from kafka import errors as KafkaErrors


class KafkaLoggingHandler(logging.Handler):
    """
    A simple handler which emits records to Kafka server
    """

    def __init__(self, kafka_producer, topic):
        """
        Constructor
        :param kafka_producer: A Kafka Producer instance
        :param topic: Kafka topic
        """
        super().__init__()
        self.topic = topic
        self.producer = kafka_producer

    def emit(self, record):
        msg = self.format(record)
        self.producer.send(self.topic, bytes(msg, 'utf-8'))

    def close(self):
        self.producer.close()
        super().close()


class Logger:
    """
    A logger which either log to local sys.stderr or remote Kafka server.
    """

    def __init__(self, name, kafka_producer=None, kafka_admin=None):
        """
        Constructor
        :param name: Logger name
        :param kafka_server: A Kafka Producer instance if remote Kafka logging is wanted instead.
        :param kafka_admin: A Kafka KafkaAdminClient for creating topic
        """
        self.log = logging.getLogger(name)
        topic = f'logging-{name}'
        if kafka_producer:
            handler = KafkaLoggingHandler(kafka_producer, topic)
            if kafka_admin:
                ktopic = NewTopic(name=topic, num_partitions=1, replication_factor=2)
                try:
                    kafka_admin.create_topics([ktopic], validate_only=False)
                except KafkaErrors.TopicAlreadyExistsError:
                    pass
        else:
            handler = logging.StreamHandler()
        f = logging.Formatter('%(asctime)s - %(name)s - %(levelname)-8s - %(message)s')
        handler.setFormatter(f)
        self.log.addHandler(handler)
        self.log.setLevel(logging.INFO)

    def __getattr__(self, name):
        """
        Redirect all methods to self.log which is logging.Logger instance.
        :param name: Method/Attribute name
        :return: Method/Attribute from self.log
        """
        return getattr(self.log, name)
