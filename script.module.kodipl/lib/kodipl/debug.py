
from functools import wraps, WRAPPER_ASSIGNMENTS
from typing import (
    List, Tuple,
)
from .logs import log as klog

import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon


log_level_short_name = {
    xbmc.LOGDEBUG: 'DBG',
    xbmc.LOGERROR: 'ERR',
    xbmc.LOGFATAL: 'FTL',
    xbmc.LOGINFO: 'INF',
    xbmc.LOGNONE: '---',
    xbmc.LOGWARNING: 'WRN',
}


def wraps_class(src):
    """Simple class wrapper, like functools.wraps."""
    def wrapper(cls):
        for attr in WRAPPER_ASSIGNMENTS:
            try:
                setattr(cls, attr, getattr(src, attr))
            except AttributeError:
                pass
        return cls

    return wrapper


@wraps(xbmc.log)
def log(msg: str, level: int = xbmc.LOGDEBUG) -> None:
    lvl = log_level_short_name.get(level, level)
    print(f'{lvl}: {msg}')
    return xbmc_log(msg=msg, level=level)


@wraps_class(xbmcgui.ListItem)
class ListItem(xbmcgui.ListItem):

    def __init__(self, label: str = "",
                 label2: str = "",
                 path: str = "",
                 offscreen: bool = False) -> None:
        self._kodipl_x_label = label
        super().__init__(label=label, label2=label2, path=path, offscreen=offscreen)

    def getLabel(self) -> str:
        return self._kodipl_x_label
        # return super().getLabel()

    def setLabel(self, label: str) -> None:
        self._kodipl_x_label = label
        return super().setLabel(label)


@wraps(xbmcplugin.addDirectoryItem)
def addDirectoryItem(handle: int,
                     url: str,
                     listitem: xbmcgui.ListItem,
                     isFolder: bool = False,
                     totalItems: int = 0) -> bool:
    label = listitem.getLabel()
    klog.info(f'addDirectoryItem({url!r}, {label!r})')
    return xbmcplugin_addDirectoryItem(handle=handle, url=url, listitem=listitem,
                                       isFolder=isFolder, totalItems=totalItems)


@wraps(xbmcplugin.addDirectoryItems)
def addDirectoryItems(handle: int,
                      items: List[Tuple[str,  ListItem,  bool]],
                      totalItems: int = 0) -> bool:
    klog.info('addDirectoryItems(\n{}\n)'.format('\n'.join(f'  ({url!r}, {item.getLabel()!r}),'
                                                           for url, item, folder in items)))
    return xbmcplugin_addDirectoryItems(handle=handle, items=items, totalItems=totalItems)


@wraps(xbmcaddon.Addon.getLocalizedString)
def getLocalizedString(self, id: str):
    s = xbmcaddon_Addon_getLocalizedString(self, id)
    return s or f'#{id}'


xbmcgui_ListItem = xbmcgui.ListItem
xbmcplugin_addDirectoryItem = xbmcplugin.addDirectoryItem
xbmcplugin_addDirectoryItems = xbmcplugin.addDirectoryItems
xbmcaddon_Addon_getLocalizedString = xbmcaddon.Addon.getLocalizedString
xbmc_log = xbmc.log


def xbmc_debug(console: bool = None, items: bool = None,
               fake: bool = None) -> None:
    """
    Switch on / off debug stuff.
    """

    if console is True:
        xbmc.log = log
    elif console is False:
        xbmc.log = xbmc_log

    if items is True:
        xbmcplugin.addDirectoryItem = addDirectoryItem
        xbmcplugin.addDirectoryItems = addDirectoryItems
    elif items is False:
        xbmcplugin.addDirectoryItem = xbmcplugin_addDirectoryItem
        xbmcplugin.addDirectoryItems = xbmcplugin_addDirectoryItems

    if fake is True:
        xbmcgui.ListItem = ListItem
        xbmcaddon.Addon.getLocalizedString = getLocalizedString
    elif fake is False:
        xbmcgui.ListItem = xbmcgui_ListItem
        xbmcaddon.Addon.getLocalizedString = xbmcaddon_Addon_getLocalizedString
