# -*- coding: utf-8 -*-

from zigmo import Application, BaseHandler, run_server
from concurrent import Return, coroutine


class AppHandler(BaseHandler):
    @classmethod
    def get(cls, **kwargs):
        return "Marry Christmas"


class AsyncHandler(BaseHandler):
    @classmethod
    @coroutine
    def yield_something(cls):
        raise Return('value from yield')

    @classmethod
    @coroutine
    def get(cls, *args, **kwargs):
        result = yield cls.yield_something()
        raise Return(result)


if __name__ == '__main__':
    app = Application([
        ('/app', AppHandler),
        ('/\d+', AppHandler),
        ('/s', AsyncHandler),
    ])
    run_server('0.0.0.0', 8080, application=app)
