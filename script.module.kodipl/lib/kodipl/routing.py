import sys
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
    TypeVar, Generic,
    overload,
    Union, Optional, Callable, Any,
    get_type_hints, get_args, get_origin,
    Dict, List, Tuple,
)
from .logs import log
from .utils import parse_url, encode_url, ParsedUrl
from .types import (
    remove_optional, bind_args,
    uint, pint, mkbool,
    Args, KwArgs,
)


# type aliases
Params = Dict[Union[str, int], Any]


def call_format(self, fmt):
    """Format Call as plugin URL."""
    if self.addon is None:
        return str(self)
    return self.addon.mkurl(self)


#: Call descrtiption
#: - method - function or method to call
#: - args - positional arguments, queried
#: - kwargs - keywoard arguments, queried
#: - raw - raw keywoard arguments, pickled
Call = namedtuple('Call', 'method args kwargs raw', defaults=(None,))
Call.addon = None
Call.__format__ = call_format

EndpointEntry = namedtuple('EndpointEntry', 'path label style title object')

RouteEntry = namedtuple('RouteEntry', 'method entry regex types')

#: Entry for dircetory, returned by mkentry().
DirEntry = namedtuple('DirEntry', 'url label title style')


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

    def __init__(self, url: Optional[str] = None, obj: Optional[object] = None, *,
                 standalone: Optional[bool] = False, router: Optional['Router'] = None,
                 addon: Optional['Addon'] = None):
        self.url = url
        self.obj = obj
        self.routes = []
        if standalone is False:
            self.routes = default_router.routes  # link to routes (it's NOT a copy)
        if router is not None:
            self.routes.extend(router.routes)
        self.addon = addon

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
    def mkentry(self, endpoint: Union[Callable, str], *,
                title: str = None, style: Union[str, List[str]] = None) -> DirEntry:
        ...

    @overload
    def mkentry(self, label: str, endpoint: Callable, *,
                title: str = None, style: Union[str, List[str]] = None) -> DirEntry:
        ...

    def mkentry(self, label, endpoint=None, *, title=None, style=None):
        """Helper. Returns (title, url) for given endpoint."""
        # flog('mkentry({title!r}, {endpoint!r})')  # DEBUG
        if endpoint is None:
            if isinstance(label, str):
                # folder(label, endpoint=title)
                endpoint = label
            else:
                # folder(endpoint, label=None)
                label, endpoint = None, label
        fmt = None
        method = endpoint
        if isinstance(endpoint, Call):
            method = endpoint.method
        #    raise TypeError('mkentry endpoint must be Addon method or str not %r' % type(endpoint))
        if label is None and title is not None:
            label = title
        if label is None:
            if callable(method):
                label = getattr(method, '__name__', method.__class__.__name__)
                look_4_entries = [method]
                if not ismethod(endpoint) and not isfunction(endpoint):
                    look_4_entries.append(endpoint.__call__)
                for func in look_4_entries:
                    entry = getattr(func, '_kodipl_endpoint', None)
                    if entry is not None:
                        if entry.label is not None:
                            label = entry.label
                        if entry.title is not None:
                            title = entry.title
                        if entry.style is not None:
                            fmt = entry.style
        if isinstance(method, str):
            url = method  # TODO: analyse this case, method name should be converted to URL or leave as is?
        else:
            url = self.mkurl(endpoint)
        if label is not None and not isinstance(label, str):
            log.warning(f'WARNING!!! Incorrect label {label!r}')
            label = str(label)
        if title is not None and not isinstance(title, str):
            log.warning(f'WARNING!!! Incorrect title {title!r}')
            title = str(title)
        if format is not None:
            fmt = style
        return DirEntry(url, label, title, fmt)

    def _find_object_path(self, obj: Any) -> List[str]:
        """Find object path (names) using `subobject` data."""
        assert obj is not None
        names = []
        while True:
            # get object parent
            try:
                parent = obj._subobject_parent
            except AttributeError:
                break
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

    def _make_path_args(self, endpoint: EndpointEntry, path_items: List[Any], params: KwArgs) -> None:
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

        def find_path(endpoint):
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
                e = getattr(func, '_kodipl_endpoint', None)  # extra @entry on __call__
                if e is not None and e.path is not None:
                    return e.path
                if endpoint is self.obj:
                    names = [self._find_global(endpoint)]
                else:
                    names = self._find_object_path(endpoint)
                if not names:
                    raise ValueError(f'Object {endpoint!r} not found')
            self._make_path_args(func, names, params)
            path = '/'.join(map(str, names))
            return f'/{path}'

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
                path = find_path(endpoint)
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

    def _get_object(self, path, *, strict=True) -> Tuple[Callable, List[str]]:
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
                ot = get_origin(t)
                if p.kind == p.VAR_POSITIONAL:
                    if ot is not None and not issubclass(ot, str) and issubclass(ot, Sequence):
                        t = get_args(t)[0]
                elif p.kind == p.VAR_KEYWORD:
                    if ot is not None and issubclass(ot, Mapping):
                        type_args = get_args(t)
                        if len(type_args) == 2:
                            t = type_args[1]
                if ot is None and t is not Any:
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

    def _apply_args(self, method: Callable, args: Args, kwargs: Params) -> Tuple[Args, KwArgs]:
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
            url = parse_url(url, raw={'_'})
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
        # Fix py 3.8 win bug, see https://bugs.python.org/issue40072
        if sys.platform == 'win32' and sys.version_info >= (3, 8):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
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


def _entry(*, router, method: Callable = None, path: str = None, label: str = None, style: str = None,
           title: str = None, object: object = None):
    """Decorator for addon URL entry."""
    entry = EndpointEntry(path=path, label=label, style=style, title=title, object=object)

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


def entry(method: Callable = None, path: str = None, *, label: str = None, style: str = None, title: str = None,
          object: object = None):
    return _entry(router=default_router, method=method, path=path, label=label, style=style,
                  title=title, object=object)
