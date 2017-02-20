# -*- coding: utf-8 -*-

import sys
import functools

try:
    from backports_abc import Generator as GeneratorType
except ImportError:
    from util import mk_gen
    GeneratorType = mk_gen()

from ioloop import IOLoop


class Return(Exception):
    def __init__(self, value=None):
        self.value = value


class Future(object):
    def __init__(self):
        self.result = None
        self.exc_info = None
        self.done = False
        self.callbacks = []

    def set_result(self, result):
        self.result = result
        self.done = True
        for cb in self.callbacks:
            cb(self)

    def add_done_callback(self, fn):
        if self.done:
            fn(self)
        else:
            self.callbacks.append(fn)


_null_future = Future()


class Runner(object):
    def __init__(self, gen, result_future, first_yielded):
        self.gen = gen
        self.result_future = result_future
        self.future = _null_future
        self.running = False
        self.finished = False

        self.ioloop = IOLoop.instance()

        if self.handle_yield(first_yielded):
            self.run()

    def handle_yield(self, yielded):
        # yielded is definitely Future
        self.future = yielded
        if not self.future.done:
            self.ioloop.add_future(self.future, lambda f: self.run())
            return False
        return True

    def run(self):
        if self.running or self.finished:
            return

        try:
            self.running = True
            while True:
                future = self.future
                if not future.done:
                    return
                self.future = None
                try:
                    value = future.result
                    yielded = self.gen.send(value)
                except (StopIteration, Return) as e:
                    self.finished = True
                    self.future = _null_future
                    self.result_future.set_result(getattr(e, 'value', None))
                    self.result_future = None
                    return
                if not self.handle_yield(yielded):
                    return
        finally:
            self.running = False


def coroutine(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        future = Future()

        try:
            result = func(*args, **kwargs)
        except (StopIteration, Return) as e:
            result = getattr(e, 'value', None)
        except Exception:
            future.exc_info = sys.exc_info()
            return future
        else:
            if isinstance(result, GeneratorType):
                try:
                    yielded = next(result)
                except (StopIteration, Return) as e:
                    future.set_result(getattr(e, 'value', None))
                except Exception:
                    future.exc_info = sys.exc_info()
                else:
                    # result is generator, yielded is Future
                    Runner(result, future, yielded)
                try:
                    return future
                finally:
                    future = None
        future.result = result
        future.done = True
        return future
    return wrapper
