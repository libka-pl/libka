"""
Access to sites. Wrapper for requests module.

.. include:: ../../../doc/en/site.md


See: https://docs.python-requests.org/en/latest/user/quickstart/
"""

from typing import (
    TYPE_CHECKING,
    Union, Any,
)
from functools import wraps
from collections.abc import Mapping
import requests
import json as jsonlib
from requests.exceptions import SSLError
import urllib3  # already used by "requests"
from urllib3.exceptions import MaxRetryError, SSLError as SSLError3
try:
    from json import JSONDecodeError
except ImportError:
    try:
        from simplejson.errors import JSONDecodeError
    except ImportError:
        JSONDecodeError = ValueError
from certifi import where
from http.cookiejar import LWPCookieJar
from .utils import encode_url, encode_params
from .url import URL
from .logs import log


class Undefined:
    """Helper. Value is undefined."""


class URL3Response:
    """Helper. `urllib3` request response with API similar to `requests` response."""

    def __init__(self, resp):
        #: urllib3 response.
        self.resp = resp
        #: Decoded unicode text. Lazy loaded.
        self._text = None
        #: Decoded JSON. Lazy loaded.
        self._json = None

    @property
    @wraps(requests.Response.ok)
    def ok(self):
        """Returns True if status_code is less than 400, False if not."""
        return self.resp.status < 400

    @property
    def status_code(self):
        """Integer Code of responded HTTP Status, e.g. 404 or 200."""
        return self.resp.status

    @property
    @wraps(requests.Response.content)
    def content(self):
        """Content of the response, in bytes."""
        return self.resp.data

    @property
    @wraps(requests.Response.text)
    def text(self):
        """Content of the response, in unicode."""
        if self._text is None:
            # TODO: detect html encoding
            self._text = self.resp.data.decode('utf-8')
        return self._text

    @wraps(requests.Response.json)
    def json(self, **kwargs):
        """Returns the json-encoded content of a response, if any."""
        if self._json is None:
            self._json = jsonlib.loads(self.text, **kwargs)
        return self._json

    @property
    def url(self):
        """Final URL location of Response."""
        return self.resp.geturl()

    @property
    def headers(self):
        """Case-insensitive Dictionary of Response Headers."""
        return self.resp.headers

    @property
    def cookies(self):
        """A CookieJar of Cookies the server sent back."""
        # TODO: implement
        assert False, "Not implemented yet"


def _resp_failed(on_fail):
    """
    Helper. Handle `on_fail` in value specific `Site` methods (like `Site.jget`). Must me called under `except`.

    Parameters
    ----------
    on_fail : Undefined
        Raise caught exception.
    on_fail : callable
        Call `on_fail` and returns result.
    on_fail : any
        Result to return.

    In all cases except `Undefined` result is returned as JSON.
    """
    if on_fail is Undefined:
        raise
    if callable(on_fail):
        return on_fail()
    return on_fail


class Site:
    """
    Access to sbstract site mixin.

    Site(base=None)

    Parameters
    ----------
    base: str
        Base site URL.
    cookiefile: str or Path
        Path to cookiejar file.

    Can be used as variable.
    >>> class MyAddon(Addon):
    ...    def __init__(self):
    ...        super(MyAddon, self).__init__()
    ...        self.site = Site(base='URL')
    ...        self.site.jget('https://very.good.url/')

    Can be used as mixin too like in `libka.SimplePlugin`.
    >>> class MyAddon(Site, Addon):
    ...    def __init__(self):
    ...        super(MyAddon, self).__init__(base='URL')
    ...        self.jget('https://very.good.url/')
    """

    #: Default value. True if SSL should be verified
    VERIFY_SSL = True
    #: default User-Agent
    UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.30 Safari/537.36'

    def __init__(self, *args, **kwargs):
        base = kwargs.pop('base', None)
        #: Base site URL.
        self.base = None if base is None else (URL(base) / '')
        #: Requests session.
        self._sess = None
        #: Path to cookie file or None.
        self.cookiefile = kwargs.pop('cookiefile', None)
        #: True if SSL should be verified
        self.verify_ssl = self.VERIFY_SSL
        #: User-Agent.
        self.ua = self.UA
        #: Option to use request worker (ex. `urllib3` instead of default requests).
        self.site_request_worker = None
        # --- call next contractor if Site is used as a mixin ---
        super(Site, self).__init__(*args, **kwargs)

    @property
    def sess(self):
        """Session for requests. It's created on first access."""
        # TODO: move to separate mixin Site.
        if self._sess is None:
            self._sess = requests.Session()
            if self.cookiefile is not None:
                self._sess.cookies = LWPCookieJar(self.cookiefile)
        return self._sess

    def _request(self, meth, url, *, params=None, data=None, json=None, headers=None,
                 verify=None, worker=None, cache=None, **kwargs):
        """Helper. Realize a network request."""

        def set_header(name, value):
            """Set default header, set only if not exist."""
            key = name.lower()
            if key not in header_keys:
                header_keys.add(key)
                headers[name] = value

        if verify is None:
            verify = self.verify_ssl
        if worker is None:
            worker = self.site_request_worker
        url = URL(url)
        if not url.is_absolute():
            url = self.base.join(url)
        if isinstance(params, Mapping):
            url, params = encode_url(url, params=params), None

        headers = dict(headers) if headers else {}
        header_keys = {name.lower() for name in headers}
        if json is not None:
            set_header('Content-Type', 'application/json')
            set_header('Accept', 'application/json')
        set_header('Accept', '*/*')
        if self.ua is not None:
            set_header('User-Agent', self.ua)
        # --- worker 'urllib3' ---
        if worker == 'urllib3':
            pool_kwargs = {}
            if verify is False:
                pool_kwargs['cert_reqs'] = 'CERT_NONE'
            elif verify is True:
                pool_kwargs['ca_certs'] = where()
            http = urllib3.PoolManager(**pool_kwargs)
            if json is not None:
                data = jsonlib.dumps(data).encode('utf-8')
            elif isinstance(data, Mapping):
                data = encode_params(data)
                set_header('Conttent-Type', 'application/x-www-form-urlencoded')
            elif data is not None and not isinstance(data, bytes):
                data = data.encode('utf-8')
            fields = kwargs.pop('fields', None)
            resp = http.request(meth, str(url), headers=headers, body=data, fields=fields)
            resp = URL3Response(resp)
        # --- default worker ---
        else:
            log(f'libka.req({meth}, {url!r}, params={params!r}, data={data!r}, json={json!r},'
                f' headers={headers!r}, {kwargs})')  # XXX
            resp = self.sess.request(meth, str(url), params=params, data=data, json=json, headers=headers,
                                     verify=verify, **kwargs)
        return resp

    def request(self, meth: str, url: Union[URL, str], *,
                on_fail: Any = Undefined, on_fail_wrapper: str = None, **kwargs):
        """
        Make a network request. On SSLError try to call self.ssl_dialog().

        Parameters
        ----------
        meth : str
            Uppercase request method like GET or POST.
        url : str or libka.url.URL
            Request URL.
        params : dict or list of tuples or bytes
            Query string parameters.
        data : dict or list of tuples or bytes or file-like object
            Data to send in the body of the Request.
        json : any
            A JSON serializable Python object to send in the body of the Request.
        headers : dict
            Dictionary of HTTP Headers to send.
        verify : bool
            Check certificates if true (default).
        worker : str
            Request worker. Default is `None` for requests`.
            Use `'urllib3'` for use `urllib3` (not fully supported).
        cache: bool or int
            Number of seconds to cache request result. If `True` cache for 24h.
        on_fail: any or callable
            Value (even `None`) to return on failed or callback to call on failed.

            - `Undefined` – exception is raised (default)
            - `callable` – calls `on_fail` and returns it result
            - any – result to return

        Returns
        -------
        Request response object, see `requests.Response`.

        Details
        -------
        Rest of keyword arguments (like `allow_redirects`) are redirect directly to `requests.request`.

        See: https://docs.python-requests.org/en/latest/api/#requests.request
        """
        def failed():
            if on_fail is Undefined:
                raise
            if callable(on_fail):
                return on_fail()
            return on_fail

        try:
            return self._request(meth, url, **kwargs)
        except SSLError:
            # requests SSLError
            ssl_dialog = getattr(self, 'ssl_dialog', None)
            if ssl_dialog is None:
                return failed()
            ssl_dialog()
        except MaxRetryError as exc:
            if not isinstance(exc.reason, SSLError3):
                return failed()
            # urllib3 SSLError
            ssl_dialog = getattr(self, 'ssl_dialog', None)
            if ssl_dialog is None:
                return failed()
            ssl_dialog()
        except Exception:
            return failed()
        try:
            return self._request(meth, url, **kwargs)
        except Exception:
            return failed()

    def get(self, url, **kwargs):
        """GET request. For arguments see `Site.request()`."""
        return self.request('GET', url, **kwargs)

    def post(self, url, **kwargs):
        """POST request. For arguments see `Site.request()`."""
        return self.request('POST', url, **kwargs)

    def put(self, url, **kwargs):
        """PUT request. For arguments see `Site.request()`."""
        return self.request('PUT', url, **kwargs)

    def patch(self, url, **kwargs):
        """PATCH request. For arguments see `Site.request()`."""
        return self.request('PATCH', url, **kwargs)

    def delete(self, url, **kwargs):
        """DELETE request. For arguments see `Site.request()`."""
        return self.request('DELETE', url, **kwargs)

    def jget(self, url, *, on_fail: Any = Undefined, **kwargs):
        """GET request, returns JSON. For arguments see `Site.request()`."""
        try:
            return self.get(url, **kwargs).json()
        except Exception:
            return _resp_failed(on_fail)

    def jpost(self, url, *, on_fail: Any = Undefined, **kwargs):
        """POST request, returns JSON. For arguments see `Site.request()`."""
        try:
            return self.post(url, **kwargs).json()
        except Exception:
            return _resp_failed(on_fail)

    def jput(self, url, *, on_fail: Any = Undefined, **kwargs):
        """PUT request, returns JSON. For arguments see `Site.request()`."""
        try:
            return self.put(url, **kwargs).json()
        except Exception:
            return _resp_failed(on_fail)

    def jpatch(self, url, *, on_fail: Any = Undefined, **kwargs):
        """PUT request, returns JSON. For arguments see `Site.request()`."""
        try:
            return self.patch(url, **kwargs).json()
        except Exception:
            return _resp_failed(on_fail)

    def jdelete(self, url, *, on_fail: Any = Undefined, **kwargs):
        """DELETE request, returns JSON. For arguments see `Site.request()`."""
        try:
            return self.delete(url, **kwargs).json()
        except Exception:
            return _resp_failed(on_fail)

    def txtget(self, url, *, on_fail: Any = Undefined, **kwargs):
        """GET request, returns text. For arguments see `Site.request()`."""
        try:
            return self.get(url, **kwargs).text
        except Exception:
            return _resp_failed(on_fail)

    def txtpost(self, url, *, on_fail: Any = Undefined, **kwargs):
        """POST request, returns text. For arguments see `Site.request()`."""
        try:
            return self.post(url, **kwargs).text
        except Exception:
            return _resp_failed(on_fail)


# def getRequests3(url, data=None, headers=None, params=None):
#     if not goptions.use_urllib3:
#         # force use requests
#         return getRequests(url, data=data, headers=headers, params=params)
#     try:
#         return _getRequests3(url, data=data, headers=headers, params=params)
#     except MaxRetryError as exc:
#         if not isinstance(exc.reason, SSLError3):
#             raise
#         with goptions:
#             goptions.ssl_dialog(using_urllib3=True)
#             if not goptions.use_urllib3:
#                 return getRequests(url, data=data, headers=headers, params=params)
#     return _getRequests3(url, data=data, headers=headers, params=params)
