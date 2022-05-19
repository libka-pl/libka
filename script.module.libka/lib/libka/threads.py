"""
Some threading wrapper to run requests concurrency.
"""

import os
from threading import Thread
from inspect import ismethod, currentframe
from collections.abc import Mapping
from itertools import chain
from .tools import adict, generator
from .logs import log
from typing import (
    # TYPE_CHECKING,
    Optional, Union, Type, Any, Generator,
    Tuple, List, Dict,
)


Params = Dict[str, Any]
Globals = Union[bool, Params]


class MISSING:
    """Internal. Type to fit as missing."""


class ThreadCall(Thread):
    """
    Async call. Create thread for func(*args, **kwargs), should be started.
    Result will be in thread.result after therad.join() call.
    """

    def __init__(self, func, *args, **kwargs):
        super(ThreadCall, self).__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.result = None

    def run(self):
        self.result = self.func(*self.args, **self.kwargs)

    @classmethod
    def started(cls, func, *args, **kwargs):
        th = cls(func, *args, **kwargs)
        th.start()
        return th


class ThreadPool:
    """
    Async with-statement.

    >>> with ThreadPool() as th:
    >>>     th.start(self.vod_list, url=self.api.series.format(id=id))
    >>>     th.start(self.vod_list, url=self.api.season_list.format(id=id))
    >>> series, data = th.result
    """

    def __init__(self, max_workers=None):
        self.result = None
        self.thread_list = []
        self.thread_by_id = {}
        if max_workers is None:
            # number of workers like in Python 3.8+
            self.max_workers = min(32, os.cpu_count() + 4)
        else:
            self.max_workers = max_workers

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def start(self, func, *args, **kwargs):
        th = ThreadCall.started(func, *args, **kwargs)
        self.thread_list.append(th)
        return th

    def start_with_id(self, id, func, *args, **kwargs):
        th = ThreadCall.started(func, *args, **kwargs)
        self.thread_list.append(th)
        self.thread_by_id[id] = th
        return th

    def join(self):
        for th in self.thread_list:
            th.join()

    def close(self):
        self.join()
        if self.thread_by_id:
            self.result = self.result_dict
        else:
            self.result = self.result_list

    @property
    def result_dict(self):
        return adict((key, th.result) for key, th in self.thread_by_id.items())

    @property
    def result_list(self):
        return [th.result for th in self.thread_list]


class ConcurrentItem:
    """Helper. Single thread item in `Concurrent`."""

    def __init__(self, *, concurrent: 'Concurrent', instance: Optional[Any], locals: Params, globals: Params,
                 key: Optional[str] = None):
        #: Owner.
        self.concurrent: 'Concurrent' = concurrent
        #: Object instance (in any) to call methods.
        self.instance: Optional[Any] = instance
        #: Local dictionary.
        self.locals: Params = locals
        #: Global dictionary.
        self.globals: Params = globals
        #: Thread key (list index or attribute name), also base to thread name.
        self.key = key
        #: Current thread to work with calls.
        self.thread: ThreadCall = None

    def __repr__(self):
        return f'ConcurrentItem(thread={self.thread!r})'

    def __call__(self, instance):
        self.instance = instance
        return self

    def __getattr__(self, key):
        def concurent_call(*args, **kwargs):
            self.thread = self.concurrent._pool.start(attr, *args, **kwargs)
            if self.concurrent._name is not None and self.key is not None:
                self.thread.name = f'{self.concurrent._name}.{self.key}'
            return self.key

        if key[:1] == '_':
            raise AttributeError(key)
        if self.thread is not None:
            raise RuntimeError('Thread already launched')
        attr = getattr(self.instance, key, MISSING)
        if attr is not MISSING:
            if ismethod(attr):
                return concurent_call
            else:
                return attr
        attr = self.locals.get(key, MISSING)
        if attr is MISSING:
            attr = self.globals.get(key, MISSING)
        if attr is MISSING:
            raise AttributeError(key)
        if callable(attr):
            return concurent_call
        return attr


class Concurrent:
    """
    Concurrent instance request API.

    See `SiteMixin.concurrent`.
    """

    def __init__(self, *, instance: Optional[Any] = None, instance_type: Optional[Type] = None,
                 locals: Union[bool, Params] = False, globals: Union[bool, Params] = False,
                 frame_depth: int = 0, name: Optional[str] = None):
        def a_getattr(that, key):
            if key[:1] == '_':
                raise AttributeError(key)
            if not self._active:
                try:
                    return self._item_dict[key].thread.result
                except KeyError:
                    raise AttributeError(key) from None
            if key in self._item_dict:
                return self._item_dict[key]
            self._item_dict[key] = item = self._new_item(attr=key)
            return item

        def a_getitem(that, key):
            if not self._active:
                return self._item_dict[key].thread.result
            if key in self._item_dict:
                return self._item_dict[key]
            self._item_dict[key] = item = self._new_item(attr=key)
            return item

        def a_contains(tha, key):
            return key in self._item_dict

        def a_iter(that):
            return iter(self._item_dict)

        def a_len(that):
            return len(self._item_dict)

        if locals is True or globals is True:
            frame = currentframe().f_back
            for _ in range(frame_depth):
                frame = frame.f_back
        if locals is False:
            locals = {}
        elif locals is True:
            locals = frame.f_locals
        if globals is False:
            globals = {}
        elif globals is True:
            globals = frame.f_globals

        #: Instance of object to work with Concurrent, could be None.
        self._instance: Optional[Any] = instance
        self._instance_type: Type = type(instance) if instance_type is None else instance_type
        self._locals: Params = locals
        self._globals: Params = globals
        self._pool: ThreadPool = ThreadPool()
        self._active: bool = True
        self._item_dict: Dict[str, ConcurrentItem] = {}
        self._item_list: List[ConcurrentItem] = []
        self._exception: Optional[Exception] = None
        #: Thread name.
        self._name = name
        # Attribute-like access.
        atype = type('ConcurrentAttr', (Mapping,),
                     {'__getattr__': a_getattr, '__getitem__': a_getitem, '__contains__': a_contains,
                      '__len__': a_len, '__iter__': a_iter})
        self.a = self.an = self.the = atype()

    def _new_item(self, instance: Optional[Any] = None, *, attr: Optional[str] = None) -> ConcurrentItem:
        if not self._active:
            log.error('Call non active Concurrent()')
            raise RuntimeError('Concurent has stopped. New threads are not allowed.')
        if instance is None:
            instance = self._instance
        if attr is None:
            attr = len(self._item_list)
        return ConcurrentItem(concurrent=self, instance=self._instance,
                              locals=self._locals, globals=self._globals, key=attr)

    def __getattr__(self, key):
        if not self._active or key[:1] == '_':
            raise AttributeError(key)
        item = self._new_item()
        self._item_list.append(item)
        return getattr(item, key)

    def __getitem__(self, key):
        if key is None:
            raise KeyError('None is not allowed in Concurrent()[]')
        if not self._active:
            if type(key) is int:
                return self._item_list[key].thread.result
            return self._item_dict[key].thread.result
        instance = self._instance
        if key is ... or key == '_' or key == len(self._item_list):
            key = None  # new item
        elif type(key) is int:
            return self._item_list[key]
        elif isinstance(key, self._instance_type):
            instance = key
            key = None
        elif key and not isinstance(key, str):
            raise KeyError(key)
        item = self._new_item(instance, attr=key)
        if key:
            self._item_dict[key] = item
        else:
            self._item_list.append(item)
        return item

    def __next__(self):
        """Pseudo iterator to use unnamed request as `next(con).method(...)`."""
        item = self._new_item()
        self._item_list.append(item)
        return item

    @property
    def _(self):
        """Attribute `_` to use unnamed request as `con._.method(...)`."""
        item = self._new_item()
        self._item_list.append(item)
        return item

    def __iter__(self):
        if self._active:
            return iter(self._item_list)
        return iter(it.thread.result for it in self._item_list)

    def __call__(self, instance: Optional[Any] = None):
        if instance is None:
            instance = self._instance
        item = self._new_item(instance)
        self._item_list.append(item)
        return item

    def __len__(self):
        return len(self._item_list)

    def _keys(self) -> Generator[Any, None, None]:
        return self._item_dict.keys()

    def _values(self) -> Generator[Any, None, None]:
        if self._active:
            return self._item_dict.values()
        return generator((it.thread.result for it in self._item_dict.values()), length=len(self._item_dict))

    def _items(self) -> Generator[Tuple[Any, Any], None, None]:
        if self._active:
            return self._item_dict.values()
        return generator(((k, it.thread.result) for k, it in self._item_dict.items()), length=len(self._item_dict))

    def _results(self) -> List[Any]:
        if self._active:
            raise RuntimeError('Concurrent is still working')
        return [it.thread.result for it in chain(self._item_list, self._item_dict.values())]

    def _list_results(self) -> List[Any]:
        if self._active:
            raise RuntimeError('Concurrent is still working')
        return [it.thread.result for it in self._item_list]

    def _dict_results(self) -> Dict[str, Any]:
        if self._active:
            raise RuntimeError('Concurrent is still working')
        return {k: it.thread.result for k, it in self._item_dict.items()}

    def _close(self):
        self._pool.close()
        self._active = False
        for a in ('keys', 'values', 'items', 'results', 'list_results', 'dict_results'):
            setattr(self, a, getattr(self, f'_{a}'))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._exception = exc_val
        self._close()


def concurrent(instance: Any = None, *, name: Optional[str] = None) -> Concurrent:
    """
    Call concurent methods.
    """
    if instance is None:
        return Concurrent(locals=True, globals=True, frame_depth=1, name=name)
    return Concurrent(instance, name=name)


class ConcurrentMixin:
    """Mixin for classes with concurrent() method."""

    def concurrent(self):
        """
        Concurrent instance methods `with` block.
        """
        return Concurrent(instance=self)
