# -*- coding: utf-8 -*-

import re
import urllib

# from wsgiref.simple_server import make_server
from wsgi_server import make_server
from concorrent import Future


_RESPONSE_STATUSES = {
    # Informational
    100: 'Continue',
    101: 'Switching Protocols',
    102: 'Processing',

    # Successful
    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non-Authoritative Information',
    204: 'No Content',
    205: 'Reset Content',
    206: 'Partial Content',
    207: 'Multi Status',
    226: 'IM Used',

    # Redirection
    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
    304: 'Not Modified',
    305: 'Use Proxy',
    307: 'Temporary Redirect',

    # Client Error
    400: 'Bad Request',
    401: 'Unauthorized',
    402: 'Payment Required',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    406: 'Not Acceptable',
    407: 'Proxy Authentication Required',
    408: 'Request Timeout',
    409: 'Conflict',
    410: 'Gone',
    411: 'Length Required',
    412: 'Precondition Failed',
    413: 'Request Entity Too Large',
    414: 'Request URI Too Long',
    415: 'Unsupported Media Type',
    416: 'Requested Range Not Satisfiable',
    417: 'Expectation Failed',
    418: "I'm a teapot",
    422: 'Unprocessable Entity',
    423: 'Locked',
    424: 'Failed Dependency',
    426: 'Upgrade Required',

    # Server Error
    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
    505: 'HTTP Version Not Supported',
    507: 'Insufficient Storage',
    510: 'Not Extended',
}


_RESPONSE_HEADERS = (
    'Accept-Ranges',
    'Age',
    'Allow',
    'Cache-Control',
    'Connection',
    'Content-Encoding',
    'Content-Language',
    'Content-Length',
    'Content-Location',
    'Content-MD5',
    'Content-Disposition',
    'Content-Range',
    'Content-Type',
    'Date',
    'ETag',
    'Expires',
    'Last-Modified',
    'Link',
    'Location',
    'P3P',
    'Pragma',
    'Proxy-Authenticate',
    'Refresh',
    'Retry-After',
    'Server',
    'Set-Cookie',
    'Strict-Transport-Security',
    'Trailer',
    'Transfer-Encoding',
    'Vary',
    'Via',
    'Warning',
    'WWW-Authenticate',
    'X-Frame-Options',
    'X-XSS-Protection',
    'X-Content-Type-Options',
    'X-Forwarded-Proto',
    'X-Powered-By',
    'X-UA-Compatible',
)

_UPPER_CASE_RESPONSE_HEADERS = (header.upper() for header in _RESPONSE_HEADERS)
_HEADER_X_POWERED_BY = {'X-Powered-By': 'zigmo/0.1'}


# Error Processing


class HandlerError(Exception):
    CODE = 500


class HandlerNotFound(HandlerError):
    CODE = 404


class MethodNotImplement(Exception):
    pass


class MethodNotAllowed(HandlerError):
    CODE = 405


def to_string(s):
    if isinstance(s, str):
        return s
    if isinstance(s, unicode):
        return s.encode('utf-8')
    return str(s)


def quote(s, encoding='utf-8'):
    if isinstance(s, unicode):
        s.encode(encoding)
    return urllib.quote(s)


class Request(object):
    def __init__(self, environ):
        self._environ = environ
        self._headers = {}
        self._cookies = {}

    @property
    def url(self):
        return self._environ['PATH_INFO']

    @property
    def headers(self):
        return self._get_headers()

    @property
    def query_string(self):
        return self._environ.get('QUERY_STRING', '')

    @property
    def method(self):
        return self._environ['REQUEST_METHOD']

    @property
    def cookies(self):
        return self._get_cookies()

    def get_cookie(self, name, default=None):
        pass

    def _get_cookies(self):
        if not self._cookies:
            cookies = {}
            cookie_str = self._environ.get('HTTP_COOKIE')
            if cookie_str:
                for cookie in cookie_str.split('; '):
                    if '=' in cookie:
                        k, v = cookie.split('=')
                        cookies[k] = v
            self._cookies = cookies
        return self._cookies

    def _get_headers(self):
        if not self._headers:
            headers = {}
            for k, v in self._environ.items():
                if k.startswith('HTTP_'):
                    key = k[5:].replace('_', '-').upper()
                    headers[key] = v.encode('utf-8')
            self._headers = headers
        return self._headers


class Response(object):
    def __init__(self):
        self._status = '200 OK'
        self._headers = {'Content-Type': 'text/html; charset=utf-8'}
        self._headers.update(_HEADER_X_POWERED_BY)
        self._cookies = {}
        self._body = {}

    def set_response_code(self, code):
        if code not in _RESPONSE_STATUSES:
            raise ValueError('Bad response code: %s' % code)
        self._status = '%s %s' % (code, _RESPONSE_STATUSES[code])

    def set_header(self, name, value):
        key = name.upper()
        if key not in _UPPER_CASE_RESPONSE_HEADERS:
            key = name
        self._headers[key] = to_string(value)

    @property
    def status(self):
        return self._status

    @property
    def headers(self):
        header_items = self._headers.items()
        if self._cookies:
            for cookie in self._cookies.values():
                header_items.append(('Set-Cookie', cookie))
        self._headers.update(_HEADER_X_POWERED_BY)
        return header_items

    def set_cookie(self, name, value, max_age=None, expires=None, path='/',
                    domain=None, secure=False, http_only=True):
        cookie = ['%s=%s' % (quote(name), quote(value))]
        if expires:
            cookie.append('Expires=%s' % expires)
        elif isinstance(max_age, (int, long)):
            cookie.append('Max-Age=%d' % max_age)

        cookie.append('Path=%s' % path)
        if domain:
            cookie.append('Domain=%s' % domain)
        if secure:
            cookie.append('Secure')
        if http_only:
            cookie.append('HttpOnly')
        self._cookies[name] = ';'.join(cookie)


class Controller(object):
    ALLOWED_METHOD = ['get', 'post', 'put', 'patch', 'delete', 'head']

    def __init__(self, url_regex, handler):
        self.url_regex = self.compile_url_pattern(url_regex)
        self.handler = handler
        self.methods = self.collect_method()

    @classmethod
    def compile_url_pattern(cls, url_regex):
        if not url_regex.startswith('$'):
            url_regex += '$'
        return re.compile(url_regex)

    def collect_method(self):
        # desert use hasattr()
        # refer: https://hynek.me/articles/hasattr/

        handler_methods = []
        for method in self.ALLOWED_METHOD:
            try:
                getattr(self.handler, method)
                handler_methods.append(method)
            except AttributeError:
                continue

        if not handler_methods:
            raise MethodNotImplement()

        return handler_methods


class Application(object):
    def __init__(self, url_handler):
        self.url_handler = url_handler
        self.url_spec = self.build_url_spec()

    def build_url_spec(self):
        return [
            Controller(url_regex, handler)
            for url_regex, handler in self.url_handler
        ]

    def dispatch(self, url, method):
        for controller in self.url_spec:
            if controller.url_regex.match(url):
                method = method.lower()
                if method in controller.methods:
                    return getattr(controller.handler, method)
                else:
                    raise MethodNotAllowed()
        raise HandlerNotFound()

    @classmethod
    def execute_handler(cls, func, request, response):
        result = func(request=request, response=response)
        if isinstance(result, Future):
            return result.result
        return result


class BaseHandler(object):
    pass


def handle_error(error, response, start_response):
    response.set_response_code(error.CODE)
    start_response(response.status, response.headers)
    return [response.status]


def build_wsgi_app(application):
    def wsgi(environ, start_response):
        request = Request(environ)
        response = Response()

        try:
            func = application.dispatch(request.url, request.method)
            content = application.execute_handler(func, request, response)
        except (HandlerNotFound, MethodNotAllowed) as error:
            return handle_error(error, response, start_response)

        start_response(response.status, response.headers)
        del request
        del response
        return [content]
    return wsgi


def run_server(host='localhost', port=9090, application=None):
    print 'Running server on %s:%s' % (host, port)
    wsgi = build_wsgi_app(application)
    server = make_server(host, port, wsgi)
    server.serve_forever()
