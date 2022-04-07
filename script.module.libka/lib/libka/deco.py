"""
Some useful decorators.
"""

from functools import wraps
from .logs import log
from .tools import do_call, CallDescr
import xbmc


def repeat_call(tries=3, delay=0, catch=Exception, *, on_fail=None):
    """
    Repeat call on filed decorator, try `tries` times. Delay `delay` between retries.

    Parameters
    ----------
    tries : int
        Numer of tries. Repeat `tries - 1` times.
    delay : float
        Delay between retries. in seconds.
    catch : Exception
        Exception to catch on retry.
    on_fail : callable
        Function to call if all retries fail.


    `on_fail` uses `libka.tools.do_call` than is supports class method decorations.

    >>> class A:
    >>>     def failed(self):
    >>>         ...
    >>>
    >>>     @repeat_call(tries=5, catch=IOError, on_fail=failed)
    >>>     def io_method(self, url):
    >>>         ...
    """

    def decorator(method):

        @wraps(method)
        def wrapper(*args, **kwargs):
            for n in range(tries):
                if n:
                    xbmc.sleep(int(1000 * delay))
                try:
                    return method(*args, **kwargs)
                except catch as exc:
                    log.debug(f'{method}(*{args}, **{kwargs}): failed n={n}: {exc}')
            if on_fail is not None:
                return do_call(on_fail, ref=CallDescr(method, args, kwargs))

        return wrapper

    # w/o parameters: @repeat_call
    if callable(tries):
        method, tries = tries, 3
        return decorator(method)
    # with parameters: @repeat_call()
    return decorator


if __name__ == '__main__':
    pass
