"""
KodiPL set of utils.

Author: rysson
"""

from collections import namedtuple
from itertools import chain
import pickle
from base64 import b64encode, b64decode
from urllib.parse import quote_plus
from urllib.parse import parse_qsl
from collections.abc import Mapping
import gzip


class adict(dict):
    """
    Simple dict with attribute access.

    Now dct.foo is dct['foo'].
    Missing attribute is None.

    Exmaple
    -------
    >>> dct = adict(foo='bar')
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


def mkmdict(seq):
    """Make multi-dict {key: [val, val]...}."""
    dct = {}
    for key, val in seq:
        dct.setdefault(key, []).append(val)
    return dct


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


def get_attr(obj, name, default=None, sep='.'):
    """
    Get attribute `name` separated by `sep` (default a dot).

    If `obj` is None, first symbol id point to global variable.
    """
    if isinstance(name, str):
        name = name.split(sep)
    if not name:
        return default
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


ParsedUrl = namedtuple('ParsedUrl', 'raw scheme raw_host path query fragment')
"""
Paresed URL.

Fields:
 - raw      - Raw (input) URL string.
 - scheme   - URL scheme, ex. "plugin://" for Kodi plugin.
 - raw_host - URL host with user and pass
 - path     - URL path, ex. method to call in KodiPL Addon.
 - query    - multi-dictionary to handle arrays.
 - fragemnt - URL fragemnt (after '#') should never be used in server URL.

Properties:
 - link     - link to plugin (scheme, host and path).
 - host     - host, ex. plugin ID for Kodi plugin.
 - args     - single query args (last form query).
"""
ParsedUrl.__new__.__defaults__ = 1*(None,)
ParsedUrl.link = property(lambda self: '%s://%s%s' % (self.scheme or 'plugin', self.host, self.path or '/'))
ParsedUrl.host = property(lambda self: self.raw_host.rpartition('@')[2])
ParsedUrl.args = property(lambda self: adict((k, vv[-1]) for k, vv in self.query.items() if vv))
ParsedUrl.__repr__ = lambda self: 'ParsedUrl(%r)' % self.raw
ParsedUrl.__str__ = lambda self: self.raw


def parse_url(url, encode_keys=None):
    """
    Split URL into link (scheme, host, port...) and encoded query and fragment.
    """
    def parse_val(key, val):
        if key in encode_keys:
            return decode_data(val)
        return val

    if encode_keys is None:
        encode_keys = ()
    link, _, fragment = url.partition('#')
    link, _, query = link.partition('?')
    query = mkmdict((k, parse_val(k, v)) for k, v in parse_qsl(query))
    scheme, _, link = link.rpartition('://')
    host, sep, path = link.partition('/')
    if sep:
        path = '/%s' % path
    return ParsedUrl(url, scheme, host, path, query, fragment)


def encode_params(params=None, raw=None):
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


def encode_url(url, path=None, params=None, raw=None):
    """
    Helper. Make URL with given data.

    Path is appended (if exists).
    All data from `params` are quoted.
    All data from `raw` are picked (+gzip +b64).
    """
    if path is not None:
        if url.startswith('//'):
            scheme, url = '//', url[2:]
        else:
            scheme, sep, url = url.rpartition('://')
            scheme += sep
        host, sep, link = url.partition('/')
        if path.startswith('/'):
            url = '%s%s%s' % (scheme, host, path)
        else:
            link = link.rpartition('/')[0]
            url = '%s%s%s%s' % (scheme, host, link or '/', path)
    if not params and not raw:
        return url
    sep = '&' if '?' in url else '?'
    return '%s%s%s' % (url, sep, encode_params(params=params, raw=raw))


def setdefaultx(dct, key, *values):
    """
    Set dict.default() for first non-None value.
    """
    for value in values:
        if value is not None:
            dct.setdefault(key, value)
            break
    return dct
