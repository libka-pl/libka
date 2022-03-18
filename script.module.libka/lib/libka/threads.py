"""
Some threading wrapper to run requests concurrency.
"""

import os
from threading import Thread
from .tools import adict


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

    def start_with_id(self, id, func, *args, **kwargs):
        th = ThreadCall.started(func, *args, **kwargs)
        self.thread_list.append(th)
        self.thread_by_id[id] = th

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
