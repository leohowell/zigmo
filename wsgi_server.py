# -*- coding: utf-8 -*-

import sys
import socket
import StringIO


class WSGIServer(object):
    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    request_queue_size = 1

    def __init__(self, server_address):
        self.listen_socket = listen_socket = socket.socket(
            self.address_family, self.socket_type,
        )
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        listen_socket.bind(server_address)
        listen_socket.listen(self.request_queue_size)
        host, port = listen_socket.getsockname()[:2]
        self.server_name = socket.getfqdn(host)
        self.server_port = port
        self.headers_set = []

    def set_app(self, application):
        self.application = application

    def serve_forever(self):
        listen_socket = self.listen_socket
        while True:
            self.client_connection, client_address = listen_socket.accept()
            self.handle_one_request()

    def handle_one_request(self):
        self.request_data = request_data = self.client_connection.recv(1024)
        print ''.join(
            '< {line}\n'.format(line=line)
            for line in request_data.splitlines()
        )
        self.parse_request(request_data)
        env = self.get_environ()
        result = self.application(env, self.start_response)
        self.finish_response(result)

    def parse_request(self, text):
        request_line = text.splitlines()[0]
        request_line = request_line.rstrip('\r\n')
        (
            self.request_method,
            self.path,
            self.request_version
        ) = request_line.split()

    def get_environ(self):
        env = {
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'http',
            'wsgi.input': StringIO.StringIO(self.request_data),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': False,
            'wsgi.run_once': False,
            'REQUEST_METHOD': self.request_method,
            'PATH_INFO': self.path,
            'SERVER_NAME': self.server_name,
            'SERVER_PORT': self.server_port,
        }
        return env

    def start_response(self, status, response_headers, exc_info=None):
        server_headers = [
            ('Date', 'Sun, 12 Feb 2017 12:54:48 GMT'),
            ('Server', 'WSGIServer demo 0.1'),
        ]
        self.headers_set = [status, response_headers + server_headers]

    def finish_response(self, result):
        try:
            status, response_headers = self.headers_set
            response = 'HTTP/1.1 {status}\r\n'.format(status=status)
            for header in response_headers:
                response += '{0}: {1}\r\n'.format(*header)
            response += '\r\n'
            for data in result:
                response += data
            print ''.join(
                '> {line}\n'.format(line=line)
                for line in response.splitlines()
            )
            self.client_connection.sendall(response)
        finally:
            self.client_connection.close()


def make_server(host, port, application):
    server_address = (host, port)
    server = WSGIServer(server_address)
    server.set_app(application)
    return server
