from kodipl.path import Path
from xbmcvfs import translatePath


class Resources:
    """
    Access do Addon resources.
    """

    def __init__(self, addon):
        self.addon = addon
        self._base = None
        self._media = None
        self._exist_map = {}

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

    def __init__(self, resources):
        self.resources = resources

    @property
    def path(self):
        """Path to media folder."""
        return self.resources.path / 'media'

    def image(self, name):
        """Get image path."""
        path = self.path / name
        for suffix in ('', '.png', '.jpg'):
            p = path.with_suffix(suffix)
            if self.resources.exists(p):
                return p


# Extra docs:
# - https://kodi.wiki/view/Special_protocol
