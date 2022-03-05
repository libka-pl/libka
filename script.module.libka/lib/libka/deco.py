"""
Some useful decorators.
"""

from functools import wraps
from inspect import ismethod
from .utils import get_class_that_defined_method
import xbmc


def repeat_call(repeat, delay=0, catch=Exception, *, on_fail=None):
    """
    Repeat `repeat` times. Delay `delay` between retries.
    """

    def decorator(method):

        @wraps(method)
        def wrapper(*args, **kwargs):
            for n in range(repeat):
                try:
                    return method(*args, **kwargs)
                except catch as exc:
                    print(f'{method}(*{args}, **{kwargs}): failed n={n}: {exc}')
                xbmc.sleep(int(1000 * delay))
            if on_fail is not None:
                on_fail()

        return wrapper

    return decorator
