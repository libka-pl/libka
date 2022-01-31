from __future__ import annotations

import re
from collections import namedtuple
from collections.abc import Sequence
from inspect import ismethod, isfunction
from inspect import getfullargspec
from inspect import signature
from typing import (
    TypeVar, Generic,
    Union,
    Callable,
    get_type_hints,
)
from .utils import parse_url, encode_url
from .utils import get_attr
from .types import remove_optional
from .types import bind_args


#: Call descrtiption
#: - method - function or method to call
#: - params - simple query (keywoard) arguments, passed directly in URL
#: - args - raw positional arguments, pickled
#: - kwargs - raw keywoard arguments, pickled
Call = namedtuple('Call', 'method args kwargs raw')
Call.__new__.__defaults__ = (None,)

EndpointEntry = namedtuple('EndpointEntry', 'path title')

Route = namedtuple('Route', 'method entry')


class MISSING:
    """Internal. Type to fit as missing."""


T = TypeVar('T')


class ArgMixin:
    """Custom argument pseudo-type for annotations."""

    @classmethod
    def subtype(cls, ann):
        """Remove Optional and returns subtype from PathArg (or `str` if none)."""
        ann = remove_optional(ann)
        origin = getattr(ann, '__origin__', ann)
        try:
            if origin is cls or issubclass(origin, ArgMixin):
                return getattr(ann, '__args__', (str,))[0]
        except TypeError:
            pass
        return None


class PathArg(ArgMixin, Generic[T]):
    """Path argument pseudo-type for annotations."""


class RawArg(ArgMixin, Generic[T]):
    """Raw argument (pickle+gzip+base64) pseudo-type for annotations."""


def entry(method=None, path=None, title=None):
    """Decorator for addon URL entry."""
    entry = EndpointEntry(path=path, title=title)

    def decorator(method):
        def make_call(**kwargs):
            return Call(method, kwargs)

        if path is not None:
            if ismethod(method):
                obj = method.__self__
                obj._routes.append(Route(method, entry))
        method._kodipl_endpoint = entry
        method.call = make_call
        return method

    if method is not None:
        return decorator(method)
    return decorator


def call(method, *args, **kwargs):
    """Addon action with arguments. Syntax suger. """
    return Call(method, args, kwargs)


class Router:
    """ """

    SAFE_CALL = False

    #: regex to find "<[type:]param>" in path.
    _RE_PATH_ARG = re.compile(r'<(?:(?P<type>\w+):)?(?P<name>[a-zA-Z]\w*|\d+)>')

    def __init__(self, url=None, obj=None):
        self.url = url
        self.obj = obj

    def mkentry(self, title, endpoint=None):
        """Helper. Returns (title, url) for given endpoint."""
        # flog('mkentry({title!r}, {endpoint!r})')  # DEBUG
        if endpoint is None:
            if isinstance(title, str):
                # folder(title, endpoint=title)
                endpoint = title
            else:
                # folder(endpoint, title=None)
                title, endpoint = None, title
        params = {}
        if isinstance(endpoint, Call):
            endpoint, params = endpoint.method, endpoint.params
        if ismethod(endpoint):
            obj = endpoint.__self__
            assert obj == self
        # elif callable(endpoint):
        #     raise TypeError('mkentry endpoint must be Addon method or str not %r' % type(endpoint))
        if title is None:
            if callable(endpoint):
                title = endpoint.__name__
                entry = getattr(endpoint, '_kodipl_endpoint', None)
                if entry is not None:
                    if entry.title is not None:
                        title = entry.title
        url = self.mkurl(endpoint, **params)
        if title is not None:
            if not isinstance(title, str):
                log(f'WARNING!!! Incorrect title {title!r}')
            title = self.translate_title(title)
        return title, url

    def _find_object_path(self, obj):
        """Find object path (names) using `subobject` data."""
        assert obj is not None
        names = []
        while True:
            # get object parent
            try:
                parent = obj._subobject_parent
            except AttributeError:
                return None
            if parent is None:
                break
            try:
                # add object name (attribute in parent points to "obj")
                names.insert(0, parent._subobject_objects[id(obj)])
            except KeyError:
                # missing "subobject", try to find object name ijn attributes
                for k, v in vars(parent):
                    if v is obj:
                        names.insert(0, k)
                        break
                else:
                    return None
            obj = parent
        # find global name (first label in the path)
        if obj is not None and self.obj is None or obj is not self.obj:
            name = self._find_global(obj)
            if name:
                names.insert(0, name)
        return names

    def _find_global(self, obj):
        """Find global object name for `obj`."""
        if obj is self.obj:
            return ':'
        for k, v in globals().items():
            if v is obj:
                if self.obj is None:
                    return k
                return f':{k}'

    def _make_path_args(self, endpoint, path_items, params):
        """Add arguemnts to path (if PathArgs is used)."""
        sig = signature(endpoint)
        hints = get_type_hints(endpoint)
        count = 0
        for p in sig.parameters.values():
            if ArgMixin.subtype(hints.get(p.name)) is not None:
                path_items.append(params.pop(p.name))
                if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
                    params.pop(count, None)
                    count += 1

    def mkurl(self, endpoint: Union[str, callable], *args, **kwargs):
        """
        Create plugin URL to given name/method with arguments.
        """
        def fill_path_args(r):
            """Substitute "<[type:]param>"."""
            name = r['name']
            if name.isdigit():
                index = int(name)
                if index in params:
                    if arguments and index < len(arguments.positional):
                        params.pop(arguments.positional[index], None)
                    return str(params.pop(index))
            else:
                if name in params:
                    if arguments:
                        params.pop(arguments.indexes.get(name), None)
                    return str(params.pop(name))
            breakpoint()
            raise TypeError(f'Unkown argument {name!r} in path {path} in {endpoint.__name__}() ({endpoint})')

        path = arguments = None
        # if endpoint is calable -> need to find endpoint path
        if callable(endpoint):
            arguments = bind_args(endpoint, *args, **kwargs)
            params = dict(enumerate(arguments.args))
            params.update(arguments.arguments)
            # if @entry with path is used, get the path
            entry = getattr(endpoint, '_kodipl_endpoint', None)
            if entry is not None and entry.path is not None:
                path = entry.path
            # check security
            elif getattr(self, 'SAFE_CALL', True):
                raise ValueError('URL to function %r is FORBIDEN, missing @entry' % endpoint)
            # find entry path
            else:
                names, func = [], endpoint
                if ismethod(endpoint):
                    names = self._find_object_path(endpoint.__self__)
                    names.append(endpoint.__name__)
                elif isfunction(endpoint):
                    name = self._find_global(endpoint)
                    if not name:
                        raise ValueError(f'Object {endpoint!r} not found')
                    names = [name]
                else:  # object.__call__
                    func = endpoint.__call__
                    if endpoint is self.obj:
                        names = [self._find_global(endpoint)]
                    else:
                        names = self._find_object_path(endpoint)
                    if not names:
                        raise ValueError(f'Object {endpoint!r} not found')
                self._make_path_args(func, names, params)
                path = '/'.join(map(str, names))
                path = f'/{path}'
        else:
            params = {i: v for i, v in enumerate(args)}
            params.update(kwargs)
        # default path
        if path is None:
            path = f'/{endpoint}'
        # apply path args (from pattern)
        if '<' in path:
            path = self._RE_PATH_ARG.sub(fill_path_args, path)
        # redice paramters, remove positional if keywoard exists
        if arguments:
            npos = len(arguments.positional)
            params = {k: v for k, v in params.items()
                      if isinstance(k, str) or k >= npos or arguments.positional[k] not in params}
        # encode
        return encode_url(self.url or '', path=path, params=params)

    def _dispatcher(self, url, root=None, *, missing=None):
        """
        Dispatcher. Call pointed method with request arguments.
        """

    def dispatcher(self, root=None, *, missing=None):
        """
        Dispatcher. Call pointed method with request arguments.
        """
        path = self.req.url.path
        params = self.req.params
        # find handler pointed by URL path
        handler = None
        for route in self._routes:
            if route.entry.path == path:
                handler = route.method
                break
        if handler is None:
            if path.startswith('/'):
                path = path[1:]
            if path:
                handler = get_attr(self, path, sep='/')
            else:
                if root is None:
                    if self.ROOT_ENTRY:
                        if isinstance(self.ROOT_ENTRY, str):
                            handler = getattr(self, self.ROOT_ENTRY, None)
                        elif isinstance(self.ROOT_ENTRY, Sequence):
                            for name in self.ROOT_ENTRY:
                                handler = getattr(self, name, None)
                                if handler is not None:
                                    break
                else:
                    handler = root
        if handler is None:
            if missing is None:
                raise ValueError('Missing endpoint for %s (req: %s)' % (path, self.req.url))
            handler = missing
        # get pointed method specification
        spec = getfullargspec(handler)
        assert spec.args
        assert spec.args[0] == 'self'
        assert ismethod(handler)
        # prepare arguments for pointed method
        args, kwargs = [], {}
        if spec.args and spec.args[0] == 'self':
            pass
            # if not PY3:
            #     # fix unbound method in Py2
            #     args.append(self)
        if spec.defaults:
            # first fill default method arguments
            for k, v in zip(reversed(spec.args), reversed(spec.defaults)):
                kwargs[k] = v
        if spec.varkw:
            # the method has **kwargs, put all request arguments
            kwargs.update(params)
        else:
            # fill arguments only if method has them
            for k in spec.args:
                if k in params:
                    kwargs[k] = params[k]
        # call pointed method
        return handler(*args, **kwargs)


class subobject:

    def __init__(self, method=None, *, name=None):
        self.method = method
        self.name = name
        if name is None and method is not None:
            # "subobject" is used as decorator
            self.name = method.__name__

    def __call__(self, *args, **kwargs):
        print('CCC', args, kwargs)

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        try:
            return getattr(instance, f'_subobject_value_{self.name}')
        except AttributeError:
            if self.method is not None:
                # create on demand
                value = self.method(instance)
                self.__set__(instance, value)
                return value
            raise AttributeError(f'{instance.__class__.__name__!r} object has no attribute {self.name!r}') from None

    def __set__(self, instance, value):
        try:
            dct = instance._subobject_objects
        except AttributeError:
            dct = instance._subobject_objects = {}
        dct[id(value)] = self.name
        value._subobject_parent = instance
        if not hasattr(instance, '_subobject_parent'):
            instance._subobject_parent = None
        setattr(instance, f'_subobject_value_{self.name}', value)

    def __delete__(self, instance):
        delattr(instance, f'_subobject_value_{self.name}')

    def __set_name__(self, owner, name):
        self.name = name


if __name__ == '__main__':
    log = print

    class Bar:
        def foo(self, a):
            print(f'{self.__class__.__name__}.foo({a!r})')

    class Baz:
        bar = subobject()

        def __init__(self):
            self.bar = Bar()

        def foo(self, a):
            print(f'{self.__class__.__name__}.foo({a!r})')

    class Class:
        bar = subobject()
        baz = subobject()
        z = subobject()

        def __init__(self):
            self.bar = Bar()
            self.baz = Baz()

        @subobject
        def abc(self):
            print('Here is "abc", I am creating Baz()')
            return Baz()

        def foo(self, a):
            print(f'{self.__class__.__name__}.foo({a!r})')

        def goo(self, a: PathArg, /, b: PathArg[int], c: float = 42, *, d: str):
            print(f'{self.__class__.__name__}.goo({a!r}, {b!r}, {c!r}, {d!r})')

        @entry(path='/auu/<a>/buu/<uint:b>/ccc/<float:c>')
        def aoo(self, a: PathArg, /, b: PathArg[int], c: float = 42, *, d: str):
            print(f'{self.__class__.__name__}.aoo({a!r}, {b!r}, {c!r}, {d!r})')

        @entry(path='/auu/<0>/buu/<uint:b>/ccc/<float:c>')
        def a00(self, a: PathArg, /, b: PathArg[int], c: float = 42, *, d: str):
            print(f'{self.__class__.__name__}.a00({a!r}, {b!r}, {c!r}, {d!r})')

        async def adef(self, a: PathArg, b: PathArg[int] = 44):
            print(f'{self.__class__.__name__}.adef({a!r}, {b!r})')

        def __call__(self, a):
            print(f'{self.__class__.__name__}({a!r})')

    def foo(a):
        print(f'foo({a!r})')

    class Z:
        def __call__(self):
            pass

    bar = foo
    # del foo

    def test(*args, **kwargs):
        url = router.mkurl(*args, **kwargs)
        print(url)

    def xxx(a, b=1, /, c=2, *d, e, f=5, **g):
        print(f'xxx({a!r}, {b!r}, c={c!r}, d={d}, e={e!r}, f={f!r}, g={g})')

    def yyy(a, b, /, c, d=3, *, e, f=5):
        pass

    def zzz(a, b=1, /, c=2, d=3, *, e, f=5):
        pass

    print('--- :')
    obj = Class()
    print('ABC', obj.abc)
    print('ABC', obj.abc)
    router = Router(url='plugin://this')
    xxx(10, 11, 12, 13, 14, e=24, g=26, h=27)  # XXX XXX
    test(xxx, 10, 11, 12, 13, 14, e=24, g=26, h=27)  # XXX XXX
    test(obj.aoo, 123, 44, d='xx')  # XXX
    test(obj.a00, 123, 44, d='xx')  # XXX
    test(obj.goo, 123, 44, d='xx')  # XXX
    test(obj.adef, 11, 22)  # XXX
    test(foo, 33)
    test('foo', 33)
    test(obj.foo, a=33)
    test(obj.baz.foo, 33)

    print('--- obj')
    obj = Class()
    obj2 = Class()
    obj.obj = obj2
    obj.z = Z()
    router = Router(url='plugin://this', obj=obj)
    test(foo, 33)
    test(bar, 44), bar.__name__
    test(obj.foo, 33)
    test(obj.goo, 99, b=44, d='dd')
    test(obj.baz.foo, 33)
    test(obj.baz.bar.foo, 33)
    test(obj.abc.bar.foo, 33)
    test(obj2.foo, 33)
    test(obj2.baz.foo, 33)
    test(obj2.baz.bar.foo, 33)
    test(obj2.abc.bar.foo, 33)
    test(obj, 55)
    test(obj.obj, 55)
    test(obj.z)
    # print(obj.abc)

    print('--- non-global obj')
    d = {'obj': Class()}
    d['obj'].z = Z()
    router = Router(url='plugin://this', obj=d['obj'])
    test(d['obj'].foo, 33)
    test(d['obj'].baz.foo, 33)
    test(d['obj'], 55)
    test(d['obj'].z)

    print('--- ...')
