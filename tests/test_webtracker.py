# -*- coding: utf-8 -*-
"""
unittest for WebTracker

:copyright: (c) 2020 by Liang Hou.
:license: Apache-2.0 License, see LICENSE for more details.
"""

from datetime import datetime
import requests

import libs.webtracker
import dns.resolver

from libs.webtracker import WebTracker


class MockRequestResult:
    def __init__(self, code):
        self.status_code = code

    def close(self):
        pass

    @property
    def text(self):
        return '''
        <html>
        <head>
        <title>  Welcome</title>
        </head>
        <body>
        </body>
        </html>
        '''


def test_webtracker_allpaths(mocker):
    """
    Test all paths in WebTracker implementation by providing the following response.

    https://aiven.io --> 200 (ok case)
    https://contentmatched.com --> 200 (Page content matched, ok case)
    https://contentdoesntmatch.com --> 200 (Page content not expected)
    https://www.expireddns.com ---> 403 (none 200 case)
    https://notexistingdns.com --> Exception dns.resolver.NXDOMAIN case
    https://timeout.com --> timeout error (Exception requests.exceptions.ConnectTimeout)
    https://anyotherexception.com --> Any other exception

    :param mocker: pytest-mock fixturer
    """
    def mock_dns_resolver(domain, qtype):
        """
        A mock DNS resolver, which either return anything normally or raise dns.resolver.NXDOMAIN exception.
        For tests, it returns as follows.

        notexistingdns.com --> Exception dns.resolver.NXDOMAIN case
        Anything else --> '8.8.8.8'

        :param domain: Domain name
        :param qtype: query string, ignored.
        :return:
        """
        if domain == 'notexistingdns.com':
            raise dns.resolver.NXDOMAIN()
        else:
            return '8.8.8.8'

    def mock_requests_get(url, timeout):
        """
        A mock request get method which returns different response for different URLs.
        Basically it covers all test paths.
        Among the return,
        https://aiven.io --> 200 (ok case)
        https://contentmatched.com --> 200 (Page content matched, ok case)
        https://contentdoesntmatch.com --> 200 (Page content not expected)
        https://non200status.com --> 403 (non 200 case)
        https://www.sslfailure.com --->  Exception requests.exceptions.SSLError
        https://timeout.com --> timeout error (Exception requests.exceptions.ConnectTimeout)
        https://anyotherexception.com --> Any other exception

        :param url: request url
        :param timeout: timeout in seconds
        :return:
        """
        if url in ['https://aiven.io', 'https://contentdoesntmatch.com', 'https://contentmatched.com']:
            return MockRequestResult(200)
        elif url == 'https://non200status.com':
            return MockRequestResult(403)
        elif url == 'https://www.sslfailure.com':
            raise requests.exceptions.SSLError()
        elif url == 'https://timeout.com':
            raise requests.exceptions.ConnectTimeout()
        elif url == 'https://anyotherexception.com':
            raise Exception('Any Exception')

    reg_exp_nomatch = '<title>\\s*Bad.*\\s*</title>'
    reg_exp_match = '<title>\\s*Welcome.*\\s*</title>'
    websites = {'https://aiven.io': '', 'https://non200status.com': '', 'https://www.sslfailure.com': '',
                'https://notexistingdns.com': '', 'https://timeout.com': '',
                'https://anyotherexception.com': '', 'https://contentdoesntmatch.com': reg_exp_nomatch,
                'https://contentmatched.com': reg_exp_match}

    mocker.patch('libs.webtracker.dns.resolver.resolve', mock_dns_resolver)
    mocker.patch('libs.webtracker.requests.get', mock_requests_get)

    test_from = 'Sydney'
    tracker = WebTracker(test_from, websites)
    for webstatus in tracker.status():
        url = webstatus['url']
        assert webstatus['from'] == test_from.lower()
        currenttime = datetime.utcnow().timestamp()
        assert webstatus['timestamp'] <= currenttime  # Since it is mocked, they could be the same
        assert webstatus['timestamp'] > currenttime - 1

        if url in ['https://aiven.io', 'https://non200status.com', 'https://www.sslfailure.com',
                   'https://contentdoesntmatch.com', 'https://contentmatched.com']:
            assert webstatus['status'] == 'responsive'
        else:
            assert webstatus['status'] == 'unresponsive'
        if url in ['https://aiven.io', 'https://contentmatched.com']:
            assert webstatus['phrase'] == 'ok'
        elif url in ['https://non200status.com']:
            assert webstatus['phrase'] == tracker.status_mapping[403]
        elif url in ['https://www.sslfailure.com']:
            assert webstatus['phrase'] == 'ssl error'
        elif url in ['https://notexistingdns.com']:
            assert webstatus['phrase'] == 'domain not exist'
        elif url in ['https://timeout.com']:
            assert webstatus['phrase'] == 'connection timeout'
        elif url in ['https://anyotherexception.com']:
            assert webstatus['phrase'] == 'any exception'
        elif url in ['https://contentdoesntmatch.com']:
            assert webstatus['phrase'] == 'page content not expected'
            assert webstatus['detail'] == reg_exp_nomatch

        if url in ['https://aiven.io', 'https://non200status.com', 'https://www.sslfailure.com',
                   'https://timeout.com', 'https://anyotherexception.com',
                   'https://contentdoesntmatch.com', 'https://contentmatched.com']:
            assert webstatus['dns'] >= 0
        else:
            assert webstatus['dns'] is None

        if url in ['https://aiven.io', 'https://non200status.com',
                   'https://contentdoesntmatch.com', 'https://contentmatched.com']:
            assert webstatus['response'] >= 0
        else:
            assert webstatus['response'] is None
