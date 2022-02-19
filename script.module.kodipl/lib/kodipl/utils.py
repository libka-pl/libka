"""
KodiPL set of utils.

Author: rysson + stackoverflow
"""

import re
from collections import namedtuple
from itertools import chain
import pickle
from base64 import b64encode, b64decode
from urllib.parse import quote_plus
from urllib.parse import parse_qsl
from collections.abc import Mapping, Callable
from functools import partial
import inspect
import gzip
from typing import (
    Optional, Union, Type,
    Set,
)
from pathlib import Path
from .types import KwArgs


class adict(dict):
    """
    Simple dict with attribute access.

    Now dct.foo is dct['foo'].
    Missing attribute is None.

    Exmaple
    -------
    >>> dct = adict(foo='baz')
    >>> dct.foo is dct['foo']
    >>> dct.bar is None
    >>> dct['bar']
        KerError: 'bar'
    """

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            return None

    def __getstate__(self):
        return dict(self)


def mkmdict(seq, *, container=None):
    """Make multi-dict {key: [val, val]...}."""
    if container is None:
        container = {}
    for key, val in seq:
        container.setdefault(key, []).append(val)
    return container


def item_iter(obj):
    """
    Return item (key, value) iterator from dict or pair sequence.
    Empty seqence for None.
    """
    if obj is None:
        return ()
    if isinstance(obj, Mapping):
        return obj.items()
    return obj


def get_attr(obj, name, *, default=None, sep='.'):
    """
    Get attribute `name` separated by `sep` (default a dot).

    If `obj` is None, first symbol id point to global variable.
    """
    if not name:
        return default
    if isinstance(name, str):
        name = name.split(sep)
    if obj is None:
        try:
            obj = globals()[name[0]]
        except KeyError:
            return default
        name = name[1:]
    for key in name:
        try:
            obj = getattr(obj, key)
        except AttributeError:
            return default
    return obj


def encode_data(data):
    """Raw Python data decode. To get *raw* Python data from URL."""
    octet = b64encode(gzip.compress(pickle.dumps(data)), b'-_').replace(b'=', b'')
    return octet.decode('ascii')


def decode_data(octet):
    """Raw Python data encode. To put *raw* Python data into URL."""
    if not isinstance(octet, bytes):
        octet = octet.encode('utf8')
    mod = len(octet) % 4
    if mod:  # restore padding
        octet += b'=' * (4 - mod)
    return pickle.loads(gzip.decompress(b64decode(octet, b'-_')))


def xit(*seq):
    """Yield non-empty items as string."""
    for x in seq:
        if x:
            yield str(x)


ParsedUrl = namedtuple('ParsedUrl', 'raw scheme credentials host port path query fragment', defaults=(None,))
"""
Paresed URL.

Fields:
 - raw       - Raw (input) URL string.
 - scheme    - URL scheme, ex. "plugin://" for Kodi plugin.
 - authority - URL host with user and pass and port
 - path      - URL path, ex. method to call in KodiPL Addon.
 - query     - multi-dictionary to handle arrays.
 - fragemnt  - URL fragemnt (after '#') should never be used in server URL.

Properties:
 - link      - link to plugin (scheme, host and path).
 - host      - host, ex. plugin ID for Kodi plugin.
 - port      - port (not used in Kodi).
 - user      - user (not used in Kodi).
 - password  - password (not used in Kodi).
 - args      - single query args (last form query).
"""
ParsedUrl.link = property(lambda self: '%s://%s%s' % (self.scheme or 'plugin', self.host, self.path or '/'))
ParsedUrl.user = property(lambda self: self.credentials.partition(':')[0])
ParsedUrl.password = property(lambda self: self.credentials.partition(':')[2])
ParsedUrl.authority = property(lambda self: '@'.join(xit(self.credentials, ':'.join(xit(self.host, self.port or '')))))
ParsedUrl.args = property(lambda self: adict((k, vv[-1]) for k, vv in self.query.items() if vv))
#ParsedUrl.__repr__ = lambda self: 'ParsedUrl(%r)' % self.raw
ParsedUrl.__str__ = lambda self: self.raw
# ParsedUrl._to_str = lambda self: ':'.join(
#     xit(self.scheme, ''.join(self.authority, xit('?'.join(
#         self.path, xit('#'.join(xit(self.encode_params(self.query), self.fragment))))))))
# ParsedUrl.replace = lambda self, **kwargs: self._replace(raw=self._to_str(), **kwargs) if True else None


def parse_url(url: str, *, raw: Optional[Set[str]] = None) -> ParsedUrl:
    """
    Split URL into link (scheme, host, port...) and encoded query and fragment.

    `raw` are decoded (from pickle+gzip+base64).
    """
    def parse_val(key, val):
        if key in raw:
            return decode_data(val)
        return val

    if raw is None:
        raw = ()
    r = parse_url.re.fullmatch(url or '')
    # if not r:
    #     raise ValueError(f'Invalid URL {url!r}')
    assert r, 'URL regex failed'
    kwargs = {k: v or '' for k, v in parse_url.re.fullmatch(url or '').groupdict().items()}
    kwargs['query'] = mkmdict((k, parse_val(k, v)) for k, v in parse_qsl(kwargs['query']))
    path, port = kwargs['path'], kwargs['port']
    try:
        port = int(port) if port else 0
    except ValueError:
        raise ValueError(f'Invalid URL {url!r}: port {port!r} not an integer in range 1..65535') from None
    if port > 65535:
        raise ValueError(f'Invalid URL {url!r}: port {port} not in range 1..65535')
    kwargs['port'] = port or None
    if kwargs['host'] and not path.startswith('/'):
        kwargs['path'] = f'/{path}'
    return ParsedUrl(url, **kwargs)


parse_url.re = re.compile((r'(?:(?P<scheme>[a-z][-+.a-z0-9]*):)?'
                           r'(?://(?:(?P<credentials>[^@/?#]*)@)?(?:(?P<host>[^:/?#]+)(?::(?P<port>[^/?#]*))?)?)?'
                           r'(?P<path>[^?#]*)?'
                           r'([?](?P<query>[^#]*))?(#(?P<fragment>.*))?'), re.IGNORECASE)


def build_parsed_url_str(url):
    """Helper. Build raw (user readable) URL string."""
    out = ''
    if url.scheme:
        out += f'{url.scheme}:'
    if url.host:
        out += '//'
    out += url.authority
    out += url.path
    if url.query:
        out += f'?{encode_params((k, v) for k, vv in url.query.items() for v in vv)}'
    if url.fragment:
        out += f'#{url.fragment}'
    return out


def encode_params(params=None, *, raw=None):
    """
    Helper. Make query aparams with given data.

    Path is appended (if exists).
    All data from `params` are quoted.
    All data from `raw` are picked (+gzip +b64).
    """
    def quote_str_plus(s):
        if not isinstance(s, str):
            s = str(s)
        return quote_plus(s)

    params = item_iter(params)
    raw = item_iter(raw)
    return '&'.join(chain(
        ('%s=%s' % (quote_str_plus(k), quote_str_plus(v)) for k, v in params),
        ('%s=%s' % (quote_str_plus(k), encode_data(v)) for k, v in raw)))


def encode_url(url: Union[str, ParsedUrl], path: Optional[Union[str, Path]] = None,
               params: Optional[KwArgs] = None, *, raw: Optional[KwArgs] = None):
    """
    Helper. Make URL with given data.

    Path is appended (if exists) or replaced (if starts with '/').
    All data from `params` are quoted.
    All data from `raw` are picked (+gzip +b64).
    """
    def join(old, new):
        if new.startswith('/'):
            return new
        parent = old.rpartition('/')[0]
        return f'{parent}/{new}'

    def quote_str_plus(s):
        if not isinstance(s, str):
            s = str(s)
        return quote_plus(s)

    if url is None:
        raise TypeError(f'encode_url: url must str or ParsedUrl not {url.__class__.__name__}')

    if isinstance(url, str):
        if path is not None:
            r = parse_url.re.fullmatch(url)
            if not r or ((port := r['port']) and not port.isdigit()):
                raise ValueError(f'Invalid URL {url!r}')
            old = r['path']
            n = r.start('path')
            url = url[:n] + join(old, path)
        if not params and not raw:
            return url
        sep = '&' if '?' in url else '?'
        return '%s%s%s' % (url, sep, encode_params(params=params, raw=raw))

    if path is not None:
        url = url._replace(path=join(url.path, path), query=mkmdict(()), fragment='')
    if params:
        mkmdict(((quote_str_plus(k), quote_str_plus(v)) for k, v in params.items()), container=url.query)
    if raw:
        mkmdict(((quote_str_plus(k), encode_data(v)) for k, v in raw.items()), container=url.query)
    # rebuild raw string of url
    return url._replace(raw=build_parsed_url_str(url))


def setdefaultx(dct, key, *values):
    """
    Set dict.default() for first non-None value.
    """
    for value in values:
        if value is not None:
            dct.setdefault(key, value)
            break
    return dct


# Author: Yoel
# See https://stackoverflow.com/a/25959545/9935708
def get_class_that_defined_method(meth: Callable) -> Type:
    """Returns class where method is defined or None."""
    if isinstance(meth, partial):
        return get_class_that_defined_method(meth.func)
    if inspect.ismethod(meth):
        for cls in inspect.getmro(meth.__self__.__class__):
            if meth.__name__ in cls.__dict__:
                return cls
        meth = meth.__func__  # fallback to __qualname__ parsing
    if inspect.isfunction(meth):
        cls = getattr(inspect.getmodule(meth),
                      meth.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0],
                      None)
        if isinstance(cls, type):
            return cls
    return getattr(meth, '__objclass__', None)  # handle special descriptor objects
