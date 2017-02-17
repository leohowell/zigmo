# -*- coding: utf-8 -*-

import sys
import socket
import logging
import StringIO
from datetime import datetime

from ioloop import IOLoop


EOL1 = b'\n\n'
EOL2 = b'\n\r\n'


formatter = logging.Formatter(
    '[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
stream_handler = logging.StreamHandler()
stream_handler.formatter = formatter

access_logger = logging.getLogger('zigmo_access')
access_logger.addHandler(stream_handler)
access_logger.setLevel(logging.INFO)


class Connection(object):
    def __init__(self, fd):
        self.fd = fd
        self.request_buffer = []
        self.handled = False
        self.response = b''

        self.headers = None
        self.status = None
        self.address = None


class WSGIServer(object):
    ADDRESS_FAMILY = socket.AF_INET
    SOCKET_TYPE = socket.SOCK_STREAM
    BACKLOG = 5

    HEADER_DATE_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'
    SERVER_NAME = 'zigmo/WSGIServer 0.3'

    def __init__(self, server_address):
        self.ssocket = self.setup_server_socket(server_address)
        host, self.server_port = self.ssocket.getsockname()[:2]
        self.server_name = socket.getfqdn(host)

        self.ioloop = IOLoop.instance()
        self.conn_pool = {}

    @classmethod
    def setup_server_socket(cls, server_address):
        ssocket = socket.socket(cls.ADDRESS_FAMILY, cls.SOCKET_TYPE)
        ssocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        ssocket.bind(server_address)
        ssocket.listen(cls.BACKLOG)
        ssocket.setblocking(0)
        return ssocket

    def set_app(self, application):
        self.application = application

    def _accept(self, ssocket, event):
        if event & IOLoop.ERROR:
            self._close(ssocket)

        connect, addr = ssocket.accept()
        connect.setblocking(0)
        ioloop = IOLoop.instance()
        ioloop.add_handler(connect, self._receive, IOLoop.READ)

        fd = connect.fileno()
        connection = Connection(fd)
        connection.address = addr
        self.conn_pool[fd] = connection

    def _receive(self, connect, event):
        if event & IOLoop.ERROR:
            self._close(connect)

        fd = connect.fileno()
        connection = self.conn_pool[fd]
        fragment = connect.recv(1024)
        connection.request_buffer.append(fragment)

        last_fragment = ''.join(connection.request_buffer[:2])
        if EOL2 in last_fragment:
            ioloop = IOLoop.instance()
            ioloop.update_handler(fd, IOLoop.WRITE)
            ioloop.update_callback(fd, self._send)

    def _send(self, connect, event):
        if event & IOLoop.ERROR:
            self._close(connect)

        fd = connect.fileno()
        connection = self.conn_pool[fd]
        if not connection.handled:
            self.handle(connection)

        byteswritten = connect.send(connection.response)
        if byteswritten:
            connection.response = connection.response[byteswritten:]

        if not len(connection.response):
            self._close(connect)

    def _close(self, connect, event=None):
        fd = connect.fileno()
        connect.shutdown(socket.SHUT_RDWR)
        connect.close()

        ioloop = IOLoop.instance()
        ioloop.remove_handler(fd)

        del self.conn_pool[fd]

    def serve_forever(self):
        self.ioloop.add_handler(self.ssocket, self._accept,
                                IOLoop.READ | IOLoop.ERROR)
        try:
            self.ioloop.start()
        finally:
            self.ssocket.close()

    def handle(self, connection):
        def start_response(status, response_headers, exc_info=False):
            utc_now = datetime.utcnow().strftime(self.HEADER_DATE_FORMAT)
            connection.headers = response_headers + [
                ('Date', utc_now),
                ('Server', self.SERVER_NAME),
            ]
            connection.status = status

        request_text = ''.join(connection.request_buffer)
        environ = self.get_environ(request_text)
        body = self.application(environ, start_response)
        connection.response = self.package_response(body, connection)

        request_line = request_text.splitlines()[0]
        access_logger.info(
            '%s "%s" %s %s', connection.address[0], request_line,
            connection.status.split(' ', 1)[0], len(body[0]),
        )
        access_logger.debug('\n' + ''.join(
            '< {line}\n'.format(line=line)
            for line in request_text.splitlines()
        ))

    @classmethod
    def parse_request_buffer(cls, text):
        content_lines = text.splitlines()

        request_line = content_lines[0].rstrip('\r\n')
        request_method, path, request_version = request_line.split()
        if '?' in path:
            path, query_string = path.split('?', 1)
        else:
            path, query_string = path, ''

        return {
            'PATH_INFO': path,
            'REQUEST_METHOD': request_method,
            'SERVER_PROTOCOL': request_version,
            'QUERY_STRING': query_string,
        }

    def get_environ(self, request_text):
        request_data = self.parse_request_buffer(request_text)
        scheme = request_data['SERVER_PROTOCOL'].split('/')[1].lower(),
        environ = {
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': scheme,
            'wsgi.input': StringIO.StringIO(request_text),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': False,
            'wsgi.run_once': False,
            'SERVER_NAME': self.server_name,
            'SERVER_PORT': self.server_port,
        }
        environ.update(request_data)
        return environ

    def package_response(self, body, connection):
        response = 'HTTP/1.1 {status}\r\n'.format(status=connection.status)
        for header in connection.headers:
            response += '{0}: {1}\r\n'.format(*header)
        response += '\r\n'
        for data in body:
            response += data
        access_logger.debug('\n' + ''.join(
            '> {line}\n'.format(line=line)
            for line in response.splitlines()
        ))
        return response


def make_server(host, port, application):
    server_address = (host, port)
    server = WSGIServer(server_address)
    server.set_app(application)
    return server
