"""
Libka set of utils.

Author: rysson + stackoverflow
"""

from itertools import chain
from urllib.parse import quote_plus
from urllib.parse import parse_qsl
from functools import partial, update_wrapper
from typing import (
    Optional, Union,
    Set,
)
from pathlib import Path
from .types import KwArgs
from .tools import (
    encode_data, decode_data,
    item_iter,
)
from .url import URL
from multidict import MultiDict, MultiDictProxy


def parse_url(url: str, *, raw: Optional[Set[str]] = None) -> URL:
    """
    Split URL into link (scheme, host, port...) and encoded query and fragment.

    `raw` are decoded (from pickle+gzip+base64).
    """
    url = URL(url)
    if raw is None:
        return url

    url.query  # access to query and buid URL._cache['query']
    query = MultiDict(parse_qsl(url.raw_query_string, keep_blank_values=True))
    for key, val in query.items():
        if key in raw:
            query[key] = decode_data(val)
    url._cache['query'] = MultiDictProxy(query)
    return url


def encode_params(params: Optional[KwArgs] = None, *, raw: Optional[KwArgs] = None) -> str:
    """
    Helper. Make query aparams with given data.

    Path is appended (if exists).
    All data from `params` are quoted.
    All data from `raw` are picked (+gzip +b64).
    """
    def quote_str_plus(s):
        if s is True:
            return 'true'
        if s is False:
            return 'false'
        if not isinstance(s, str):
            s = str(s)
        return quote_plus(s)

    params = item_iter(params)
    raw = item_iter(raw)
    return '&'.join(chain(
        ('%s=%s' % (quote_str_plus(k), quote_str_plus(v)) for k, v in params),
        ('%s=%s' % (quote_str_plus(k), encode_data(v)) for k, v in raw)))


def encode_url(url: Union[URL, str], path: Optional[Union[str, Path]] = None,
               params: Optional[KwArgs] = None, *, raw: Optional[KwArgs] = None) -> URL:
    """
    Helper. Make URL with given data.

    Path is appended (if exists) or replaced (if starts with '/').
    All data from `params` are quoted.
    All data from `raw` are picked (+gzip +b64).
    """
    if url is None:
        raise TypeError(f'encode_url: url must URL, str or ParsedUrl not {url.__class__.__name__}')

    url = URL(url)
    if path is not None:
        if isinstance(path, Path):
            path = str(path)
        url = url.join(URL(path))

    return url % encode_params(params=params, raw=raw)


print(f'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX  {__name__!r}   <==========')
if __name__ == '__main__':
    s = encode_url('http://a.b/c/d', params={'e': 42}, raw={'x': set((1, 2, 3))})
    print(f'encoding url: {s!r}')
    s = str(s)
    print(f'encoded url:  {s!r}')
    u = parse_url(s, raw={'x'})
    print(f'decoded url:  {u!r}')
    print(f'query:        {u.query!r}')
    print(f'query "x":    {u.query["x"]!r}')
