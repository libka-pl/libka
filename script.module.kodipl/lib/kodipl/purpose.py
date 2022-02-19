
from collections.abc import Callable
from types import MethodType
from typing import Any, Type
from .utils import adict


def purpose_decorator(*, name: str, method: Callable, value: Any = True):

    def decorator(method):
        purpose = getattr(method, '_kodipl_purpose', adict())
        method._kodipl_purpose = purpose
        purpose[name] = value
        return method

    if method is not None:
        return decorator(method)
    return decorator


def find_purpose(obj: Any, name: str):
    """
    Scan class `cls` and find first purpose matching to `name`.
    """
    if isinstance(obj, type):
        obj, cls = None, obj
    else:
        cls = obj.__class__
    none = adict()
    for method in vars(cls).values():
        purpose = getattr(method, '_kodipl_purpose', none)
        if purpose.get(name):
            if obj is not None:
                method = MethodType(method, obj)
            return method
