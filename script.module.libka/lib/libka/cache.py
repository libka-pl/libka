"""
Cache module. Storage any data, specially JSON responses.

"""

from typing import (
    Optional,
    Set,
)
from collections import namedtuple
from functools import wraps
from .storage import Storage, MultiStorage
from .tools import adict, copy_function
from .utils import encode_params
from .registry import registry, register_singleton


Ref = namedtuple('Ref', 'name')


class Cache:
    """
    """


#: Missing cache
MissingCache = object()


#: Default cache values
default = adict()
default.expires = 24 * 3600
default.short = 3600
default.long = 7 * 24 * 3600


def cached(*args, expires: Optional[int] = None, key: Optional[str] = None, skip: Optional[Set[str]] = None,
           storage: Optional[Storage] = None,
           on_fail=None):
    """
    Repeat call on filed decorator, try `tries` times. Delay `delay` between retries.

    Parameters
    ----------
    expires : int
        Cache expires in seconds.
    key : str
        Cache key name. If None, function name with they args is used.
    skip : set of str
        Names of `kwargs` arguments to skip in `key` build.
    """

    def decorator(method):

        nonlocal storage
        if storage is None:
            storage = registry.cache_storage

        @wraps(method)
        def wrapper(*args, **kwargs):
            if key is None:
                kw = {i: a for i, a in enumerate(args)}
                kw.update(() for k, v in kwargs.items() if skip is None or k not in skip)
                the_key = '{}?{}'.format(method.__name__, encode_params(kw))
            else:
                the_key = key
            data = storage.get(the_key, MissingCache)
            if data is MissingCache:
                data = method(*args, **kwargs)
                storage.set(the_key, data)
                storage.save()
            return data

        return wrapper

    if len(args) > 1:
        raise TypeError('Too many positional arguments, use @cached or @cached(key=value, ...)')
    method = args and args[0]
    if expires is None:
        expires = default.expires
    elif type(expires) is Ref:
        expires = default[expires.name]
    # with parameters: @cache()
    if method is None:
        return decorator
    # w/o parameters: @cache
    return decorator(method)


def _make_cache_function(name: str, **kwargs):
    """Helper. Generate decorator function with defaults from `default`."""
    fn = copy_function(cached)
    fn.__kwdefaults__.update(kwargs)
    if name:
        fn.__name__ = f'{fn.__name__}.{name}'
    return fn


cached.short = _make_cache_function('short', expires=Ref('short'))
cached.long = _make_cache_function('long', expires=Ref('long'))
cached.json = _make_cache_function('json', serializer='json')
cached.pickle = _make_cache_function('pickle', serializer='pickle')


@register_singleton
def create_cache_storage():
    return MultiStorage('cache', addon=None)
