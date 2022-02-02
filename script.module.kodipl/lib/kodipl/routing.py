from __future__ import annotations

import re
import asyncio
from collections import namedtuple
from collections.abc import Sequence, Mapping
from inspect import (
    ismethod, isfunction, iscoroutinefunction,
    signature,
    Signature,  # typing
)
from typing import (
    TypeVar, Generic, GenericAlias,
    overload,
    Union, Optional, Callable, Any,
    get_type_hints, get_args, get_origin,
)
from .utils import parse_url, encode_url, ParsedUrl
from .types import (
    remove_optional, bind_args,
    uint, pint, mkbool,
    Args, KwArgs,
)


# type aliases
Params = dict[Union[str, int], Any]


#: Call descrtiption
#: - method - function or method to call
#: - params - simple query (keywoard) arguments, passed directly in URL
#: - args - raw positional arguments, pickled
#: - kwargs - raw keywoard arguments, pickled
Call = namedtuple('Call', 'method args kwargs raw', defaults=(None,))

EndpointEntry = namedtuple('EndpointEntry', 'path title object')

RouteEntry = namedtuple('RouteEntry', 'method entry regex types')


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


def call(method, *args, **kwargs):
    """Addon action with arguments. Syntax suger. """
    return Call(method, args, kwargs)


ArgDescr = namedtuple('ArgDescr', 'type pattern')


class Router:
    """
    URL router to manage methods and paths.

    >>> @entry(path='/Foo/<a>/<int:b>')
    >>> def foo(a, /, b, c=1, *, d: int, e=2):
    >>>     print(f'foo(a={a!r}, b={b!r}, c={c!r}, d={d!r}, e={e!r})')
    >>>
    >>> def bar(a: PathArg, /, b: PathArg[int], c=1, *, d: int, e=2):
    >>>     print(f'bar(a={a!r}, b={b!r}, c={c!r}, d={d!r}, e={e!r})')
    >>>
    >>> rt = Router('plugin://this')
    >>> rt.url_for(foo, 11, 12, 13, d=14)  # plugin://this/Foo/11/12?c=13&d=14
    >>> rt.url_for(bar, 11, 12, 13, d=14)  # plugin://this/bar/11/12?c=13&d=14
    >>>
    >>> rt.dispatch('plugin://this/Foo/11/12?c=13&d=14')  # foo(a='11', b=12, c='13', d=14, e=2)
    >>> rt.dispatch('plugin://this/bar/11/12?c=13&d=14')  # bar(a='11', b=12, c='13', d=14, e=2)
    """

    SAFE_CALL = False

    #: regex to find "<[type:]param>" in path.
    _RE_PATH_ARG = re.compile(r'<(?:(?P<type>\w+):)?(?P<name>[a-zA-Z]\w*|\d+)>')

    _ARG_TYPES = {
        'str':    ArgDescr(str,    r'[^/]+'),
        'path':   ArgDescr(str,    r'.+'),
        'int':    ArgDescr(int,    r'[+-]?\d+'),
        'uint':   ArgDescr(uint,   r'\d+'),
        'pint':   ArgDescr(pint,   r'[1-9]\d*'),
        'float':  ArgDescr(float,  r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(:?[eE][+-]?\d+)?'),
        'bool':   ArgDescr(mkbool, r'true|false'),
    }

    def __init__(self, url: str = None, obj: object = None, *,
                 standalone: bool = False, router: Router = None):
        self.url = url
        self.obj = obj
        self.routes = []
        if standalone is False:
            self.routes = default_router.routes  # link to routes (it's NOT a copy)
        if router is not None:
            self.routes.extend(router.routes)

    def add_route(self, path: str, *, method: Callable, entry: EndpointEntry) -> None:
        """Add route (ex. from @entry)."""
        def mkarg(r):
            name = r['name']
            typ = r['type'] or 'str'
            typ = self._ARG_TYPES[typ]
            if name.isdigit():
                types[int(name)] = typ.type
                name = f'_{name}'
            else:
                types[name] = typ.type
            return fr'(?P<{name}>{typ.pattern})'

        if path is not None:
            path = getattr(path, 'path', path)  # EndpointEntry - dack typing
            types = {}
            pattern = self._RE_PATH_ARG.sub(mkarg, path)
            self.routes.append(RouteEntry(method, entry, re.compile(pattern), types))

    @overload
    def mkentry(self, endpoint: Union[Callable, str]) -> tuple[str, str]:
        ...

    @overload
    def mkentry(self, title: str, endpoint: Callable) -> tuple[str, str]:
        ...

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
        method = endpoint
        if isinstance(endpoint, Call):
            method = endpoint.method
        #    raise TypeError('mkentry endpoint must be Addon method or str not %r' % type(endpoint))
        if title is None:
            if callable(method):
                title = method.__name__
                entry = getattr(method, '_kodipl_endpoint', None)
                if entry is not None:
                    if entry.title is not None:
                        title = entry.title
        url = self.mkurl(endpoint)
        if title is not None:
            if not isinstance(title, str):
                log(f'WARNING!!! Incorrect title {title!r}')
                title = str(title)
            title = self.translate_title(title)
        return title, url

    def _find_object_path(self, obj: Any) -> list[str]:
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

    def _find_global(self, obj: Any) -> str:
        """Find global object name for `obj`."""
        if obj is self.obj:
            return ':'
        for k, v in globals().items():
            if v is obj:
                if self.obj is None:
                    return k
                return f':{k}'

    def _make_path_args(self, endpoint: EndpointEntry, path_items: list[Any], params: KwArgs) -> None:
        """Add arguemnts to path (if PathArgs is used). Modify `path_items`."""
        sig = signature(endpoint)
        hints = get_type_hints(endpoint)
        count = 0
        for p in sig.parameters.values():
            if ArgMixin.subtype(hints.get(p.name)) is not None:
                path_items.append(params.pop(p.name))
                if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
                    params.pop(count, None)
                    count += 1

    def mkurl(self, endpoint: Union[str, Callable], *args, **kwargs) -> str:
        """
        Create plugin URL to given name/method with arguments.
        """
        def fill_path_args(r):
            """Substitute "<[type:]param>"."""
            name = r['name']
            if name == 'self':
                if ismethod(endpoint):
                    return '.'.join(self._find_object_path(endpoint.__self__))
                if callable(endpoint) and not isfunction(endpoint):  # object.__call__
                    return '.'.join(self._find_object_path(endpoint))
            elif name.isdigit():
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
            raise TypeError(f'Unkown argument {name!r} in path {path} in {endpoint.__name__}() ({endpoint})')

        path = arguments = None
        raw = {}
        if isinstance(endpoint, Call):
            args = endpoint.args + args
            kwargs = {**endpoint.kwargs, **kwargs}
            if endpoint.raw:
                raw = {'_': endpoint.raw}
            endpoint = endpoint.method

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
        # reduce paramters: remove positional if keywoard exists, remove defaults arguments
        if arguments:
            npos = len(arguments.positional)
            params = {k: v for k, v in params.items()
                      if (v != arguments.defaults.get(k)
                          and (isinstance(k, str) or k >= npos or arguments.positional[k] not in params))}
        # encode
        return encode_url(self.url or '', path=path, params=params, raw=raw)

    url_for = mkurl

    def _get_object(self, path, *, strict=True) -> tuple[Callable, list[str]]:
        """Return (object, args)."""
        if path.startswith('/'):
            path = path[1:]
        if self.obj is None:
            dct = globals()
        else:
            dct = None
        obj = self.obj
        names = re.split(r'[/:.]', path)
        if obj is not None and len(names) <= 2 and not any(names):
            return obj, []
        for i, name in enumerate(names):
            if not i and not name:
                dct = globals()
            elif dct is not None:
                obj = dct[name]
                dct = None
            else:
                try:
                    obj = getattr(obj, name)
                except AttributeError:
                    if strict:
                        raise
                    return obj, names[i:]
        return obj, []

    def _convert_args(self, method: Callable, args: Args, kwargs: KwArgs, *, sig: Signature) -> Call:
        """Convert method arguments based on annotations."""
        def posargs():
            """Generator for itarate positional parameters."""
            for p in sig.parameters.values():
                if p.kind == p.VAR_POSITIONAL:
                    while True:
                        yield p
                yield p

        def convert(v, p):
            """Convert (value, hint_type) -> value."""
            t = None if p is None else hints.get(p.name)
            if t is not None:
                t = remove_optional(t)
                if (x := ArgMixin.subtype(t)) is not None:
                    t = x
                if p.kind == p.VAR_POSITIONAL:
                    ot = get_origin(t)
                    if ot is not None and not issubclass(ot, str) and issubclass(ot, Sequence):
                        t = get_args(t)[0]
                elif p.kind == p.VAR_KEYWORD:
                    ot = get_origin(t)
                    if ot is not None and issubclass(ot, Mapping):
                        type_args = get_args(t)
                        if len(type_args) == 2:
                            t = type_args[1]
                if not isinstance(t, GenericAlias) and t is not Any:
                    v = t(v)
            return v

        if sig is None:
            sig = signature(method)
        if all(p.annotation is p.empty for p in sig.parameters.values()):
            hints = {}  # the is no hints at all
        else:
            try:
                hints = get_type_hints(method)
            except TypeError:
                assert callable(method)
                hints = get_type_hints(method.__call__)
        try:
            kwparam = next(iter(p for p in sig.parameters.values() if p.kind == p.VAR_KEYWORD))
        except StopIteration:
            kwparam = None
        params = sig.parameters
        args = tuple(convert(a, p) for a, p in zip(args, posargs()))
        kwargs = {k: convert(v, params.get(k, kwparam)) for k, v in kwargs.items()}
        return Call(method, args, kwargs)

    def _dispatcher_args(self, method: Callable, params: Params, entry: EndpointEntry) -> Call:
        """
        Dispatcher helper. Find method args and kwargs.
        """
        sig = signature(method)
        args = []
        i = 0
        for p in sig.parameters.values():
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
                if not i and p.name == 'self':
                    obj = self.obj
                    if obj is None:
                        obj = entry.object
                    if isinstance(obj, str):
                        obj, _ = self._get_object(obj)
                    elif 'self' in params:
                        obj, _ = self._get_object(params.pop('self'))
                    if obj is None:
                        raise ValueError('Missing object self.')
                    params.pop('self', None)
                    args.append(obj)
                    i -= 1
                elif i in params:
                    args.append(params.pop(i))
                elif p.name in params:
                    args.append(params.pop(p.name))
                else:
                    if p.default is p.empty:
                        raise TypeError(f'Missing argument {p.name!r} for {method.__qualname__}')
            i += 1

        assert 'self' not in params
        return self._convert_args(method, args, params, sig=sig)

    def _apply_args(self, method: Callable, args: Args, kwargs: Params) -> tuple[Args, KwArgs]:
        """Apply arguments by method singature and returns (args, kwargs)."""
        ait = iter(args)
        args = []
        sig = signature(method)
        for i, p in enumerate(sig.parameters.values()):
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
                try:
                    args.append(next(ait))
                except StopIteration:
                    try:
                        if i in kwargs:
                            args.append(kwargs.pop(i))
                        else:
                            args.append(kwargs.pop(p.name))
                    except KeyError:
                        if p.default is p.empty:
                            raise TypeError(f'Missing {i} argument {p.name!r}') from None
            elif p.kind == p.VAR_POSITIONAL:
                while True:
                    try:
                        args.append(next(ait))
                    except StopIteration:
                        try:
                            args.append(kwargs.pop(i))
                        except KeyError:
                            break
                    i += 1
                break
        return self._convert_args(method, args, kwargs, sig=sig)

    def _dispatcher_entry(self, url: Union[str, ParsedUrl], *,
                          root: Callable, missing: Optional[Callable] = None) -> Call:
        """
        Dispatcher helper. Find pointed method with request arguments.
        """
        # Request (dack typing)
        if isinstance(url, str):
            url = parse_url(url, encode_keys={'_'})
        params = {int(k) if k.isdigit() else k: v for k, v in url.args.items()}
        raw = params.pop('_', None)
        if raw:
            params.update(raw)
        # search in entry(path=)
        for route in self.routes:
            if (r := route.regex.fullmatch(url.path)):
                for k, v in r.groupdict().items():
                    if k[:1] == '_' and k[1:].isdigit():
                        k = int(k[1:])
                    params[k] = route.types[k](v)
                return self._dispatcher_args(route.method, params, route.entry)
        # detect root "/"
        if root is not None and url.path == '/':
            return Call(root, (), {})
        # find object by auto-path
        method, names = self._get_object(url.path, strict=False)
        if method is None:
            if missing is False:
                return
            if missing is None:
                raise ValueError(f'Missing handle for {url.path!r}')
            assert all(isinstance(k, str) for k in params)
            return Call(missing, tuple(names), params)
        # apply arguments
        entry = self._apply_args(method, names, params)

        # convert argument values
        assert all(isinstance(k, str) for k in entry.kwargs)
        return entry

    def sync_dispatch(self, url: Union[str, ParsedUrl], root: Optional[Callable] = None, *,
                      missing: Optional[Callable] = None) -> Any:
        """
        Sync dispatch. Call pointed method with request arguments.

        Find `url.path` and call method with direct and query arguments.
        For '/' call `root` or method decoratred with @entry(path='/').
        If no method found call `missing`.

        It failes if found method is async.
        """
        entry = self._dispatcher_entry(url, root=root, missing=missing)
        if entry is None or entry.method is None:
            raise ValueError(f'Missing endpoint for {url!r}')
        if iscoroutinefunction(entry.method):
            raise TypeError(f'Async endpoint {entry.method.__qualname__}() in sync dispatcher for {url!r}')
        # call pointed method
        return entry.method(*entry.args, **entry.kwargs)

    async def async_dispatch(self, url: Union[str, ParsedUrl], root: Optional[Callable] = None, *,
                             missing: Optional[Callable] = None) -> Any:
        """
        Async dispatcher. Call pointed method with request arguments.

        Find `url.path` and call method with direct and query arguments.
        For '/' call `root` or method decoratred with @entry(path='/').
        If no method found call `missing`.

        It supports sync and async methods.
        """
        entry = self._dispatcher_entry(url, root=root, missing=missing)
        if entry is None or entry.method is None:
            raise ValueError(f'Missing endpoint for {url!r}')
        # call pointed method
        if iscoroutinefunction(entry.method):
            return await entry.method(*entry.args, **entry.kwargs)
        return entry.method(*entry.args, **entry.kwargs)

    def dispatch(self, url: Union[str, ParsedUrl], root: Optional[Callable] = None, *,
                 missing: Optional[Callable] = None) -> Any:
        """
        Dispatcher. Call pointed method with request arguments.
        See: sync_dispatch() and async_dispatch().

        >>> def foo():
        >>>     Router().dispatch(url)
        >>>
        >>> async def bar():
        >>>     await Router().dispatch(url)
        """

        try:
            # Test if loop is working.
            asyncio.get_running_loop()
        except RuntimeError:
            # Loop is NOT working.
            pass
        else:
            # Loop is working.
            # NOTE: Do not execute, just return coroutine instead, should be awaited.
            return self.async_dispatch(url, root=root, missing=missing)
        # Execute dispatch in new loop.
        return asyncio.run(self.async_dispatch(url, root=root, missing=missing))


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


default_router = Router(standalone=True)


def _entry(*, router, method=None, path=None, title=None, object=None):
    """Decorator for addon URL entry."""
    entry = EndpointEntry(path=path, title=title, object=object)

    def decorator(method):
        def make_call(*args, **kwargs):
            return Call(method, args, kwargs)

        method._kodipl_endpoint = entry
        method.call = make_call
        if router is not None and path is not None:
            router.add_route(path, method=method, entry=entry)
        return method

    if method is not None:
        return decorator(method)
    return decorator


def entry(method=None, path=None, *, title=None, object=None):
    return _entry(router=default_router, method=method, path=path, title=title, object=object)


if __name__ == '__main__':
    log = print

    class Bar:
        def foo(self, a):
            print(f'{self.__class__.__name__}.foo({a!r})')

        @entry(path='/<self>/GOO/<a>')
        def goo(self, a):
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

        @entry(path='/o/auu/<a>/buu/<uint:b>/ccc/<float:c>', object='obj')
        def aoo(self, a: PathArg, /, b: PathArg[int], c: float = 42, *, d: str):
            print(f'{self.__class__.__name__}.aoo({a!r}, {b!r}, {c!r}, {d!r})')

        @entry(path='/<self>/0/auu/<0>/buu/<uint:b>/ccc/<float:c>')
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
        print(f'----- {args} {kwargs}')
        url = router.mkurl(*args, **kwargs)
        print(url)
        entry = router._dispatcher_entry(url, root=None)
        print(f'  --> {entry!r}')
        if entry:
            print('  ==> ', end='')
            entry.method(*entry.args, **entry.kwargs)
            print('')

    def xxx(a, b=1, /, c=2, *d, e, f=5, **g):
        print(f'xxx({a!r}, {b!r}, c={c!r}, d={d}, e={e!r}, f={f!r}, g={g})')

    def yyy(a, b, /, c, d=3, *, e, f=5):
        pass

    def zzz(a, b=1, /, c=2, d=3, *, e, f=5):
        pass

    if 1:
        print('--- :')
        obj = Class()
        print('ABC', obj.abc)
        print('ABC', obj.abc)
        router = Router(url='plugin://this')
        test(Call(xxx, (11,), {'e': 14}, {'z': 99}))  # XXX
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
        test(obj.bar.goo, 66)

    if 1:
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
        test(obj.bar.goo, 66)
        # print(obj.abc)

        def root():
            print('root /')

        router._dispatcher_entry('plugin://this', root=root)
        router._dispatcher_entry('plugin://this/', root=root)

    if 1:
        print('--- non-global obj')
        d = {'obj': Class()}
        d['obj'].z = Z()
        router = Router(url='plugin://this', obj=d['obj'])
        test(d['obj'].foo, 33)
        test(d['obj'].baz.foo, 33)
        test(d['obj'], 55)
        test(d['obj'].z)

    if 1:
        print('--- run disptacher')

        async def aroot():
            print('ROOT')
            return 42

        async def arun():
            return await Router().dispatch('/', root=aroot)

        print('sync ', Router().dispatch('/', root=aroot))
        print('async', asyncio.run(arun()))

    if 1:
        print('--- disptach args and kwargs')
        default_router = Router(standalone=True)

        @entry(path='/Foo/<a>/<int:b>')
        def foo(a, /, b, c=1, *, d: int, e=2):
            print(f'foo(a={a!r}, b={b!r}, c={c!r}, d={d!r}, e={e!r})')

        def bar(a: PathArg, /, b: PathArg[int], c=1, *, d: int, e=2):
            print(f'bar(a={a!r}, b={b!r}, c={c!r}, d={d!r}, e={e!r})')

        def baz(a: PathArg, /, b: PathArg[int], *c: tuple[int], d: int, e=2, **z: dict[str, int]):
            print(f'bar(a={a!r}, b={b!r}, c={c!r}, d={d!r}, e={e!r}, z={z!r})')

        rt = Router('plugin://this')
        print(rt.url_for(foo, 11, 12, 13, d=14))  # plugin://this/bar/11/12?c=13&d=14
        print(rt.url_for(bar, 11, 12, 13, d=14))  # plugin://this/bar/11/12?c=13&d=14
        print(rt.url_for(baz, 11, 12, 131, 132, d=14, x=21, z=23))  # plugin://this/bar/11/12?c=13&d=14

        rt.dispatch('plugin://this/Foo/11/12?c=13&d=14')  # foo(a='11', b=12, c='13', d=14, e=2)
        rt.dispatch('plugin://this/bar/11/12?c=13&d=14')  # bar(a='11', b=12, c='13', d=14, e=2)
        rt.dispatch('plugin://this/baz/11/12?2=131&3=132&d=14&x=21&z=23')  # bar(a='11', b=12, c='13', d=14, e=2)

        def play(vid: PathArg):
            print(f'Playing video with ID {vid}')

        url = rt.url_for(play, 123)
        print(f'URL {url} -> ', end='')
        rt.dispatch(url)

    if 1:
        print('--- disptach the same path with different arg types')
        default_router = Router(standalone=True)

        @entry(path='/aaa/<a>/<int:b>')
        def foo(a, /, b, c=1):
            print(f'foo(a={a!r}, b={b!r}, c={c!r})')

        @entry(path='/aaa/<a>/<b>')
        def bar(a, /, b, c=1):
            print(f'bar(a={a!r}, b={b!r}, c={c!r})')

        rt = Router('plugin://this')

        print(rt.url_for(foo, 'A', 99))   # plugin://this/aaa/A/99
        print(rt.url_for(bar, 'A', 'B'))  # plugin://this/aaa/A/B

        rt.sync_dispatch('plugin://this/aaa/A/99')  # foo(a='A', b=99, c=1)
        rt.sync_dispatch('plugin://this/aaa/A/B')   # bar(a='A', b='B', c=1)

    print('--- ...')
