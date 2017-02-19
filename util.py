# -*- coding: utf-8 -*-


import collections as _collections_abc

def mk_gen():
    from abc import abstractmethod

    required_methods = (
        '__iter__', '__next__' if hasattr(iter(()), '__next__') else 'next',
         'send', 'throw', 'close')

    class Generator(_collections_abc.Iterator):
        __slots__ = ()

        if '__next__' in required_methods:
            def __next__(self):
                return self.send(None)
        else:
            def next(self):
                return self.send(None)

        @abstractmethod
        def send(self, value):
            raise StopIteration

        @abstractmethod
        def throw(self, typ, val=None, tb=None):
            if val is None:
                if tb is None:
                    raise typ
                val = typ()
            if tb is not None:
                val = val.with_traceback(tb)
            raise val

        def close(self):
            try:
                self.throw(GeneratorExit)
            except (GeneratorExit, StopIteration):
                pass
            else:
                raise RuntimeError('generator ignored GeneratorExit')

        @classmethod
        def __subclasshook__(cls, C):
            if cls is Generator:
                mro = C.__mro__
                for method in required_methods:
                    for base in mro:
                        if method in base.__dict__:
                            break
                    else:
                        return NotImplemented
                return True
            return NotImplemented

    generator = type((lambda: (yield))())
    Generator.register(generator)
    return Generator
