from collections import namedtuple
import xbmc
# traversal modules (ready to monkey-pathing)
import xbmcvfs
import xbmcaddon
import xbmcdrm
import xbmcgui
import xbmcplugin


version_info_type = namedtuple('version_info_type', 'major micro minor')
version_info_type.__new__.__defaults__ = 2*(0,)


def get_kodi_version_info():
    """Return major kodi version as int."""
    default = '19'
    ver = xbmc.getInfoLabel('System.BuildVersion') or default
    ver = ver.partition(' ')[0].split('.', 3)[:3]
    return version_info_type(*(int(v.partition('-')[0]) for v in ver))


version_info = get_kodi_version_info()

version = version_info.major

K18 = (version == 18)
K19 = (version == 19)
K20 = (version == 20)
