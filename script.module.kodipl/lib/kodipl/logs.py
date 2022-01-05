# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals, print_function
from future.utils import PY2
if PY2:
    from builtins import *  # dirty hack
from future.utils import text_type, binary_type

from kodi_six import xbmc
from kodipl.format import vfstr
from kodipl.kodi import K18


def log(msg, level=None):
    """XBMC log."""
    if isinstance(msg, binary_type):
        msg = msg.decode('utf-8')
    elif not isinstance(msg, text_type):
        msg = text_type(msg)
    if level is None:
        if K18:
            level = xbmc.LOGNOTICE
        else:
            level = xbmc.LOGINFO
    xbmc.log(msg, level)


def log_error(msg):
    log(msg, level=xbmc.LOGERROR)


def log_warning(msg):
    log(msg, level=xbmc.LOGWARNING)


def log_info(msg):
    log(msg, level=xbmc.LOGINFO)


def log_debug(msg):
    log(msg, level=xbmc.LOGDEBUG)


log.error = log_error
log.warning = log_warning
log.info = log_info
log.debug = log_debug


def flog(msg, level=None, depth=0):
    """f-string folrmatted log."""
    if isinstance(msg, binary_type):
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


flog.error = flog_error
flog.warning = flog_warning
flog.info = flog_info
flog.debug = flog_debug
