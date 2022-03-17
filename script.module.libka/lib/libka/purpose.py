
from collections.abc import Callable
from inspect import currentframe
from types import MethodType
from typing import Any
from .tools import adict


class Purpose(adict):
    """Callbacks (decorated methods) pool."""

    # def __init__(self):
    #     self.purpose = adict()


class PurposeMixin:
    """Simple mixin to collect libka purpose callbacks."""

    _libka_purpose = Purpose()


def purpose_decorator(*, name: str, method: Callable, value: Any = True):

    def decorator(method):
        frame = currentframe().f_back
        purpose = frame.f_locals.get('_libka_purpose')
        if purpose is None:
            purpose = getattr(method, '_libka_purpose', adict())
            method._libka_purpose = purpose
            purpose[name] = value
        else:
            purpose[name] = method
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
    purpose = getattr(cls, '_libka_purpose', None)
    if purpose is not None:
        return purpose.get(name)
    none = adict()
    for method in vars(cls).values():
        purpose = getattr(method, '_libka_purpose', none)
        if purpose.get(name):
            if obj is not None and not isinstance(method, MethodType):
                # bind method
                method = MethodType(method, obj)
            return method
