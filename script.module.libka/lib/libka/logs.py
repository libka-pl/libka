import xbmc
from .format import vfstr


def log(*msg, sep=' ', title=None, level=None):
    """XBMC log."""
    msg = sep.join(map(str, msg))
    # if isinstance(msg, bytes):
    #     msg = msg.decode('utf-8')
    # elif not isinstance(msg, str):
    #    msg = str(msg)
    if level is None:
        level = xbmc.LOGINFO
    if title is not None:
        msg = f'===== {title} =====  {msg}'
    xbmc.log(msg, level)


def log_error(*msg, sep=' ', title=None):
    log(*msg, level=xbmc.LOGERROR)


def log_warning(*msg, sep=' ', title=None):
    log(*msg, level=xbmc.LOGWARNING)


def log_info(*msg, sep=' ', title=None):
    log(*msg, level=xbmc.LOGINFO)


def log_debug(*msg, sep=' ', title=None):
    log(*msg, level=xbmc.LOGDEBUG)


def log_xdebug(*msg, sep=' ', title=None):
    pass


log.error = log_error
log.warning = log_warning
log.info = log_info
log.debug = log_debug
log.xdebug = log_xdebug


def flog(msg, level=None, depth=0):
    """f-string formatted log."""
    if isinstance(msg, bytes):
        msg = msg.decode('utf-8')
    msg = vfstr(msg, (), {}, depth=depth+1)
    log(msg, level=level)


def flog_error(msg):
    flog(msg, level=xbmc.LOGERROR, depth=1)


def flog_warning(msg):
    log(msg, level=xbmc.LOGWARNING, depth=1)


def flog_info(msg):
    flog(msg, level=xbmc.LOGINFO, depth=1)


def flog_debug(msg):
    flog(msg, level=xbmc.LOGDEBUG, depth=1)


def flog_xdebug(msg):
    pass


flog.error = flog_error
flog.warning = flog_warning
flog.info = flog_info
flog.debug = flog_debug
flog.xdebug = flog_xdebug
