"""
Simple date & time module.
"""

from datetime import datetime, date as dt_date, time as dt_time, timedelta
from numbers import Integral
from collections.abc import Sequence
from typing import Optional, Union, List


def now() -> datetime:
    """Get now datetime. Support for external time source."""
    return datetime.now()


def local_now() -> datetime:
    """Get now datetime with timezone. Support for external time source."""
    return datetime.now().astimezone()


def str2datetime(string: str) -> datetime:
    """Convert string to datetime.date in typical formats."""
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y%m%d %H:%M:%S', '%d.%m.%Y %H:%M:%S',
                '%Y-%m-%d %H:%M', '%Y%m%d %H:%M', '%d.%m.%Y %H:%M'):
        try:
            return datetime.strptime(string, fmt)
        except ValueError:
            pass
    raise ValueError(f"date {string!r} does not match any format")


def str2date(string: str) -> dt_date:
    """Convert string to datetime.date in typical formats."""
    for fmt in ('%Y-%m-%d', '%Y%m%d', '%d.%m.%Y'):
        try:
            return datetime.strptime(string, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"date {string!r} does not match any format")


def str2time(string: str) -> dt_date:
    """Convert string to datetime.time in typical formats."""
    for fmt in ('%H:%M:%S.%f', '%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(string, fmt).time()
        except ValueError:
            pass
    raise ValueError(f"time {string!r} does not match any format")


def make_datetime(val, *, time: Optional[Union[dt_time, str, int]] = None) -> datetime:
    """
    Build datetime.datetime from `val` (string, datetime, etc.).

    If `val` has only date, `time` is used:
      - None, "min"    - mim time (00:00)
      - "max"          - max time (24:59)
      - int            - hour
      - str            - str2time() is used
      - datetime.time  - used directly
    """
    if val == 'now':
        return now()
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            return str2datetime(val)
        except ValueError:
            val = str2date(val)
    if isinstance(val, dt_date):
        if time is None:
            time = dt_time.min
        elif isinstance(time, Integral):
            time = dt_time(time)  # offset in hours
        else:
            time = make_time(time)
        return datetime.combine(val, time)
    if isinstance(val, Sequence):
        return datetime(*val)
    raise ValueError(f"unknown date {val!r}")


def make_date(d: Union[str, datetime, List[int]]) -> dt_date:
    """Build datetime.date from `d` (string, datetime, etc.)."""
    if isinstance(d, dt_date):
        return d
    if isinstance(d, str):
        return str2date(d)
    if isinstance(d, Sequence):
        return dt_date(*d)
    try:
        return d.date()
    except AttributeError:
        raise ValueError(f"unknown date {d!r} type {type(d)}")


def make_time(t: Union[str, datetime, List[int]]) -> dt_time:
    """Build datetime.time from `t` (string, datetime, etc.)."""
    if isinstance(t, dt_time):
        return t
    if isinstance(t, str):
        if t == 'min':
            return dt_time.min
        if t == 'max':
            return dt_time.max
        return str2time(t)
    if isinstance(t, Sequence):
        return dt_time(*t)
    try:
        return t.time()
    except AttributeError:
        raise ValueError(f"unknown time {t!r} type {type(t)}")


def time_delta(value: Union[int, str, None], *, unit: Optional[str] = None) -> timedelta:
    r"""
    Convert any type of fime offset to datetime.timedelta().

    Value:
        "Ns" - N seconds
        "Nm" - N minutes
        "Nh" - N hours
        "Nd" - N days
        "Nw" - N weeks
        "H:M:S" or "H:M" or "H"
        "N" or N    - number means N `unit` (default: hours).
    """

    units = {'s': 'seconds', 'm': 'minutes', 'h': 'hours', 'd': 'days', 'w': 'weeks'}
    if value is None:
        return timedelta()
    if isinstance(value, str):
        if value and value[-1] in units:
            kwargs = {units[value[-1]]: int(value[:-1])}
            return timedelta(**kwargs)
        if ':' in value:
            h, m, *s = value.split(':', 2)
            s = int(s[0]) if s else 0
            return timedelta(hours=int(h), minutes=int(m), seconds=s)
    if unit is None:
        return timedelta(hours=int(value))
    unit = units.get(unit, unit)
    kwargs = {unit: int(value)}
    return timedelta(**kwargs)
