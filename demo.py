# -*- coding: utf-8 -*-

from zigmo import Application, BaseHandler, run_server


class AppHandler(BaseHandler):
    @classmethod
    def get(cls, **kwargs):
        return "Marry Christmas"


if __name__ == '__main__':
    app = Application([
        ('/app', AppHandler),
        ('/\d+', AppHandler),
    ])
    run_server(application=app)
