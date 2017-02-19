# -*- coding: utf-8 -*-


from backports_abc import Generator as GeneratorType


class Return(Exception):
    def __init__(self, value=None):
        self.value = value


def coroutine(func):
    def wrapper(*args, **kwargs):
        def _dispatch(yielded):
            if isinstance(yielded, GeneratorType):
                return _execute_yield(yielded)
            else:
                return _send(yielded)

        def _send(yielded):
            try:
                yielded = origin_gen.send(yielded)
                return _dispatch(yielded)
            except (StopIteration, Return) as e:
                return getattr(e, 'value', None)
            except Exception as error:
                print 'terrible error happened: %r' % error

        def _execute_yield(gen):
            yielded = next(gen)
            return _dispatch(yielded)

        result = func(*args, **kwargs)
        origin_gen = result
        return _execute_yield(result)

    return wrapper


def get_value2():
    return 10086


def get_value1():
    yield get_value2()


@coroutine
def test():
    value1 = yield get_value1()
    print 'got value1: %d' % value1

    value2 = yield get_value2()
    print 'got value2: %d' % value2

    raise Return(value1 == value2)


if __name__ == '__main__':
    result = test()
    print result

"""
>>> got value1: 10086
>>> got value2: 10086
>>> True
"""
