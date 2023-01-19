"""
Some base addon classes methods.
"""

from typing import Optional
from xbmcaddon import Addon as XbmcAddon
from xbmcvfs import translatePath
from .path import Path
from .registry import registry, register_singleton


LIBKA_ID = 'script.module.libka'


class BaseAddonMixin:
    """
    Some base addon methods.

    Needs `self.xbmc_addon`.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #: Profile path (lazy load).
        self._profile_path: Path = None

    def info(self, key: str) -> str:
        """Get XBMC addon info (like "path", "version"...)."""
        return self.xbmc_addon.getAddonInfo(key)

    @property
    def addon_path(self) -> Path:
        """Path to addon (unziped) folder."""
        if self._profile_path is None:
            path = self.xbmc_addon.getAddonInfo('path')
            self._profile_path = Path(translatePath(path))
        return self._profile_path

    @property
    def profile_path(self) -> Path:
        """Path to addon profile folder."""
        if self._profile_path is None:
            path = self.xbmc_addon.getAddonInfo('profile')
            self._profile_path = Path(translatePath(path))
        return self._profile_path


# class BaseAddonMetaclass(type):
#
#     def __call__(cls, *, id: Optional[str] = None):
#         obj = cls.__new__(cls, id=id)
#         obj.__init__(id=id)
#         return obj


class BaseAddon(BaseAddonMixin):
    """Base default addon."""

    _instances = {}

    def __new__(cls, *, id: Optional[str] = None):
        default_adoon: bool = id is None
        xbmc_addon: XbmcAddon = None
        if id is None:
            obj = BaseAddon._instances.get(None)
            if obj is not None:
                return obj
            xbmc_addon = registry.xbmc_addon
            id = xbmc_addon.getAddonInfo('id')
        else:
            xbmc_addon = XbmcAddon(id)
        if id in BaseAddon._instances:
            return BaseAddon._instances[id]
        obj = super().__new__(cls)
        obj.xbmc_addon = xbmc_addon
        BaseAddon._instances[id] = obj
        if default_adoon:
            BaseAddon._instances[None] = obj
        return obj

    def __init__(self, *, id: Optional[str] = None):
        # Call BaseAddon, our single super class.
        super().__init__()
        #: Addon ID (ex. plugin.video.myplugin).
        self.id: str = self.xbmc_addon.getAddonInfo('id') if id is None else id
        #: Kodi Addon instance.
        self.xbmc_addon: XbmcAddon

    def __repr__(self):
        return f'{self.__class__.__name__}({self.id!r})'


@register_singleton
def create_xbmc_addon():
    return XbmcAddon()
