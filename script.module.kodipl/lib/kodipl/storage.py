from typing import (
    Union, Any,
    List,
)
from inspect import isclass
from xbmcvfs import translatePath
from .path import Path
from .logs import log
from .serializer.json import Json


class NoDefault:
    """Helper. Default doesn't exist."""


class Storage:
    """
    Simple data storage in .kodi/user_data/...
    """

    def __init__(self, path=None, *, addon, default: Any = None, sync: bool = False, pretty: bool = True,
                 serializer=None):
        if serializer is None:
            serializer = Json
        if isclass(serializer):
            serializer = serializer()
        self.addon = addon
        self.serializer = serializer
        self._base = None
        if path is None:
            path = 'data{suffix}'
        if isinstance(path, str):
            path = path.format(suffix=serializer.SUFFIX)
        self._path = Path(path)
        self.default = default
        self.sync = sync
        self._dirty = False
        self._data = None

    @property
    def base(self):
        """Path to addon folder."""
        if self._base is None:
            if self.addon is None:
                from xbmcaddon import Addon  # fallback
                base = Addon().getAddonInfo('profile')
            else:
                base = self.addon.info('profile')
            self._base = Path(translatePath(base))
        return self._base

    @property
    def path(self):
        """Starage path file."""
        if not self._path.is_absolute():
            self._path = self.base / self._path
        return self._path

    @property
    def data(self):
        """Lazy load and get data."""
        if self._data is None:
            try:
                self._data = self.serializer.load(self.path)
            except IOError as exc:
                log.warning(f'Storage({self.path}): load failed: {exc!r}')
        return self._data

    @property
    def dirty(self):
        """Read dirty flag."""
        return self._dirty

    def do_save(self):
        """Save data."""
        if self._data is None:
            return
        try:
            path = self.path.resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_stem(f'.new.{path.stem}')
            self._data = self.serializer.save(self._data, tmp_path)
            tmp_path.rename(path)
        except IOError as exc:
            log.error(f'Storage({self.path}): save failed: {exc!r}')

    def save(self):
        """Save file if data changed."""
        if self._dirty:
            self.do_save()

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
        self._dirty = True
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
        if self.sync:
            self.save()

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
            self._dirty = True
            del data[key[-1]]
        if self.sync:
            self.save()

    delete = remove
