# -*- coding: utf-8 -*-

"""
tracker.tracker
~~~~~~~~~~~~~~~

This module implements WebTracker which sends HTTP GET request to provided URLs and provides their response status.

:copyright: (c) 2020 by Liang Hou.
:license: Apache-2.0 License, see LICENSE for more details.
"""

import time
import re
import requests
import copy
from urllib.parse import urlparse
from http import HTTPStatus

import dns.resolver

from .status import WebsiteStatus


class WebTracker:
    """
    Class to report Websites Availability.
    """

    def __init__(self, track_from, urls={}, timeout=10):
        """
        Constructor
        :param track_from: Where this Web Availability test is made, like 'sydney'.
        It would be converted to lower cases.
        :param urls: A dictionary with URL and its expected regexp pattern for the page,
        For example, {'https://aiven.io':'<svg\\s+.*', 'https://www.google.com':''} is:
        1. Detect 'https://aiven.io' status and checking whether the response page contains svg tag
        2. Detect 'https://www.goog.com' status
        :param timeout: Seconds to wait for the server to send data before giving up
        """
        self.track_from = track_from.lower()
        # Original dictionary with regexp string
        self.urls = urls
        # This new dictionary with one-off compiled regexp
        self._urls = copy.deepcopy(self.urls)
        for url, reg_exp in urls.items():
            if reg_exp.strip():
                self._urls[url] = re.compile(reg_exp.strip())
        self.timeout = timeout
        # A mapping between HTTP Status codes and their phrases.
        self.status_mapping = dict([(getattr(x, 'value'), getattr(x, 'phrase').lower()) for x in HTTPStatus])

    def status(self):
        """
        A generator to return status for all URLs at the specific period
        :return: A generator yielding WebsiteStatus objects
        """
        for url, re_exp in self._urls.items():
            status = 'unresponsive'
            dns_time = None
            response_time = None
            detail = None

            # We can resolve domain one-off in __init__ but decided not to do so
            # since this is not a time-critical task and it is handy to do in this way.
            domain = urlparse(url).netloc
            try:
                # Measure DNS query time firstly
                stime = time.time()
                # We are measuring DNS response in a rough way through dns.resolver module
                dns.resolver.resolve(domain, 'A')
                etime = time.time()
                # DNS response time in ms
                dns_time = int((etime - stime) * 1000)
                stime = time.time()
                r = requests.get(url, timeout=self.timeout)
                r.close()
                etime = time.time()
                # Total Response time in ms
                response_time = int((etime - stime) * 1000)
                status = 'responsive'
                phrase = self.status_mapping[r.status_code]
                if re_exp:
                    if not re_exp.findall(r.text):
                        phrase = 'Page content not expected'
                        detail = f'{self.urls[url]}'
            except dns.resolver.NXDOMAIN:
                phrase = 'domain not exist'
            except requests.exceptions.SSLError:
                status = 'responsive'
                phrase = 'ssl error'
            except requests.exceptions.ConnectTimeout:
                phrase = 'connection timeout'
            except Exception as e:  # This should never happen, but just in case.
                phrase = str(e).lower()
            yield WebsiteStatus(self.track_from, url, status, phrase, dns_time, response_time, detail)
