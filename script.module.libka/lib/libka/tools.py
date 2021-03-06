"""
Libka set of low-level tools.

Author: rysson + stackoverflow
"""

import pickle
from base64 import b64encode, b64decode
from collections.abc import Mapping
from dataclasses import fields
from functools import partial, update_wrapper
from functools import WRAPPER_ASSIGNMENTS
import copy
import types
import inspect
import gzip
from types import ModuleType
from typing import (
    Type, Callable,
    Optional, Union, Any,
    Dict, List, Tuple,
)


AttrDict = Dict[str, Any]
Args = Tuple[Any]
KwArgs = Dict[str, Any]


# Author: rysson
class adict(dict):
    """
    Simple dict with attribute access.

    Now dct.foo is dct['foo'].
    Missing attribute is None.

    Exmaple
    -------
    >>> dct = adict(foo='baz')
    >>> dct.foo is dct['foo']
    >>> dct.bar is None
    >>> dct['bar']
        KerError: 'bar'
    """

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            return None

    def __getstate__(self):
        return dict(self)


# Author: rysson
def mkmdict(seq, *, container=None):
    """Make multi-dict {key: [val, val]...}."""
    if container is None:
        container = {}
    for key, val in seq:
        container.setdefault(key, []).append(val)
    return container


# Author: rysson
def item_iter(obj):
    """
    Return item (key, value) iterator from dict or pair sequence.
    Empty seqence for None.
    """
    if obj is None:
        return ()
    if isinstance(obj, Mapping):
        return obj.items()
    return obj


# Author: rysson
def get_attr(obj, name, *, default: Optional[Any] = None, sep='.'):
    """
    Get attribute `name` separated by `sep` (default a dot).

    If `obj` is None, first symbol id point to global variable.
    """
    if not name:
        return default
    if isinstance(name, str):
        name = name.split(sep)
    if obj is None:
        try:
            obj = globals()[name[0]]
        except KeyError:
            return default
        name = name[1:]
    for key in name:
        try:
            obj = getattr(obj, key)
        except AttributeError:
            return default
    return obj


# Author: rysson
def wraps_class(src):
    """Simple class wrapper, like `functools.wraps`."""
    def wrapper(cls):
        for attr in WRAPPER_ASSIGNMENTS:
            try:
                setattr(cls, attr, getattr(src, attr))
            except AttributeError:
                pass
        return cls

    return wrapper


# Author: rysson
def encode_data(data):
    """Raw Python data decode. To get *raw* Python data from URL."""
    octet = b64encode(gzip.compress(pickle.dumps(data), mtime=0), b'-_').replace(b'=', b'')
    return octet.decode('ascii')


# Author: rysson
def decode_data(octet):
    """Raw Python data encode. To put *raw* Python data into URL."""
    if not isinstance(octet, bytes):
        octet = octet.encode('utf8')
    mod = len(octet) % 4
    if mod:  # restore padding
        octet += b'=' * (4 - mod)
    return pickle.loads(gzip.decompress(b64decode(octet, b'-_')))


# Author: rysson
def xstriter(*seq):
    """Yield non-empty items as string."""
    for x in seq:
        if x:
            yield str(x)


# Author: rysson
def setdefaultx(dct, key, *values):
    """
    Set dict.default() for first non-None value.
    """
    for value in values:
        if value is not None:
            dct.setdefault(key, value)
            break
    return dct


# Author: rysson
class CallDescr:
    """
    Simple call description.

    Parameters
    ----------
    method : callable
        Function or method to call.
    args: tuple
        Positional method arguments.
    kwargs: dict
        Keywoard method arguments.
    """
    def __init__(self, method, args: Optional[Args] = None, kwargs: Optional[KwArgs] = None):
        if not callable(method):
            meth_type = type(method)
            if meth_type is staticmethod:
                ...
            elif meth_type is classmethod:
                ...
            method = method.__func__  # standard class method decriptors
        #: Function or method to call.
        self.method = method
        #: Positional method arguments.
        self.args = () if args is None else args
        #: Keywoard method arguments.
        self.kwargs = {} if kwargs is None else kwargs
        #: Method signature.
        self._signature = None

    @classmethod
    def make(cls, method, args: Optional[Args] = None, kwargs: Optional[KwArgs] = None):
        if type(method) is CallDescr:
            return method
        return CallDescr(method, args, kwargs)

    def __repr__(self):
        aa = [repr(self.method)]
        if self.args:
            aa.extend(repr(a) for a in self.args)
        if self.kwargs:
            aa.extend(f'{k}={v!r}' for k, v in self.kwargs.items())
        return f'CallDescr({", ".join(aa)})'

    @property
    def signature(self):
        if self._signature is None:
            self._signature = inspect.signature(self.method)
        return self._signature

    @property
    def self(self):
        obj = getattr(self.method, '__self__', None)
        if obj is not None and not isinstance(obj, type):
            return obj
        return self._get_arg('self')

    @property
    def cls(self):
        obj = getattr(self.method, '__self__', None)
        if obj is not None:
            if isinstance(obj, type):
                return obj
            return obj.__class__
        if 'self' in self.signature.parameters:
            obj = self._get_arg('self')
            if obj is not None:
                return obj.__class__
        return self._get_arg('cls')

    def _get_arg(self, name):
        params = self.signature.parameters
        if name in params:
            for i, param in enumerate(params.values()):
                if i < len(self.args) and param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
                    if param.name == name:
                        return self.args[i]
                elif param.name == name:
                    return self.kwargs.get(name)


# Author: Yoel
# See https://stackoverflow.com/a/25959545/9935708
def get_class_that_defined_method(meth: Callable) -> Type:
    """Returns class where method is defined or None."""
    if meth is None:
        return None
    if isinstance(meth, partial):
        return get_class_that_defined_method(meth.func)
    if isinstance(meth, property):
        return get_class_that_defined_method(meth.fget)
    if inspect.ismethod(meth):
        for cls in inspect.getmro(meth.__self__.__class__):
            if meth.__name__ in cls.__dict__:
                return cls
        meth = meth.__func__  # fallback to __qualname__ parsing
    if inspect.isfunction(meth):
        cls = getattr(inspect.getmodule(meth),
                      meth.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0],
                      None)
        if isinstance(cls, type):
            return cls
    cls = getattr(meth, '__objclass__', None)  # handle special descriptor objects
    if cls is None:
        func = getattr(meth, '__func__', None)  # handle staticmethod and classmethod
        if func is not None:
            return get_class_that_defined_method(func)
    return cls


# Author: rysson
def do_call(meth: Callable, args: Optional[Args] = None, kwargs: Optional[KwArgs] = None,
            *, cls: Optional[Type] = None, obj: Optional[Any] = None, ref=None) -> Any:
    """Call `meth` whatever it is. Support for unbounded methods."""
    if args is None:
        args = ()
    if kwargs is None:
        kwargs = {}
    if inspect.ismethod(meth):
        return meth(*args, **kwargs)
    if not callable(meth):
        meth = meth.__func__  # handle descriptors (like staticmethod, classmethod)
    # determine unbound methods
    sig = inspect.signature(meth)
    first = next(iter(sig.parameters), None)
    if first == 'self':
        if obj is None and ref is not None:
            obj = CallDescr.make(ref).self
        if obj is None:
            raise TypeError(f'Can NOT call method {meth} without "self", ref: {ref!r}')
        return meth(obj, *args, **kwargs)
    elif first == 'cls':
        if cls is None:
            if obj is not None:
                cls = obj.__class__
            else:
                cls = get_class_that_defined_method(meth)
        if cls is None:
            raise TypeError(f'Can NOT call class method {meth} without "cls", ref: {ref!r}')
        return meth(cls, *args, **kwargs)
    return meth(*args, **kwargs)


# Author: Mad Physicist, unutbu, Glenn Maynard
# See: https://stackoverflow.com/a/49077211/9935708
def copy_function(f: Callable, *,
                  globals: Optional[Union[bool, AttrDict]] = None,
                  defaults: Optional[Tuple[Any]] = None,
                  module: Optional[ModuleType] = None):
    """Function deep copy with global override (dict or `True` for copy)."""
    if globals is None:
        globals = f.__globals__
    elif globals is True:
        globals = copy.copy(f.__globals__)
    if defaults is None:
        defaults = f.__defaults__
    else:
        defaults = tuple(defaults)
    g = types.FunctionType(f.__code__, globals, name=f.__name__,
                           argdefs=f.__defaults__, closure=f.__closure__)
    g = update_wrapper(g, f)
    if module is not None:
        g.__module__ = module
    g.__kwdefaults__ = copy.copy(f.__kwdefaults__)
    return g


# Author: MacSanhe
# See: https://stackoverflow.com/a/43879552/9935708
# See: https://github.com/MacHu-GWU/inspect_mate-project


# Author: rysson
def add_url_scheme(scheme):
    """Add scheme as netloc realtive, then the scheme works as http in urljoin()."""
    from urllib.parse import uses_relative, uses_netloc
    if isinstance(scheme, str):
        scheme = (scheme,)
    for s in scheme:
        if s not in uses_relative:
            uses_relative.append(s)
        if s not in uses_netloc:
            uses_netloc.append(s)


# Author: rysson
class generator:
    """Simple generator object with length."""

    def __init__(self, generator, *, length=None):
        self._generator = generator
        self._length = length

    def __iter__(self):
        return iter(self._generator)

    def __len__(self):
        if self._length is None:
            TypeError(f'object of type {type(self._generator)} has no len()')
        return self._length


# Author: rysson
class SingletonMetaclass(type):
    """Simple singleton metaclass."""

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonMetaclass, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


# Author: rysson
def sequential_dataclass(cls):
    """
    Make sequence from `dataclass` decorator.

    >>> @sequential_dataclass
    >>> @dataclass
    >>> class A:
    >>>     a: int = 1
    >>>     b: int = 2
    >>>     c: str = 'xyz'
    >>>
    >>> len(A())  # 3
    >>> A()[-1]   # 'xyz'
    >>> A()[:2]   # [1, 2]
    """
    def __iter__(self):
        """Iterator for dataclass fields."""
        return iter(getattr(self, f.name) for f in fields(self))

    def __reversed__(self):
        return iter(getattr(self, f.name) for f in reversed(fields(self)))

    def __len__(self):
        """Length for dataclass fields."""
        return len(fields(self))

    def __getitem__(self, index: Union[int, slice]):
        """List-like access to dataclass fields."""
        if type(index) == slice:
            return [getattr(self, f.name) for f in fields(self)[index]]
        return getattr(self, fields(self)[index].name)

    def __setitem__(self, index: Union[int, slice], value: Union[Any, List[Any]]):
        """List-like set dataclass fields."""
        if type(index) == slice:
            ff = fields(self)[index]
            for n, val in enumerate(value):
                setattr(self, ff[n].name, val)
            if n < len(ff):
                raise ValueError('Value length mismatch')
        else:
            setattr(self, fields(self)[index].name, value)

    def __contains__(self, value: Any):
        return any(getattr(self, f.name) == value for f in fields(self))

    cls.__iter__ = __iter__
    cls.__reversed__ = __reversed__
    cls.__len__ = __len__
    cls.__getitem__ = __getitem__
    cls.__setitem__ = __setitem__
    cls.__contains__ = __contains__
    cls.index = lambda self: 0
    cls.count = lambda self: 0
    return cls
