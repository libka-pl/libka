"""
Libka set of utils.

Author: rysson + stackoverflow
"""

import re
from sys import maxsize
from itertools import chain
from urllib.parse import quote_plus
from urllib.parse import parse_qsl
from typing import (
    Optional, Union, Generator,
    Any, Set, List,
)
from pathlib import Path
import json
from .types import KwArgs
from .tools import (
    encode_data, decode_data,
    item_iter,
)
from .url import URL
from multidict import MultiDict, MultiDictProxy

#: Regex type
regex = type(re.search('', ''))


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


def prepare_query_params(params: Optional[KwArgs] = None, *, raw: Optional[KwArgs] = None) -> str:
    """
    Helper. Make dict ready to query. Can be used with URL.

    Path is appended (if exists).
    All data from `params` are prepared (ex. using JSON).
    All data from `raw` are picked (+gzip +b64).
    """
    def prepare(s):
        if s is True:
            # Non-standard behavior !
            return 'true'
        if s is False:
            # Non-standard behavior !
            return 'false'
        if isinstance(s, (dict, list)):
            # Non-standard behavior !
            s = json.dumps(s)
        elif not isinstance(s, str):
            s = str(s)
        return s

    result = {}
    result.update((k, prepare(v)) for k, v in item_iter(params))
    result.update((k, encode_data(v)) for k, v in item_iter(raw))
    return result


def encode_params(params: Optional[KwArgs] = None, *, raw: Optional[KwArgs] = None) -> str:
    """
    Helper. Make query aparams with given data.

    Path is appended (if exists).
    All data from `params` are quoted.
    All data from `raw` are picked (+gzip +b64).
    """
    def quote_str_plus(s):
        if s is True:
            # Non-standard behavior !
            return 'true'
        if s is False:
            # Non-standard behavior !
            return 'false'
        if isinstance(s, (dict, list)):
            # Non-standard behavior !
            s = json.dumps(s)
        elif not isinstance(s, str):
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

    return url % prepare_query_params(params=params, raw=raw)


def find_re(pattern: Union[regex, str], text: str, *, default: str = '', flags: int = 0,
            many: bool = True) -> Union[str, List[str]]:
    """
    Search regex pattern, return sub-expr(s) or whole found text or default.

    Parameters
    ----------
    pattern : str or regex
        Regex pattern to find.
    text : str
        Text where pattern is seached.
    default : str
        Default text if pattern is not found.
    flags : int
        Regex flags like `re.IGNORECASE`.
    many : bool
        Returns all groups if there is more then one sub-expr.

    Returns
    -------
    str
        Found expresion or first subexpresion.
    list of str
        All subexpresion (if there are more then one) if `many` is true.

    Pattern can be text (str or unicode) or compiled regex.

    When no sub-expr defined returns whole matched text (whole pattern).
    When one sub-expr defined returns sub-expr.
    When many sub-exprs defined returns all sub-exprs if `many` is True else first sub-expr.

    Of course unnamed sub-expr (?:...) doesn't matter.
    """
    if not isinstance(pattern, regex):
        pattern = re.compile(pattern, flags)
    rx = pattern.search(text)
    if not rx:
        return default
    groups = rx.groups()
    if not groups:
        rx.group(0)
    if len(groups) == 1 or not many:
        return groups[0]
    return groups


def html_json_iter(html: str, var: str, *, strict: bool = True,
                   start: int = 0, end: int = maxsize) -> Generator[Any, None, None]:
    """
    Extracting JSON parts from JavaScript `<script>` tags from HTML pages generator.

    Parameters
    ----------
    html : str
        HTML page text, where JSON will be looked for.
    var : str
        JavaScript variable name `var = {...}`.
    strict : bool
        Parse JSON strict if true. If false some JS extension will be allowed like ending commas.
    start : int
        Starting offset in HTML page `html[start:]`.
    end : int
        Last offset in HTML page `html[:end]`.

    Yield
    -----
    Parsed JSON.
    """
    inside = r'(?:"(?:\\.|[^"])*"|[^;])*'
    r = re.compile(rf'\b{var}' r'\s*=\s*(\{' f'{inside}' r'\}|\[' f'{inside}' r'\])\s*;', re.DOTALL)
    for mch in r.finditer(html, pos=start, endpos=end):
        data = mch.group(1)
        if not strict:
            def repl(m):
                return ''.join((m.group(1) or '', rm_re.sub(r'\1', m.group(2))))

            rm_re = re.compile(r',(\s*[]}])', flags=re.DOTALL)
            data = re.sub(r'("(?:\\.|[^"])*")?([^"]*)', repl, data, flags=re.DOTALL)
        yield json.loads(data)


def html_json(html: str, var: str, *, strict: bool = True, start: int = 0, end: int = maxsize) -> Any:
    """
    Extract single JSON from JavaScript `<script>` tags from HTML pages.

    Parameters
    ----------
    html : str
        HTML page text, where JSON will be looked for.
    var : str
        JavaScript variable name `var = {...}`.
    strict : bool
        Parse JSON strict if true. If false some JS extension will be allowed like ending commas.
    start : int
        Starting offset in HTML page `html[start:]`.
    end : int
        Last offset in HTML page `html[:end]`.

    Returns
    -------
    Parsed JSON or None.
    """
    for data in html_json_iter(html, var, strict=strict, start=start, end=end):
        return data


if __name__ == '__main__':
    s = encode_url('http://a.b/c/d', params={'e': 42}, raw={'x': set((1, 2, 3))})
    # print(f'encoding url: {s!r}')
    assert s == URL(s)
    assert s == URL('http://a.b/c/d?e=42&x=H4sIAAAAAAAC_2tgmcrNAAH9UzS8Gb2ZvJkn6AEArwccxBYAAAA')
    s = str(s)
    # print(f'encoding url: {s!r}')
    assert s == 'http://a.b/c/d?e=42&x=H4sIAAAAAAAC_2tgmcrNAAH9UzS8Gb2ZvJkn6AEArwccxBYAAAA'
    u = parse_url(s, raw={'x'})
    # print(f'decoded url:  {u!r}')
    assert u == URL('http://a.b/c/d?e=42&x=H4sIAAAAAAAC_2tgmcrNAAH9UzS8Gb2ZvJkn6AEArwccxBYAAAA')
    # print(f'query:        {u.query!r}')
    assert u.query == MultiDict(e='42', x={1, 2, 3})
    # print(f'query "x":    {u.query["x"]!r}')
    assert u.query["x"] == {1, 2, 3}

    assert html_json('asd aa= {"qwe": ",};",};  z={ "z": "Z" };', 'aa', strict=False) == {'qwe': ',};'}
