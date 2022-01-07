# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals, print_function
from future.utils import PY2
if PY2:
    from builtins import *  # dirty hack, force py2 to be like py3

from collections import namedtuple
from kodi_six import xbmc
from kodi_six import xbmcvfs
# traversal modules
from kodi_six import (
    xbmcaddon,
    xbmcdrm,
    xbmcgui,
    xbmcplugin,
)


version_info_type = namedtuple('version_info_type', 'major micro minor')
version_info_type.__new__.__defaults__ = 2*(0,)


def get_kodi_version_info():
    """Return major kodi version as int."""
    # Kodistubs returns empty string, so guass Kodi by Python version.
    if PY2:
        default = '18'
    else:
        default = '19'
    ver = xbmc.getInfoLabel('System.BuildVersion') or default
    ver = ver.partition(' ')[0].split('.', 3)[:3]
    return version_info_type(*(int(v.partition('-')[0]) for v in ver))


version_info = get_kodi_version_info()

version = version_info.major

K18 = (version == 18)
K19 = (version == 19)
K20 = (version == 20)


# Added missing context manager support in K18.
# It's in Kodi since K19.
if not hasattr(xbmcvfs.File, '__enter__'):

    class File(xbmcvfs.File):
        __doc__ = xbmcvfs.File.__doc__

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()

    xbmcvfs.File = File


if not hasattr(xbmcvfs, 'translatePath'):
    xbmcvfs.translatePath = xbmc.translatePath

if not hasattr(xbmcvfs, 'validatePath'):
    xbmcvfs.validatePath = xbmc.validatePath

if not hasattr(xbmcvfs, 'makeLegalFilename'):
    xbmcvfs.makeLegalFilename = xbmc.makeLegalFilename
