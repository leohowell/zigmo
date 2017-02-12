# -*- coding: utf-8 -*-

import sys
import select
import socket
import logging
import StringIO
from datetime import datetime


EOL1 = b'\n\n'
EOL2 = b'\n\r\n'


formatter = logging.Formatter(
    '[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')
stream_handler = logging.StreamHandler()
stream_handler.formatter = formatter

access_logger = logging.getLogger('zigmo_access')
access_logger.addHandler(stream_handler)
access_logger.setLevel(logging.INFO)


class Connection(object):
    def __init__(self, fd, connection, raw_request=b'', response=b''):
        self.fd = fd
        self.raw_request = raw_request
        self.response = response
        self.connection = connection
        self.headers = None
        self.status = None
        self.send = False
        self.address = None


class WSGIServer(object):
    ADDRESS_FAMILY = socket.AF_INET
    SOCKET_TYPE = socket.SOCK_STREAM
    BACKLOG = 5

    HEADER_DATE_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'
    SERVER_HEADER = ('Server', 'zigmo/WSGIServer 0.2')

    def __init__(self, server_address):
        self.ssocket = ssocket = socket.socket(
            self.ADDRESS_FAMILY, self.SOCKET_TYPE,
        )
        ssocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        ssocket.bind(server_address)
        ssocket.listen(self.BACKLOG)
        ssocket.setblocking(0)
        host, port = ssocket.getsockname()[:2]
        self.server_name = socket.getfqdn(host)
        self.server_port = port
        self.headers_set = []

        self.epoll = select.epoll()
        self.epoll.register(ssocket.fileno(), select.EPOLLIN)

    def set_app(self, application):
        self.application = application

    def serve_forever(self):
        ssocket = self.ssocket
        epoll = self.epoll
        sfileno = ssocket.fileno()

        pool = {}
        try:
            while True:
                events = epoll.poll(1)
                for fd, event in events:
                    if fd == sfileno:
                        connection, address = ssocket.accept()
                        connection.setblocking(0)
                        connection_fileno = connection.fileno()

                        epoll.register(connection_fileno, select.EPOLLIN)

                        conn = Connection(connection_fileno, connection)
                        conn.address = address
                        pool[connection_fileno] = conn
                    elif event & select.EPOLLIN:
                        conn = pool[fd]
                        conn.raw_request += conn.connection.recv(1024)
                        if EOL1 in conn.raw_request or EOL2 in conn.raw_request:
                            epoll.modify(fd, select.EPOLLOUT)
                    elif event & select.EPOLLOUT:
                        conn = pool[fd]
                        if not conn.send:
                            self.handle(self.application, conn,
                                        self.server_name, self.server_port)
                        bytes = conn.connection.send(conn.response)
                        conn.send = True
                        conn.response = conn.response[bytes:]

                        if len(conn.response) == 0:
                            epoll.modify(fd, 0)
                            conn.connection.shutdown(socket.SHUT_RDWR)
                            conn.connection.close()
                    elif event & select.EPOLLHUP:
                        conn = pool[fd]
                        epoll.unregister(fd)
                        del pool[fd]
                        del conn
        finally:
            epoll.unregister(ssocket.fileno())
            epoll.close()
            ssocket.close()

    @classmethod
    def handle(cls, application, connection, server_name, server_port):
        def start_response(status, response_headers, exc_info=False):
            connection.headers = response_headers + [
                ('Date', datetime.utcnow().strftime(cls.HEADER_DATE_FORMAT)),
                cls.SERVER_HEADER,
            ]
            connection.status = status

        access_logger.debug('\n' + ''.join(
            '< {line}\n'.format(line=line)
            for line in connection.raw_request.splitlines()
        ))
        environ = cls.get_environ(
            connection.raw_request, server_name, server_port
        )
        body = application(environ, start_response)
        connection.response = cls.package_response(body, connection)
        request_line = connection.raw_request.splitlines()[0]
        access_logger.info(
            '%s "%s" %s %s', connection.address[0], request_line,
            connection.status.split(' ', 1)[0], len(body[0]),
        )

    @classmethod
    def parse_request(cls, content):
        content_lines = content.splitlines()

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

    @classmethod
    def get_environ(cls, raw_request, server_name, server_port):
        request_data = cls.parse_request(raw_request)
        environ = {
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': request_data['SERVER_PROTOCOL'].split('/')[1].lower(),
            'wsgi.input': StringIO.StringIO(raw_request),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': False,
            'wsgi.run_once': False,
            'SERVER_NAME': server_name,
            'SERVER_PORT': server_port,
        }
        environ.update(request_data)
        return environ

    @classmethod
    def package_response(cls, body, connection):
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
