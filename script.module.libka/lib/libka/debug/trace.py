import sys
import functools
from enum import IntEnum
from pathlib import Path
from typing import Optional, Union, Callable, Any, TYPE_CHECKING

import xbmc
from ..kodi import addon_id
from ..logs import log

if TYPE_CHECKING:
    import inspect
    Frame = type(inspect.currentframe())
    Code = type(inspect.currentframe().f_code)


class TraceMode(IntEnum):
    #: Trace all calls (without returns). Uses sys.settrace().
    TRACE_CALL = 1
    #: Trace all events. Uses sys.setprofile().
    TRACE_ALL = 2


if sys.version_info >= (3, 8):
    from typing import Final
    TRACE_CALL: Final[TraceMode] = TraceMode.TRACE_CALL
    TRACE_ALL: Final[TraceMode] = TraceMode.TRACE_ALL
else:
    TRACE_CALL: TraceMode = TraceMode.TRACE_CALL
    TRACE_ALL: TraceMode = TraceMode.TRACE_ALL


class TraceLogger(object):
    """
    Trace logger.

    Logs every call. Every return if set.

    Parameters
    ----------
    details: int
        Trace details (TRACE_CALL or TRACE_ALL)
    level : int or None, optional
        Kodi log level (xbmc.LOGINFO...) or None (xbmc.LOGDEBUG is used).
    use_old_trace : bool, optional
        True if old trace also should be used.
    """

    def __init__(self, details: TraceMode = TraceMode.TRACE_CALL, level: Optional[int] = None,
                 use_old_trace: bool = False):
        self.level: int = level
        self.use_old_trace: bool = use_old_trace
        self._old_trace: Callable = None
        self._running: bool = False
        self._details: TraceMode = details

    @property
    def details(self) -> TraceMode:
        """Trace details (TRACE_CALL or TRACE_ALL). Can't be changed."""
        return self._details

    @property
    def running(self) -> bool:
        """True if tracing."""
        return self._running

    def _should_skip(self, frame) -> bool:
        f, fname = frame.f_back, frame.f_code.co_filename
        while f:
            if fname.startswith('/usr/lib/'):
                return True
            if 'addons/script.module.libka/lib/libka/debug' in fname:
                return True
            f = f.f_back
        return False

    def log_trace(self, frame, event, arg) -> None:
        """
        Trace callback. See sys.settrace().
        """
        if event in ('c_call', 'c_return', 'c_exception'):
            return
        if self._should_skip(frame):
            return
        fc = frame.f_code
        fname, lno, func = fc.co_filename, fc.co_firstlineno, fc.co_name
        anames = fc.co_varnames
        pre = f'[{addon_id}][STACK] '

        def geta(k):
            try:
                v = frame.f_locals.get(k, frame.f_globals.get(k, '?????'))
                if isinstance(v, str):
                    v = v[:100]
                elif isinstance(v, list):
                    if v and isinstance(v[0], str):
                        v = list(s[:100] if isinstance(s, str) else s for s in v[:50])
                    else:
                        v = v[:50]
            except Exception as exc:
                log(f'{pre}Getting varaible {k!r} failed.', level=xbmc.LOGDEBUG)
                return f'<get {k!r} variable failed: {exc}>'
            try:
                return repr(v)
            except Exception as exc:
                log(f'{pre}Representation varaible {k!r} (type {type(v)}) failed.', level=xbmc.LOGDEBUG)
                return f'<repr {k!r} variable (type {type(v)}) failed: {exc}>'

        sargs = ', '.join(f'{k}={geta(k)}' for k in anames)
        indent: str = '  ' * fc.co_stacksize
        prespace: str = ' ' * (len(pre) + 2)
        msg: str = f'{pre}{indent}{fname}:{lno}:\n{prespace}{indent}{func}({sargs})'
        log(msg, level=xbmc.LOGDEBUG if self.level is None else self.level)
        if self.use_old_trace and self._old_trace:
            self._old_trace(
                frame, event, arg
            )  # returns None – the scope shouldn’t be traced

    def start(self) -> None:
        """Start traceing."""
        # log('[XXX] Starting! ' + str(self._details), level=xbmc.LOGINFO)
        if not self._running:
            if self._details == TraceMode.TRACE_ALL:
                self._old_trace = sys.gettrace()
                sys.settrace(self.log_trace)
            elif self._details == TraceMode.TRACE_CALL:
                self._old_trace = sys.getprofile()
                sys.setprofile(self.log_trace)
            else:
                assert False, f'Incorect details level ({self._details})'
                return
            self._running = True

    def stop(self) -> None:
        """Stop traceing."""
        # log('[XXX] Stopping!', level=xbmc.LOGINFO)
        if self._running:
            if self._details == TraceMode.TRACE_ALL:
                sys.settrace(self._old_trace)
            elif self._details == TraceMode.TRACE_CALL:
                sys.setprofile(self._old_trace)
            else:
                assert False, f'Incorect details level ({self._details})'
            self._old_trace = None
            self._running = False


#: Global trace logger.
global_trace: TraceLogger = None


def start_trace(details: TraceMode = TraceMode.TRACE_CALL, level: Optional[int] = None) -> None:
    """
    Start trace logger.

    Logs every call. Every return if set.

    Parameters
    ----------
    details: int
        Trace details (TRACE_CALL or TRACE_ALL)
    level : int or None, optional
        Kodi log level (xbmc.LOGINFO...) or None (xbmc.LOGDEBUG is used).
    """
    global global_trace
    if not global_trace:
        global_trace = TraceLogger(details=details, level=level)
        global_trace.start()


def stop_trace() -> None:
    """
    Stop trace logger.
    """
    global global_trace
    if global_trace:
        global_trace.stop()
        global_trace = None


def trace_deco(details: Union[Callable, TraceMode] = TraceMode.TRACE_CALL, level: Optional[int] = None,
               use_old_trace: bool = False) -> Callable:
    """
    Decorator for trace decoratred function.

    >>> @trace_deco
    >>> def foo():
    >>>     pass

    >>> @trace_deco(details=trace.TRACE_CALL, level=xmbc.LOGWARNING)
    >>> def foo():
    >>>     pass
    """

    def decorator(method: Callable) -> Callable:

        @functools.wraps(method)
        def wrapped(*args, **kwargs) -> Any:
            tracer: TraceLogger = TraceLogger(details=details, level=level, use_old_trace=use_old_trace)
            tracer.start()
            log(f'>>>>>>>>>>>>>>> trace started {details=!r}, level={level!r}')
            try:
                return method(*args, **kwargs)
            finally:
                tracer.stop()
                log(f'>>>>>>>>>>>>>>> trace stopped {details=!r}, level={level!r}')

        log(f'>>>>>>>>>>>>>>> need trace {details=!r}, level={level!r}')
        return wrapped

    # w/o parameters: @trace_deco
    if callable(details):
        method, details = details, TraceMode.TRACE_CALL
        return decorator(method)
    # with parameters: @trace_deco(...)
    return decorator


def profile(method: [Callable] = None, *, level: Optional[int] = None,
            path: Optional[Union[Path, str]] = None, sort: str = 'cumtime') -> Callable:
    import cProfile
    import pstats

    def wrapper(func: Callable):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            with cProfile.Profile() as pr:
                # ... do something ...
                try:
                    return func(*args, **kwargs)
                finally:
                    with open(path or '/tmp/profile', 'w') as f:
                        # pr.print_stats()
                        ps = pstats.Stats(pr, stream=f).sort_stats(sort)
                        ps.print_stats()

        log_level: int = xbmc.LOGDEBUG if level is None else level
        return wrapped

    if callable(method):
        return wrapper(method)
    return wrapper
