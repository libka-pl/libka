from .base import LIBKA_ID
from .path import Path
from typing import Optional, Union, Dict
from xbmcvfs import translatePath
from xbmcaddon import Addon as XbmcAddon


class Resources:
    """
    Access do Addon resources.
    """

    def __init__(self, addon, *, base: Optional[Union[Path, str]] = None):
        self.addon = addon
        self._base: Path = None if base is None else Path(base)
        self._media: Media = None
        self._exist_map: Dict[Path, bool] = {}

    @property
    def base(self):
        """Path to addon folder."""
        if self._base is None:
            self._base = Path(translatePath(self.addon.info('path')))
        return self._base

    @property
    def path(self):
        """Path to resources folder."""
        return self.base / 'resources'

    @property
    def media(self):
        """Media object."""
        if self._media is None:
            self._media = Media(self)
        return self._media

    def exists(self, path):
        if not isinstance(path, Path):
            path = Path(path)
        try:
            return self._exist_map[path]
        except KeyError:
            exists = path.exists()
            self._exist_map[path] = exists
            return exists


class Media:
    """
    Access do Addon resources media.
    """

    def __init__(self, resources: Resources):
        self.resources: Resources = resources
        self._transparent: Path = None
        self._black: Path = None
        self._white: Path = None

    @property
    def path(self) -> Path:
        """Path to media folder."""
        return self.resources.path / 'media'

    def image(self, name: str) -> Path:
        """Get image path."""
        path = self.path / name
        for suffix in ('', '.png', '.jpg'):
            p = path.with_suffix(suffix)
            if self.resources.exists(p):
                return p

    def libka_media_path(self) -> Path:
        return Path(translatePath(XbmcAddon(LIBKA_ID).getAddonInfo('path'))) / 'resources' / 'media'

    @property
    def transparent(self) -> Path:
        """Return path to 1x1 tranparent image."""
        if self._transparent is None:
            self._transparent = self.libka_media_path() / 'transparent.png'
        return self._transparent

    @property
    def black(self) -> Path:
        """Return path to 1x1 black image."""
        if self._black is None:
            self._black = self.libka_media_path() / 'black.png'
        return self._black

    @property
    def white(self) -> Path:
        """Return path to 1x1 white image."""
        if self._white is None:
            self._white = self.libka_media_path() / 'white.png'
        return self._white


# #: Libka const resources and media like "white".
# media = Media(Resources(None, base=Path(translatePath(XbmcAddon(LIBKA_ID).getAddonInfo('path'))) / 'resources'))

# Extra docs:
# - https://kodi.wiki/view/Special_protocol
