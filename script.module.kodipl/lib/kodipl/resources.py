# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals, print_function
from future.utils import PY2
if PY2:
    from builtins import *  # dirty hack
from future.utils import python_2_unicode_compatible

from pathlib import Path
from kodi_six import xbmcvfs


@python_2_unicode_compatible
class Resources(object):
    """
    Access do Addon resources.
    """

    def __init__(self, addon=None):
        if addon is None:
            addon = globals()['addon']
        self.addon = addon
        self._base = None
        self._media = None
        self._exist_map = {}

    @property
    def base(self):
        """Path to addon folder."""
        if self._base is None:
            self._base = Path(xbmcvfs.translatePath(self.addon.info('path')))
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


@python_2_unicode_compatible
class Media(object):
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
