
from functools import wraps
from .logs import log as klog

import xbmc
import xbmcplugin
import xbmcgui


log_level_short_name = {
    xbmc.LOGDEBUG: 'DBG',
    xbmc.LOGERROR: 'ERR',
    xbmc.LOGFATAL: 'FTL',
    xbmc.LOGINFO: 'INF',
    xbmc.LOGNONE: '---',
    xbmc.LOGWARNING: 'WRN',
}


@wraps(xbmc.log)
def log(msg: str, level: int = xbmc.LOGDEBUG) -> None:
    lvl = log_level_short_name.get(level, level)
    print(f'{lvl}: {msg}')
    return xbmc_log(msg=msg, level=level)


@wraps(xbmcplugin.addDirectoryItem)
def addDirectoryItem(handle: int,
                     url: str,
                     listitem: xbmcgui.ListItem,
                     isFolder: bool = False,
                     totalItems: int = 0) -> bool:
    klog.info(f'addDirectoryItem({url!r}')
    return xbmcplugin_addDirectoryItem(handle=handle, url=url, listitem=listitem,
                                       isFolder=isFolder, totalItems=totalItems)


xbmcplugin_addDirectoryItem = xbmcplugin.addDirectoryItem
xbmc_log = xbmc.log


def xbmc_debug(console: bool = None, items: bool = None) -> None:
    """
    Switch on / off debug stuff.
    """

    if console is True:
        xbmc.log = log
    elif console is False:
        xbmc.log = xbmc_log

    if items is True:
        xbmcplugin.addDirectoryItem = addDirectoryItem
    elif items is False:
        xbmcplugin.addDirectoryItem = xbmcplugin_addDirectoryItem
