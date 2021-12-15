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


def flog(msg, level=None):
    """f-string folrmatted log."""
    if isinstance(msg, binary_type):
        msg = msg.decode('utf-8')
    msg = vfstr(msg, (), {}, depth=1)
    log(msg, level=level)
