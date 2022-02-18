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
from collections.abc import Mapping
from http.cookiejar import LWPCookieJar
from kodipl.utils import encode_url, encode_params
from kodipl.logs import log


class UL3Response:
    """urllib3 request response with API similar to requests response."""

    def __init__(self, resp):
        self.resp = resp
        self._text = None
        self._json = None

    @property
    def constent(self):
        return self.resp.data

    @property
    def text(self):
        if self._text is None:
            # TODO: detect html encoding
            self._text = self.resp.data.decode('utf-8')
        return self._text

    def json(self):
        if self._json is None:
            self._json = jsonlib.loads(self.text)
        return self._json


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

    Can be used as mixin too.
    >>> class MyAddon(Site, Addon):
    ...    def __init__(self):
    ...        super(MyAddon, self).__init__(base='URL')
    """

    #: Default value. True if SSL should be verified
    VERIFY_SSL = True
    #: default User-Agent
    UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.30 Safari/537.36'

    def __init__(self, *args, **kwargs):
        #: Base site URL.
        self.base = kwargs.pop('base', None)
        #: Requests session.
        self._sess = None
        #: Path to cookie file or None.
        self.cookiefile = kwargs.pop('cookiefile', None)
        #: True if SSL should be verified
        self.verify_ssl = self.VERIFY_SSL
        #: User-Agent.
        self.ua = self.UA
        #: Option to use urllib3 instead requests.
        self.use_urllib3 = False
        # --- call next contructors if Site is used as a mixin ---
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

    def _request(self, meth, url, params=None, data=None, json=None, headers=None, cookies=None,
                 verify_ssl=None, worker=None):
        """Realize a network request."""

        def set_header(name, value):
            """Set default header, set only if not exist."""
            key = name.lower()
            if key not in header_keys:
                header_keys.add(key)
                headers[name] = value

        # xbmc.log('PLAYER.PL: getRequests(%r, data=%r, headers=%r, params=%r)'
        #          % (url, data, headers, params), xbmc.LOGWARNING)
        if verify_ssl is None:
            verify_ssl = self.verify_ssl
        if worker is None and self.use_urllib3:
            worker = 'urllib3'
        if isinstance(params, Mapping):
            url, params = encode_url(url, params=params), None

        headers = dict(headers) if headers else {}
        header_keys = {name.lower() for name in headers}
        if json is not None:
            set_header('Content-Type', 'application/json')
            set_header('Accept', 'application/json')
        set_header('Accept', '*/*')
        set_header('User-Agent', self.ua)
        if worker == 'urllib3':
            pool_kwargs = {}
            if verify_ssl is False:
                pool_kwargs['cert_reqs'] = 'CERT_NONE'
            elif verify_ssl is True:
                pool_kwargs['ca_certs'] = where()
            http = urllib3.PoolManager(**pool_kwargs)
            if json is not None:
                data = jsonlib.dumps(data).encode('utf-8')
            elif isinstance(data, Mapping):
                data = encode_params(data)
                set_header('Conttent-Type', 'application/x-www-form-urlencoded')
            elif data is not None and not isinstance(data, bytes):
                data = data.encode('utf-8')
            resp = http.request(meth, url, headers=headers, body=data)
            resp = UL3Response(resp)
        else:
            log('req(%s, %r, params=%r, data=%r, json=%r, headers=%r, cookies=%r)' % (meth, url, params, data, json, headers, cookies))  # XXX
            resp = self.sess.request(meth, url, params=params, data=data, json=json,
                                     headers=headers, cookies=cookies, verify=verify_ssl)
        return resp

    def request(self, meth, url, **kwargs):
        """Make a network request. If SSLError try to call self.ssl_dialog()."""
        try:
            return self._request(meth, url, **kwargs)
        except SSLError:
            # requests SSLError
            ssl_dialog = getattr(self, 'ssl_dialog', None)
            if ssl_dialog is None:
                raise
            ssl_dialog()
        except MaxRetryError as exc:
            if not isinstance(exc.reason, SSLError3):
                raise
            # urllib3 SSLError
            ssl_dialog = getattr(self, 'ssl_dialog', None)
            if ssl_dialog is None:
                raise
            ssl_dialog()
        return self._request(meth, url, **kwargs)

    def get(self, url, **kwargs):
        """GET request. Keywoard arguments line in _request()."""
        return self.request('GET', url, **kwargs)

    def post(self, url, **kwargs):
        """POST request. Keywoard arguments line in _request()."""
        return self.request('POST', url, **kwargs)

    def jget(self, url, **kwargs):
        """GET request returns JSON. Keyword arguments line in _request()."""
        return self.get(url, **kwargs).json()

    def jpost(self, url, **kwargs):
        """POST request returns JSON. Keyword arguments line in _request()."""
        # return self.post(url, **kwargs).json()
        log('jpost(%r, %r)' % (url, kwargs))  # XXX
        resp = self.post(url, **kwargs)
        with open('/tmp/z', 'wb') as f:
            f.write(resp.content)
        return resp.json()


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
