"""
Libka set of low-level tools.

Author: rysson + stackoverflow
"""

import pickle
from base64 import b64encode, b64decode
from collections.abc import Mapping, Callable
from functools import partial, update_wrapper
import copy
import types
import inspect
import gzip
from typing import (
    Optional, Union, Type,
    Set,
)


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


def mkmdict(seq, *, container=None):
    """Make multi-dict {key: [val, val]...}."""
    if container is None:
        container = {}
    for key, val in seq:
        container.setdefault(key, []).append(val)
    return container


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


def get_attr(obj, name, *, default=None, sep='.'):
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


def encode_data(data):
    """Raw Python data decode. To get *raw* Python data from URL."""
    octet = b64encode(gzip.compress(pickle.dumps(data)), b'-_').replace(b'=', b'')
    return octet.decode('ascii')


def decode_data(octet):
    """Raw Python data encode. To put *raw* Python data into URL."""
    if not isinstance(octet, bytes):
        octet = octet.encode('utf8')
    mod = len(octet) % 4
    if mod:  # restore padding
        octet += b'=' * (4 - mod)
    return pickle.loads(gzip.decompress(b64decode(octet, b'-_')))


def xstriter(*seq):
    """Yield non-empty items as string."""
    for x in seq:
        if x:
            yield str(x)


def setdefaultx(dct, key, *values):
    """
    Set dict.default() for first non-None value.
    """
    for value in values:
        if value is not None:
            dct.setdefault(key, value)
            break
    return dct


# Author: Yoel
# See https://stackoverflow.com/a/25959545/9935708
def get_class_that_defined_method(meth: Callable) -> Type:
    """Returns class where method is defined or None."""
    if isinstance(meth, partial):
        return get_class_that_defined_method(meth.func)
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
    fget = getattr(meth, 'fget', None)  # handle @property
    if fget:
        return get_class_that_defined_method(fget)
    return getattr(meth, '__objclass__', None)  # handle special descriptor objects


# Author: Mad Physicist, unutbu, Glenn Maynard
# See: https://stackoverflow.com/a/49077211/9935708
def copy_function(f, *, globals=None, module=None):
    """Function deep copy with global override (dict or `True` for copy)."""
    if globals is None:
        globals = f.__globals__
    elif globals is True:
        globals = copy.copy(f.__globals__)
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
