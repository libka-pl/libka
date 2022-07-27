"""
User data storage module.

`Storage` allows to load and save user date in easy way. Could be instanced in any time with any file path.

`libka.addon.Addon` instance has already created `Storage` available as `self.user_data`. It is auto-save on
end of `libka.addon.Addon.run()` method, even if exception raises.

>>> class Main(SimplePlugin):
>>>    def foo(self):
>>>        n = self.user_data.get('bar.baz', 0)
>>>        self.user_data.set('bar.baz', n + 1)
"""

from typing import (
    Optional, Union, Any,
    Tuple, List, Dict,
)
from contextlib import contextmanager
from copy import deepcopy
from inspect import isclass, ismodule
from shutil import move
import json
from .base import BaseAddon
from .path import Path
from .registry import register_singleton
from .logs import log
from .serializer import SerializerType
from .serializer.json import Json
from .serializer.pickle import Pickle
from .serializer.module import Module


class NoDefault:
    """Helper. Default doesn't exist."""


class Storage:
    """
    Simple data storage in `~/.kodi/user_data/addon_data/*/...`.

    Parameters
    ----------
    path : libka.path.Path or str or None
        Relative path to addon profile directory or absolute path. If None, `data.json`¹ is used.
    addon : libka.addon.Addon
        Main addon instance or None.
    sync : bool
        If true data are saved after every `Storage.set()` and `Storage.remove()`. Default false.
    pretty : bool
        Write pretty data if serializer handle it (ex. `json`).
    serializer: str or object or class or module
        Serializer and deserializer for data.

    Main API is `Storage.get()`, `Storage.set()` and `Storage.remove()`.

    Supported serialisers:

    - `json` – use JSON
    - `pickle` – user pickle module
    - object – use ovject `load(path)` and `save(data, path, pretty)`
    - class – create and use `class()` object
    - module – call `module.load(f)` and `module.dump(data, f)`, where `f` is opened binary file
               like `pickle` or `marshal`

    ¹) File extension depends on `serializer.SUFFIX` or ".data" otherwise.
    """

    #: Serializer classes
    SERIALIZER: Dict = {
        'json': Json,
        'pickle': Pickle,
        json: Json,
    }

    def __init__(self, path: Optional[Union[Path, str]] = None, *, addon: BaseAddon, default: Optional[Any] = None,
                 sync: Optional[bool] = False, pretty: Optional[bool] = True,
                 serializer: Optional[Union[SerializerType, str]] = None):
        # Guess data serializer.
        if serializer is None:
            serializer = Json
        else:
            serializer = self.SERIALIZER.get(serializer, serializer)
        if ismodule(serializer):
            serializer = Module(module=serializer)
        elif isclass(serializer):
            serializer = serializer()
        # Guess suffix and storage path.
        suffix: str = getattr(serializer, 'SUFFIX', 'data')
        if path is None:
            path = 'data{suffix}'
        if isinstance(path, str):
            path = path.format(suffix=suffix)
        #: Addon.
        self.addon: BaseAddon = BaseAddon() if addon is None else addon
        #: Seriazier object (ex. JSON, Pickle).
        self.serializer = serializer
        #: Base path to folder with storage. Lazy loaded.
        self._base: Path = None
        #: Default suffix for file(s).
        self.suffix: str = suffix
        #: Path to stoarge (file or directory if masterkey is True).
        self._path: Path = Path(path)
        #: Default value if missing key.
        self.default: Any = default
        #: If true data are saved after every `Storage.set()` and `Storage.remove()`.
        self.sync: bool = sync
        self._dirty: bool = False
        self._data: Dict[str, Any] = None
        self._transactions: Dict[str, Any] = []

    @property
    def base(self) -> Path:
        """Path to addon profile folder."""
        if self._base is None:
            self._base = self.addon.profile_path
        return self._base

    @property
    def path(self) -> Path:
        """Storage file path."""
        if not self._path.is_absolute():
            self._path = self.base / self._path
        return self._path

    @property
    def data(self) -> Dict[str, Any]:
        """Lazy load and get all data like `Storage.get` with `('')` or `([])`."""
        if self._data is None:
            try:
                self._data = self.serializer.load(self.path)
            except IOError as exc:
                log.warning(f'Storage({self.path}): load failed: {exc!r}')
        return self._data

    @property
    def dirty(self) -> bool:
        """Read dirty flag. True id data needs to be written."""
        return self._dirty

    def _do_save(self) -> None:
        """Helper. Save data."""
        if self._data is None:
            return
        try:
            path = self.path.resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            # os.chmod(path.parent, 0o777)
            tmp_path = path.with_stem(f'.new.{path.stem}')
            self.serializer.save(self._data, tmp_path)
        except IOError as exc:
            log.error(f'Storage({self.path}): save failed: {exc!r}')
            try:
                tmp_path.unlink()
            except IOError:
                pass
        else:
            log.xdebug(f'{tmp_path!r} -> {path!r}')
            try:
                move(tmp_path, path)
            except IOError as exc:
                # for Windows rename() fails on existing file
                # then remove target file and try rename again
                log.info(f'Storage({self.path}): rename failed: {exc!r}')
                path.unlink()
                move(tmp_path, path)

    def save(self) -> None:
        """Save file if data changed."""
        if self._dirty:
            self._do_save()

    def get(self, key: Union[str, List[str]], default: Any = NoDefault) -> Any:
        """
        Get dot-separated key value.

        Parameters
        ----------
        key : str or list of str
            Value path like `'a.b.c'` where `value` is stored.
            Could be as list of keys like `['a', 'b', 'c']`.

        Returns
        -------
        Value pointed by `key`. Could be complex like `list` or `dict`.
        """
        if default is NoDefault:
            default = self.default
        if self.data is None:
            return default
        if isinstance(key, str):
            key = key.split('.')
        data = self.data
        for item in key:
            try:
                data = data[item]
            except Exception:
                return default
        return data

    def set(self, key: Union[str, List[str]], value: Any) -> None:
        """
        Set dot-separated key value. Force `dict` in key-path.

        Parameters
        ----------
        key : str or list of str
            Value path like `'a.b.c'` where `value` will be stored.
            Could be as list of keys like `['a', 'b', 'c']`.
        value : any
            Value to storage. Could be complex like `list` or `dict`.

        If any of key-path doesn't exist or is not a `dict`, new `dict` is created.
        >>> data = Storage(addon=addon)
        >>> data.data()
        >>> # {'a': {'b': 2}}
        >>> data.set('a.b.c', 3)
        >>> data.data()
        >>> # {'a': {'b': {'c': 3}}}
        """
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

    def remove(self, key: Union[str, List[str]]) -> None:
        """
        Remove dot-separated key value.
        `Storage.remove()` and `Storage.delete()` is the same method.

        Parameters
        ----------
        key : str or list of str
            Value path like `'a.b.c'` where `value` is stored.
            Could be as list of keys like `['a', 'b', 'c']`.

        Remove missing key do nothing.
        """
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

    @contextmanager
    def transaction(self):
        """
        Set transaction to keep all operations set or not. Even if exception raises.

        >>> with self.transaction() as data:
        >>>     data.set('foo', 1)
        >>>     raise Exception()  # test
        >>>     data.set('bar', 2)
        """
        try:
            self._transactions.append(deepcopy(self._data))
            yield self
        except BaseException:
            # restore old copy and continue exception
            self._data = self._transactions.pop()
            raise
        else:
            # ignore old copy
            self._transactions.pop()


class MultiStorage(Storage):
    """
    Storage with several parts (ex. files). API is the same.
    """

    def __init__(self, path: Optional[Union[Path, str]] = None, *, addon: BaseAddon, default: Optional[Any] = None,
                 sync: Optional[bool] = False, pretty: Optional[bool] = True,
                 serializer: Optional[Union[SerializerType, str]] = None, hint: Optional[str] = None):

        # NOTE.
        # There is no base Storage() constructor called. There is not `super().__init__`.
        # Handle single or multi files is different.

        # Guess data serializer.
        if serializer is None:
            serializer = Json
        else:
            serializer = self.SERIALIZER.get(serializer, serializer)
        if ismodule(serializer):
            serializer = Module(module=serializer)
        elif isclass(serializer):
            serializer = serializer()
        # Guess suffix and storage path.
        suffix: str = getattr(serializer, 'SUFFIX', 'data')
        if path is None:
            path = 'data'
        if isinstance(path, str):
            path = path.format(suffix=suffix)
        #: Addon.
        self.addon: BaseAddon = BaseAddon() if addon is None else addon
        #: Seriazier object (ex. JSON, Pickle).
        self.serializer: SerializerType = serializer
        #: Base path to folder with storage. Lazy loaded.
        self._base: Path = None
        #: Default suffix for file(s).
        self.suffix: str = suffix
        #: Path to storage folder.
        self._path: Path = Path(path)
        #: Default value if missing key.
        self.default: Any = default
        #: If true data are saved after every `Storage.set()` and `Storage.remove()`.
        self.sync: bool = sync
        #: Pretty serializer format. Not used now.
        self.pretty: bool = pretty
        #: Storages.
        self._storages: Dict[str, Storage] = {}

    def subpath(self, key: str) -> Path:
        """Storage file path."""
        return (self.path / key).with_suffix(self.suffix)

    @property
    def data(self) -> Dict[str, Any]:
        """Lazy load and get all data from all files like `Storage.get` with `('')` or `([])`."""
        data = {}
        for path in self.path.glob(f'*{self.suffix}'):
            key = path.stem
            storage, _ = self._substorage([key])
            data[key] = storage.data
        return data

    def save(self) -> None:
        """Save file if data changed."""
        self.path.mkdir(parents=True, exist_ok=True)
        for storage in self._storages.values():
            storage.save()

    def _substorage(self, key: Union[str, List[str]]) -> Tuple[Storage, List[str]]:
        """Returns Storage() and rest of key."""
        if isinstance(key, str):
            key = key.split('.')
        mkey: str = key[0]
        storage: Storage = self._storages.get(mkey)
        if storage is None:
            self._storages[mkey] = storage = Storage(path=self.subpath(mkey), default=self.default, sync=self.sync,
                                                     addon=self.addon, serializer=self.serializer, pretty=self.pretty)
        return storage, key[1:]

    def get(self, key: Union[str, List[str]], default: Any = NoDefault) -> Any:
        """
        Get dot-separated key value.

        Parameters
        ----------
        key : str or list of str
            Value path like `'a.b.c'` where `value` is stored.
            Could be as list of keys like `['a', 'b', 'c']`.

        Returns
        -------
        Value pointed by `key`. Could be complex like `list` or `dict`.
        """
        if default is NoDefault:
            default = self.default
        if not key:
            return self.data
        storage, key = self._substorage(key)
        return storage.get(key, default)

    def set(self, key: Union[str, List[str]], value: Any) -> None:
        """
        Set dot-separated key value. Force `dict` in key-path.

        Parameters
        ----------
        key : str or list of str
            Value path like `'a.b.c'` where `value` will be stored.
            Could be as list of keys like `['a', 'b', 'c']`.
        value : any
            Value to storage. Could be complex like `list` or `dict`.

        If any of key-path doesn't exist or is not a `dict`, new `dict` is created.
        >>> data = MultiStorage(addon=addon)
        >>> data.data()
        >>> # {'a': {'b': 2}}
        >>> data.set('a.b.c', 3)
        >>> data.data()
        >>> # {'a': {'b': {'c': 3}}}
        """
        if not key:
            return
        self.path.mkdir(parents=True, exist_ok=True)
        storage, key = self._substorage(key)
        storage.set(key, value)

    def remove(self, key: Union[str, List[str]]) -> None:
        """
        Remove dot-separated key value.
        `Storage.remove()` and `Storage.delete()` is the same method.

        Parameters
        ----------
        key : str or list of str
            Value path like `'a.b.c'` where `value` is stored.
            Could be as list of keys like `['a', 'b', 'c']`.

        Remove missing key do nothing.
        Remove empty key removes all storage files.
        """
        if not key:
            # Remove all.
            for path in self.path.glob(f'*{self.suffix}'):
                path.unlink()
            return
        if isinstance(key, str):
            key = key.split('.')
        if len(key) < 2:
            # Remove all data in sub-storage.
            path: Path = self.subpath(key[0])
            path.unlink(missing_ok=True)
            return
        storage, key = self._substorage(key)
        storage.remove(key)

    @contextmanager
    def transaction(self):
        """
        Set transaction to keep all operations set or not. Even if exception raises.

        >>> with self.transaction() as data:
        >>>     data.set('foo', 1)
        >>>     raise Exception()  # test
        >>>     data.set('bar', 2)
        """

        raise NotImplementedError()

        # TODO: load missing sub-storages (if file exists but in not loaded)
        storages = self._storages.values()
        try:
            for storage in storages:
                storage._transactions.append(deepcopy(storage._data))
            yield self
        except BaseException:
            # restore old copy and continue exception
            for storage in storages:
                storage._data = storage._transactions.pop()
            raise
        else:
            # ignore old copy
            for storage in storages:
                storage._transactions.pop()


@register_singleton
def create_storage():
    return Storage(addon=None)
