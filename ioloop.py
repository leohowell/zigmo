# -*- coding: utf-8 -*-

import time
import select
import functools
import collections


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

        self._future_callbacks = collections.deque()

    @staticmethod
    def instance():
        if not hasattr(IOLoop, '_instance'):
            IOLoop._instance = IOLoop()
        return IOLoop._instance

    def add_handler(self, fd_obj, handler, event):
        fd = fd_obj.fileno()
        self.handlers[fd] = (fd_obj, handler)
        self.epoll.register(fd, event)

    def update_handler(self, fd, event):
        self.epoll.modify(fd, event)

    def remove_handler(self, fd):
        self.handlers.pop(fd, None)
        try:
            self.epoll.unregister(fd)
        except Exception as error:
            print 'epoll unregister failed %r' % error

    def replace_handler(self, fd, handler):
        self.handlers[fd] = (self.handlers[fd][0], handler)

    def start(self):
        try:
            while True:
                for i in range(len(self._future_callbacks)):
                    callback = self._future_callbacks.popleft()
                    callback()

                events = self.epoll.poll(self.PULL_TIMEOUT)
                self.events.update(events)
                while self.events:
                    fd, event = self.events.popitem()
                    try:
                        fd_obj, handler = self.handlers[fd]
                        handler(fd_obj, event)
                    except Exception as error:
                        print 'ioloop callback error: %r' % error
                        time.sleep(0.5)
        finally:
            for fd, _ in self.handlers.items():
                self.remove_handler(fd)
            self.epoll.close()

    def add_future_callback(self, callback, *args, **kwargs):
        self._future_callbacks.append(
            functools.partial(callback, *args, **kwargs)
        )

    def add_future(self, future, callback):
        future.add_done_callback(
            lambda future: self.add_future_callback(callback, future)
        )
