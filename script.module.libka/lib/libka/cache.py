"""
Cache module. Storage any data, specially JSON responses.

"""

from typing import (
    Optional, Any,
)
from collections.abc import Sequence
from collections import namedtuple
from functools import wraps
from .storage import Storage
from .tools import adict, copy_function


Ref = namedtuple('Ref', 'name')


class Cache:
    """
    """


#: Default cache values
default = adict()
default.expires = 24 * 3600
default.short = 3600
default.long = 7 * 24 * 3600


def cached(*args, expires: Optional[int] = None, key: Optional[str] = None,
           serializer='json,pickle', on_fail=None):
    """
    Repeat call on filed decorator, try `tries` times. Delay `delay` between retries.

    Parameters
    ----------
    expires : int
        Cache expires in seconds.
    key : str
        Cache key name. If None, function name is used.
    """

    def decorator(method):

        nonlocal key
        if key is None:
            key = method.__name__

        @wraps(method)
        def wrapper(*args, **kwargs):
            # check via serializer
            return method(*args, **kwargs)
            # if on_fail is not None:
            #     return do_call(on_fail, ref=CallDescr(method, args, kwargs))

        return wrapper

    if len(args) > 1:
        raise TypeError('Too many positional arguments, use @cached or @cached(key=value, ...)')
    method = args and args[0]
    if expires is None:
        expires = default.expires
    elif type(expires) is Ref:
        expires = default[expires.name]
    if isinstance(serializer, str):
        serializer = serializer.split(',')
    elif not isinstance(serializer, Sequence):
        serializer = (serializer,)
    # with parameters: @cache()
    if method is None:
        return decorator
    # w/o parameters: @cache
    return decorator(method)


def _make_cache_function(name: str, **kwargs):
    """Helper. Generate decorator function with defaults from `default`."""
    fn = copy_function(cached)
    fn.__kwdefaults__.update(kwargs)
    setattr(cached, name, fn)


_make_cache_function('short', expires=Ref('short'))
_make_cache_function('long', expires=Ref('long'))
_make_cache_function('json', serializer='json')
_make_cache_function('pickle', serializer='pickle')
