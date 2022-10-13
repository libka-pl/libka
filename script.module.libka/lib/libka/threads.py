"""
Some threading wrapper to run requests concurrency.

See `ThreadPool` and `concurrent()`.
"""

import os
from threading import Thread, Event
from inspect import ismethod, currentframe
from collections.abc import Mapping
from itertools import chain
import time
from .tools import adict, generator
from .logs import log
from typing import (
    # TYPE_CHECKING,
    Optional, Union, Type, Any, Generator, Callable,
    Tuple, List, Dict,
)


__pdoc__ = {}
__pdoc__['Concurrent._'] = True
__pdoc__['Concurrent._keys'] = True
__pdoc__['Concurrent._values'] = True
__pdoc__['Concurrent._items'] = True
__pdoc__['Concurrent._results'] = True
__pdoc__['Concurrent._list_results'] = True
__pdoc__['Concurrent._dict_results'] = True


Params = Dict[str, Any]
Globals = Union[bool, Params]


class MISSING:
    """Internal. Type to fit as missing."""


class ThreadCall(Thread):
    """
    Thread async call. Create thread for `func(*args, **kwargs)`, should be started.
    """

    def __init__(self, func, *args, **kwargs):
        """
        Parameters
        ----------
        func : callable
            Function or method to call.
        args
            Postional arguments passed to `func()`.
        kwargs
            Named arguments passed to `func()`.

        The thread is not started.

        Result is returned by `ThreadCall.join()`
        and is be available in `ThreadCall.result` after `ThreadCall.join()` call.
        """
        super(ThreadCall, self).__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.result = None

    def run(self):
        self.result = self.func(*self.args, **self.kwargs)

    def join(self, timeout=None):
        """
        Wait until the thread terminates and returns the result.

        See: `threading.Thread.join`.
        """
        super().join(timeout)
        return self.result

    @classmethod
    def started(cls, func: Callable, *args, **kwargs) -> 'ThreadCall':
        """
        Create and start a thread.

        Parameters
        ----------
        func : callable
            Function or method to call.
        args
            Postional arguments passed to `func()`.
        kwargs
            Named arguments passed to `func()`.

        Result is returned by `ThreadCall.join()`
        """
        th: ThreadCall = cls(func, *args, **kwargs)
        th.start()
        return th


class ThreadPool:
    """
    Thread async with-statement.

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

    def start(self, func: Callable, *args, **kwargs) -> ThreadCall:
        """
        Creates and starts a thread to call `func(*args, **kwargs)`.

        Parameters
        ----------
        func : callable
            Function or method to call in the thread.
        args
            Positional `func` arguments.
        kwargs
            Named `func` arguments.

        Returns
        -------
        Created thread.
        """
        th = ThreadCall.started(func, *args, **kwargs)
        self.thread_list.append(th)
        return th

    def start_with_id(self, id: Any, func: Callable, *args, **kwargs) -> ThreadCall:
        """
        Creates and starts a thread to call `func(*args, **kwargs) and assign to given `id`.

        Parameters
        ----------
        id : any
            ID of the thread and key of the `ThreadPool.result_dict`.
        func : callable
            Function or method to call in the thread.
        args
            Positional `func` arguments.
        kwargs
            Named `func` arguments.

        Returns
        -------
        Created thread.
        """
        th = ThreadCall.started(func, *args, **kwargs)
        self.thread_list.append(th)
        self.thread_by_id[id] = th
        return th

    def join(self) -> None:
        """Join all threads by `ThreadCall.join()`."""
        for th in self.thread_list:
            th.join()

    def close(self) -> None:
        """Close `with` statement. Join threads and prepare results."""
        self.join()
        if self.thread_by_id:
            self.result = self.result_dict
        else:
            self.result = self.result_list

    @property
    def result_dict(self) -> adict:
        """`adict` with all results from threads created by `ThreadPool.start_with_id()`."""
        return adict((key, th.result) for key, th in self.thread_by_id.items())

    @property
    def result_list(self):
        """`list` with all results from threads created by `ThreadPool.start()`."""
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
    Concurrent instance request API. Allow call many concurrent method call get theirs results in easy way.

    Parameters
    ----------
    instance : any or None
        Object instance to call methods or None to ignore.
    instance_type : type or None
        Object instance class to detect instance override. If None type of `instance` is used.
    locals : bool or dict
        False to skip locals dict.
        True to grab locals dict from the caller.
        `dict` to use dict directly.
    globals : bool or dict
        False to skip globals dict.
        True to grab globals dict from the caller.
        `dict` to use dict directly.
    frame_depth : int
        Number of frames to skip when `locals` or `globals` dicts are taken.
        That allows use extra functions like `concurrent()`.
    name: str
        Concurrent and threads name. Only for mark objects.

    For brief description see `concurrent()`.

    - Methods are called using proxy object created with a `with` statement or its attribute proxy `a`.
    - Methods are taken from `instance` object, `locals` and `globals` in that order.
    - Methods are requested like simple call
    - All method call requests return result index (integer for list or name for attribute).

    `Concurrent` try to find method in given `instance` (if not None), then in `locals` and `globals`.
    Both `locals` and `globals` could be set as False to ignore them, True to grab from a caller
    or to `dict` to user date specified by the caller.

    `Concurrent` has two containers to collect threads results. One is a `list` and second is a `dict`.
    All direct calls append new thread in the list. All attribute calls inserts threads into the dict.

    **Note:** Most important things is that "call" on proxy object *does NOT* call the method directly.
    It creates a thread instead and starts the thread with the method.
    All threads are joined on the `with` statement exit.

    By list
    -------
    >>> with Concurrent(globals=True) as con:
    ...     con.foo(1, 2, c=3)
    ...     con.bar()
    >>> print(f'foo={con[0]!r}, bar={con[1]!r}')

    Where `foo()` is functions in `globals()` scope.

    Ways to create threads on the list are:
    >>> con.foo()
    >>> con._.foo()
    >>> next(con).foo()
    >>> con[len(con)].foo()
    >>> con['_'].foo()
    >>> con[...].foo()

    By attribute
    ------------
    Threads are attribute-like objects in an internal dict.
    >>> with Concurrent(globals=True) as con:
    ...     con.a.aa.foo(1, 2, c=3)
    ...     con.a.bb.bar()
    >>> print(f'foo={con.a.aa!r}, bar={con.a.bb!r}')

    Where `foo()` is functions in `globals()` scope.

    Ways to create threads on the dict are:
    >>> con['ee'].foo()
    >>> con.a.ee.foo()
    >>> con.an.ee.foo()
    >>> con.the.ee.foo()

    Results
    -------

    Same `Concurrent` result methods are created after `with` statement finished to avoid name collision.

    Sequential (added by list) results and mutable (added by attribute) results are stored separately.

    It's possible to get all results (sequential and dict values):
    >>> con.results()  # list of sequential results and dict values

    ### As list

    `Concurrent` object is sequence after close (`with` statement finished).
    >>> with Concurrent() as con:
    ...     ...
    >>> len(con), con[0], list(con)
    >>> for result in con: ...
    >>> con.dict_results()  # returns list of sequential results

    ### Ad dict

    `Concurrent` object has dict-like method after close (`with` statement finished).
    Except the pure iterator already used to sequential (added by list) results.

    >>> with Concurrent() as con:
    ...     ...
    >>> con['abc'], con.a.abc
    >>> con.keys(), con.values(), con.items()  # generators with len() support
    >>> len(con.keys())
    >>> con.dict_results()  # returns dict of mutable result (createed by attribute)

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
        """Pseudo iterator to use unnamed (as list) request as `next(con).method(...)`."""
        item = self._new_item()
        self._item_list.append(item)
        return item

    @property
    def _(self):
        """Attribute `_` to use unnamed (as list) request as `con._.method(...)`."""
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
        """
        Return a `dict.keys`-like view for mutable (created by attribute) results.

        This method is available as `Concurrent.keys()` after `with` statement finished.
        """
        return self._item_dict.keys()

    def _values(self) -> Generator[Any, None, None]:
        """
        Return a `dict.values`-like view for mutable (created by attribute) results.

        This method is available as `Concurrent.values()` after `with` statement finished.
        """
        if self._active:
            return self._item_dict.values()
        return generator((it.thread.result for it in self._item_dict.values()), length=len(self._item_dict))

    def _items(self) -> Generator[Tuple[Any, Any], None, None]:
        """
        Return a `dict.items`-like view for mutable (created by attribute) results.

        This method is available as `Concurrent.items()` after `with` statement finished.
        """
        if self._active:
            return self._item_dict.values()
        return generator(((k, it.thread.result) for k, it in self._item_dict.items()), length=len(self._item_dict))

    def _results(self) -> List[Any]:
        """
        Return all sequencial (list like) and dict values (attribute like) results as a list.

        This method is available as `Concurrent.results()` after `with` statement finished.
        """
        if self._active:
            raise RuntimeError('Concurrent is still working')
        return [it.thread.result for it in chain(self._item_list, self._item_dict.values())]

    def _list_results(self) -> List[Any]:
        """
        Return all sequencial (list like) results as a list.

        This method is available as `Concurrent.list_results()` after `with` statement finished.
        """
        if self._active:
            raise RuntimeError('Concurrent is still working')
        return [it.thread.result for it in self._item_list]

    def _dict_results(self) -> Dict[str, Any]:
        """
        Return mutable (attribute like) results as a dict.

        This method is available as `Concurrent.dict_results()` after `with` statement finished.
        """
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
    Call concurrent methods in a `with` statement.

    Parameters
    ----------
    instance : any or None
        Object instance to call methods. If None `locals()` and `globals()` will be used.
    name: str
        Concurrent and threads name. Only for mark objects.

    Allow call many concurrent method call get theirs results in easy way.

    - Methods are called using proxy object created with a `with` statement or its attribute proxy `a`.
    - Methods are taken from `instance` object, `locals` and `globals` in that order.
    - Methods are requested like simple call
    - All method call requests return result index (integer for list or name for attribute).

    **Note:** Most important things is that "call" on proxy object *does NOT* call the method directly.
    It creates a thread instead and starts the thread with the method.
    All threads are joined on the `with` statement exit.

    >>> def foo(x):
    ...     time.sleep(1)
    ...     return x**2
    >>>
    >>> with concurrent() as con:
    ...     indexes = [con.foo(x) for x in range(10)]  # by list
    ...     abc = con.a.abc.foo(10)                    # by attribute
    ...     xyz = con.a.xyz.foo(11)                    # by attribute
    ...     x12 = con.foo(12)                          # by list
    >>> print(indexes, abc, xyz, x12)
    >>> # [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] abc xyz 10
    >>> print(list(con), con[abc], con[xyz], con[x12])
    >>> # [0, 1, 4, 9, 16, 25, 36, 49, 64, 81, 144] 100 121 144
    >>> print(con.results())
    >>> # [0, 1, 4, 9, 16, 25, 36, 49, 64, 81, 144, 100, 121]
    >>> print(con.list_results())
    >>> # [0, 1, 4, 9, 16, 25, 36, 49, 64, 81, 144]
    >>> print(con.dict_results())
    >>> # {'abc': 100, 'xyz': 121}


    For details see: `Concurrent`.
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


def thread_it_zipped(function, delay: int, *args: List[List[Any]], **kwargs: Dict[str, List[Any]]) -> List[Any]:
    """
    Call `function` in threads with zipped `args` and `kwargs`.

    Parameters
    ----------
    function : calable
        Function to be executed.
    delay : int
        Duration of delay between start each thread. Zero means no delay.
    args
        Optional positional arguments for the provided function, every argument enter as a list.
        All `args` and `kwargs` lists must be same length.
    kwargs
        Optional named arguments for the provided function, every argument enter as a list.
        All `args` and `kwargs` lists must be same length.

    Returns
    -------
    List of function call results.

    Useful function for executing functions in threads

     - select function
     - choose delay when needed or enter 0
     - provide arguments as Lists, ex. thread_it_multi(function, 0, [param], key=[Value list]
     - all `args` and `kwargs` lists must be same length

    >>> def foo(a, b, *, c):
    ...     return a + b + c
    >>>
    >>> a = [11, 21, 31, 41]
    >>> b = [12, 22, 32, 42]
    >>> c = [13, 23, 33, 43]
    >>> results = thread_it_zipped(foo, 0, a, b, c=c)
    >>> # [36, 66, 96, 126]
    >>>
    >>> # foo() has called four times:
    >>> # foo(11, 12, c=13)
    >>> # foo(21, 22, c=23)
    >>> # foo(31, 32, c=33)
    >>> # foo(41, 42, c=43)
    """
    A = len(args)
    all_args = zip(*args, *kwargs.values())
    threads = [ThreadCall(function, *args[:A], **dict(zip(kwargs, args[A:]))) for args in all_args]

    for i, th in enumerate(threads):
        if i and delay:
            time.sleep(delay)
        th.start()
    return [th.join() for th in threads]


def cyclic_call(interval: float, function: Callable, *args, **kwargs) -> Thread:
    """
    Calling the `function()` in every `interval`.

    Parameters
    ----------
    interval : int
        The interval to wait before every call.
    function : callable
        The function to call in every `interval`.
    args
        The function's positional parameters.
    kwargs
        The function's keyword parameters.

    Returns
    -------
        Created thread instance.

    >>> def foo(a, b, c=0):
    >>>     print(f'foo: a={a}, b={b}, c={c}')
    >>>
    >>> cyclic_call(10, foo, 1, 2, c=3)
    >>>
    >>> # ... waiting 10 seconds
    >>> # foo: a=1, b=2, c=3
    >>> # ... waiting 10 seconds
    >>> # foo: a=1, b=2, c=3
    >>> # ...
    """

    def calling():
        while True:
            time.sleep(interval)
            function(*args, **kwargs)

    thread = Thread(target=calling)
    thread.start()
    return thread


class Timer(Thread):
    """
    Multishot Python `threading.Thread`. Calls a `function()` in every `interval`.

    Parameters
    ----------
    interval : int
        The interval to wait before every call.
    function : callable
        The function to call in every `interval`.
    args : tuple
        The function's positional parameters.
    kwargs: dict
        The function's keyword parameters.

    >>> def foo(a, b, c=0):
    >>>     print(f'foo: a={a}, b={b}, c={c}')
    >>>
    >>> timer = Timer(10, foo, (1, 2), {'c': 3})
    >>> timer.start()
    >>>
    >>> # ... waiting 10 seconds
    >>> # foo: a=1, b=2, c=3
    >>> # ... waiting 10 seconds
    >>> # foo: a=1, b=2, c=3
    >>>
    >>> timer.cancel()

    Note
    ----
    Code is taken from Python 3.10. The `oneshot` is added.
    """

    def __init__(self, interval: float, function: Callable, args: Tuple[Any] = None, kwargs: Dict[str, Any] = None,
                 *, oneshot: bool = False):
        Thread.__init__(self)
        self.interval = interval
        self.function = function
        self.args = args if args is not None else []
        self.kwargs = kwargs if kwargs is not None else {}
        self.oneshot = oneshot
        self.finished = Event()

    def cancel(self):
        """Stop the timer if it hasn't finished yet."""
        self.finished.set()

    def run(self):
        while not self.finished.is_set():
            self.finished.wait(self.interval)
            if not self.finished.is_set():
                self.function(*self.args, **self.kwargs)
            if self.oneshot:
                self.finished.set()
