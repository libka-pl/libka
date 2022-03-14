"""
`yarl` (Yet another URL library) wrapper on `str` type.

You should do NOT use this module in new code. Use `yarl` directly instead.

```python
>>> url = URL('https://www.python.org')
>>> url / 'foo' / 'bar'
URL('https://www.python.org/foo/bar')
>>> url / 'foo' % {'bar': 'baz'}
URL('https://www.python.org/foo?bar=baz')
```

For API see https://yarl.readthedocs.io/en/latest/api.html

If you mix new and old code, where URL is `str` this module can help.
URL is a `str` with full `yarl.URL` API.

WARNING: operator `%` is taken by `yarl.URL`, than you can not use it as `str`,
ex. this doas **NOT** work:
```python
URL('https://host.com/api/%s/%03d') % ('foo', 42)
```
Use `str` directly if you have to:
```python
URL('https://host.com/api/%s/%03d' % ('foo', 42))
```
"""

from sys import getdefaultencoding
from inspect import isfunction, isdatadescriptor
import yarl
from .utils import copy_function


class MISSING:
    """Helper. Type to mark as missing."""


class DeletedAttribute:
    """Helper. Hide attribute descriptor."""
    def __init__(self, name=None):
        self.name = name

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        raise AttributeError(f'attribute {self.name!r} has been deleted')


class CloneURL(type):
    """Helper. Metaclass for clone yarl.URL."""

    def __new__(cls, name, bases, dct):
        def copy(k):
            meth = getattr(yarl.URL, k)
            if isfunction(meth):
                meth = copy_function(meth, globals=True)
                meth.__globals__['URL'] = new
                meth.__globals__['isinstance'] = _ininstance
                proto = yarl.URL.__dict__[k]
                if isinstance(proto, classmethod):
                    meth = classmethod(meth)
                elif isinstance(proto, staticmethod):
                    meth = staticmethod(meth)
            elif isdatadescriptor(meth):
                wrapped = getattr(meth, 'wrapped', None)
                if wrapped is not None:
                    meth.wrapped = copy_function(meth.wrapped, globals=True)
                    meth.wrapped.__globals__['URL'] = new
                    meth.wrapped.__globals__['isinstance'] = _ininstance
            setattr(new, k, meth)

        def _ininstance(obj, class_or_tuple, /):
            if class_or_tuple is new:
                class_or_tuple = (new, yarl.URL)
            return isinstance(obj, class_or_tuple)

        def _type(obj):
            if type(obj) == yarl.URL:
                return new
            return type(obj)

        def cmp_meth(meth):
            def cmp(this, other):
                typ = type(other)
                if typ is new or typ is yarl.URL:
                    return copied(this, other)
                return getattr(str, meth)(this, other)

            copied = getattr(new, meth)  # with overloaded URL and isinstance
            copied.__globals__['type'] = _type
            return cmp

        new = super().__new__(cls, name, bases, dct)
        for k in dir(yarl.URL):
            if not k.startswith('__') and k not in {'_val', '_cache'}:
                copy(k)
        for k in ('__str__', '__repr__', '__hash__', '__mod__', '__truediv__', '__getstate__', '__setstate__',
                  '__bytes__', '__eq__', '__le__', '__lt__', '__ge__', '__gt__'):
            copy(k)
        for k in ('__eq__', '__le__', '__lt__', '__ge__', '__gt__'):
            setattr(new, k, cmp_meth(k))
        new.__rmod__ = DeletedAttribute('__rmod__')
        return new


class URL(str, metaclass=CloneURL):
    """
    yarl (Yet another URL library) wrapper with `str` support.

    See: https://yarl.readthedocs.io/en/latest/api.html#yarl.URL

    You should do not use this, use `yarl.URL` instead.

    Mixed class with `str` and `yarl.URL` API. to help use old code with new one.

    Conflicted method, like `__hash__`, __repr__`, `__mod__` (`%`), comparing
    are bind to `yarl.URL`.
    """

    __slots__ = ('_val', '_cache')

    def __new__(cls, obj=MISSING, encoding=MISSING, errors=MISSING, *, encoded=False, strict=None):
        if type(obj) is cls:
            return obj
        if type(obj) is yarl.URL:
            self = str.__new__(cls, str(obj))
            self._val = obj._val
            self._cache = obj._cache
            return self
        if encoding is MISSING and errors is MISSING:
            # str
            txt = '' if obj is MISSING else obj
            tmp = yarl.URL(txt, encoded=encoded, strict=strict)
            self = str.__new__(cls, str(tmp))
        else:
            # bytes
            if encoding is MISSING:
                encoding = getdefaultencoding()
            if errors is MISSING:
                errors = 'strict'
            args = [b'' if obj is MISSING else obj, encoding, errors]
            self = str.__new__(cls, *args)
            tmp = yarl.URL(args[0], encoded=encoded, strict=strict)
        self._val = tmp._val
        self._cache = tmp._cache
        return self

    def __init_subclass__(cls):
        """Inheriting is forbidden."""
        raise TypeError(f"Inheriting a class {cls!r} from URL is forbidden")

    def __dir__(self):
        return set(object.__dir__(self)) - {'__rmod__'}

    def asURL(self):
        """Returns yarl.URL."""
        return yarl.URL(self)


if __name__ == '__main__':
    u = URL('http://a.b/c/d?e=33')
    print(f'u: {u} {u!r}')
    print(dir(u))
    print(u.host)
    u2 = u.with_host('x.y')
    # print(f'{u2} {u2!r} {u2._url!r} {u2.host}')
    print(f'{u2} {u2!r} {u2.host}')
    print(repr(u % {'x': 1, 'y': 2}))
    print(u._normalize_path)
    print(issubclass(URL, str), issubclass(URL, yarl.URL))
    print(isinstance(u, str), isinstance(u, yarl.URL))
    print(type(u2))
    print(u.join(u2))
    print(u.join(URL('/i/j')))
    print(u.join(yarl.URL('/i/j')))
    print(yarl.URL('http://a.b/c/d?e=33').join(yarl.URL('/i/j')))
    print(yarl.URL('http://a.b/c/d?e=33').join(URL('/i/j').asURL()))
    # print(yarl.URL('http://a.b/c/d?e=33').join(URL('/i/j')))
    print(f'parent: {u.parent!r} {type(u.parent)}')
    print(URL('http://example.com:8888') == URL('http://example.com:8888'))
    print(u == u)
    print(u == yarl.URL('http://a.b/c/d?e=33'))
    print(u == 'http://a.b/c/d?e=33')
    print(dir(u))
