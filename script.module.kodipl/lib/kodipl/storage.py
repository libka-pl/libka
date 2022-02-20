import json
from typing import (
    Union, Any,
    List,
)
from xbmcvfs import translatePath
from .path import Path
from .logs import log


class NoDefault:
    """Helper. Default doesn't exist."""


class Storage:
    """
    Simple ata storage in .kodi/user_data/...
    """

    def __init__(self, path=None, * addon):
        self.addon = addon
        self.path = None if path is None else Path(path)

    @property
    def base(self):
        """Path to addon folder."""
        if self._base is None:
            self._base = Path(translatePath(self.addon.info('profile')))
        return self._base


class AddonUserData:
    """Simple userdata JSON file."""

    def __init__(self, path=None, default: Any = None, *, addon):
        self.path = Path('data.json' if path is None else path)
        self.addon = addon
        if not self.path.is_absolute():
            if addon is None:
                from xbmcaddon import Addon  # fallbavk
                base = Addon().getAddonInfo('profile')
            else:
                base = self.addon.info('profile')
            self.path = Path(translatePath(base)) / self.path
        self.default = default
        self.dirty = False
        self._data = None

    @property
    def data(self):
        """Lazy load and get data."""
        if self._data is None:
            try:
                with open(self.path, 'r') as f:
                    self._data = json.load(f)
            except IOError as exc:
                log.warning(f'AddonUserData({self.path}): load failed: {exc!r}')
        return self._data

    def do_save(self, indent: int = None):
        """Save data."""
        if self._data is None:
            return
        try:
            path = self.path.resolve()
            path.parent.mkdirs(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                self._data = json.dump(self._data, f, indent=indent)
        except IOError as exc:
            log.error(f'AddonUserData({self.path}): save failed: {exc!r}')

    def save(self, indent: int = None):
        """Save file if data changed."""
        if self.dirty:
            self.do_save(indent=indent)

    def get(self, key: Union[str, List[str]], default: Any = NoDefault):
        """Get dot-separated key value."""
        if self.data is None:
            return default
        if default is NoDefault:
            default = self.default
        if isinstance(key, str):
            key = key.split('.')
        data = self.data
        for item in key:
            try:
                data = data[item]
            except Exception:
                return default
        return data

    def set(self, key: Union[str, List[str]], value: Any):
        """Set dot-separated key value. Force dicts in path."""
        if not key:
            return
        self.dirty = True
        if isinstance(key, str):
            key = key.split('.')
        if not isinstance(self.data, dict):
            self._data = {}
        data = self.data
        for item in key[:-1]:
            sub = data.setdefault(item, {})
            if not isinstance(sub, dict):
                data[item] = {}
            data = sub
        data[key[-1]] = value

    def remove(self, key: Union[str, List[str]]):
        """Remove dot-separated key value."""
        if not key or self.data is None:
            return
        if isinstance(key, str):
            key = key.split('.')
        if not isinstance(self.data, dict):
            self._data = {}
        data = self.data
        for item in key[:-1]:
            sub = data.get(item)
            if not isinstance(sub, dict):
                return
            data = sub
        if key[-1] in data:
            self.dirty = True
            del data[key[-1]]

    delete = remove
