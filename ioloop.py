# -*- coding: utf-8 -*-

import select


class IOLoop(object):
    _EPOLLIN = 0x001
    _EPOLLOUT = 0x004
    _EPOLLERR = 0x008
    _EPOLLHUP = 0x010

    READ = _EPOLLIN
    WRITE = _EPOLLOUT
    ERROR = _EPOLLERR | _EPOLLHUP

    PULL_TIMEOUT = 1

    def __init__(self):
        self.handlers = {}
        self.events = {}
        self.epoll = select.epoll()

    @staticmethod
    def instance():
        if not hasattr(IOLoop, '_instance'):
            IOLoop._instance = IOLoop()
        return IOLoop._instance

    def add_handler(self, fd_obj, callback, event):
        fd = fd_obj.fileno()
        self.handlers[fd] = (fd_obj, callback)
        self.epoll.register(fd, event)

    def update_handler(self, fd, event):
        self.epoll.modify(fd, event)

    def remove_handler(self, fd):
        self.handlers.pop(fd, None)
        try:
            self.epoll.unregister(fd)
        except Exception as error:
            print 'epoll unregister failed %r' % error

    def update_callback(self, fd, callback):
        self.handlers[fd] = (self.handlers[fd][0], callback)

    def start(self):
        try:
            while True:
                events = self.epoll.poll(self.PULL_TIMEOUT)
                self.events.update(events)
                while self.events:
                    fd, event = self.events.popitem()
                    try:
                        fd_obj, callback = self.handlers[fd]
                        callback(fd_obj, event)
                    except Exception as error:
                        print 'ioloop callback error: %r' % error
        finally:
            for fd, _ in self.handlers.items():
                self.remove_handler(fd)
            self.epoll.close()
