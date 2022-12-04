import functools
import traceback

import xbmc
from ..kodi import addon_id


INDENT = 44 * ' '


def _get_backtrace(skip=2, prefix=None):
    """
    Get backtrace lines.

    Parameters
    ----------
    skip : int
        Number of entries to skip. To avoid debug functions in backtrace.
    prefix : str or None
        Text to prefix every line.

    Returns
    -------
    str
        Backtrace string lines. All lines separated by EOL not by backtrace entry.
    """
    callstack = traceback.format_stack()
    if skip > 0:
        callstack = callstack[:-skip]
    callstack = ((prefix or '') + ln for e in callstack for ln in e.splitlines())
    return list(callstack)


def log_exception(level=None):
    """
    Log exception.

    Parameters
    ----------
    e : Exception
        Exception to log.
    level : int or None
        Kodi log level or None for default level (DEBUG).
    """
    if level is None:
        level = xbmc.LOGDEBUG
    msg = (
        'EXCEPTION Thrown: -->Python callback/script returned the following error<--\n'
    )
    msg += traceback.format_exc()
    msg += '-->End of Python script error report<--'
    xbmc.log(msg, level)


def stacktrace(func):
    """Decorator for trace function enter.

    See: https://stackoverflow.com/a/48653175
    """

    @functools.wraps(func)
    def wrapped(*args, **kwds):
        # Get all but last line returned by traceback.format_stack()
        # which is the line below.
        prefix = f'[{addon_id or "XXX"}] '
        callstack = '\n'.join(
            prefix + e.rstrip() for e in traceback.format_stack()[:-1]
        )
        callstack = '\n'.join(f'>{e}<' for e in traceback.format_stack()[:-1])
        print(f'{func.__name__}() called:')
        print(callstack)
        return func(*args, **kwds)

    return wrapped
