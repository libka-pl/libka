# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals, print_function
from future.utils import PY2, python_2_unicode_compatible
if PY2:
    from builtins import *  # dirty hack, force py2 to be like py3
import sys
import re
from contextlib import contextmanager
from collections import namedtuple
from collections.abc import Sequence
# from functools import wraps
from inspect import ismethod
# from future.utils import text_type, binary_type
from kodipl.py2n3 import inspect  # monkey-patching
from inspect import getfullargspec
from kodipl.py2n3 import get_method_self
from kodipl.utils import parse_url, encode_url
from kodipl.utils import get_attr
from kodipl.settings import Settings
from kodipl.logs import flog
from kodipl.resources import Resources
from kodipl.folder import AddonDirectory
from kodi_six import xbmc
from kodi_six.xbmcaddon import Addon as XbmcAddon


#: Call descrtiption
#: - method - function or method to call
#: - params - simple query (keywoard) arguments, passed directly in URL
#: - args - raw positional arguments, pickled
#: - kwargs - raw keywoard arguments, pickled
Call = namedtuple('Call', 'method params args kwargs')
Call.__new__.__defaults__ = (None, None)

EndpointEntry = namedtuple('EndpointEntry', 'path title')

Route = namedtuple('Route', 'method entry')


class MISSING:
    """Internal. Type to fit as missing."""


def entry(method=None, path=None, title=None):
    """Decorator for addon URL entry."""
    entry = EndpointEntry(path=path, title=title)

    def decorator(method):
        def make_call(**kwargs):
            return Call(method, kwargs)

        if path is not None:
            if ismethod(method):
                obj = get_method_self(method)
                obj._routes.append(Route(method, entry))
        method._kodipl_endpoint = entry
        method.call = make_call
        return method

    if method is not None:
        return decorator(method)
    return decorator


def call(method, **params):
    """Addon action with arguments. Syntax suger. """
    return Call(method, params)


def raw_call(method, *args, **kwargs):
    """Addon action with raw arguments. Syntax suger. Don't use it."""
    return Call(method, (), args, kwargs)


@python_2_unicode_compatible
class Request(object):
    """
    Addon call request.
    """

    def __init__(self, url, encoded_keys=None):
        self.url = parse_url(url, encoded_keys)
        self.params = self.url.args
        # flog('XXXXX: argv: {sys.argv}')
        # flog('XXXXX: url:  {list(self.url)}')
        # flog('XXXXX: req={self.url}, link={self.url.link!r}, params={self.params!r}')


@python_2_unicode_compatible
class Addon(object):
    """
    Abstract KodiPL Addon.
    """

    #: Only method with @entry is allowed if True, else any method
    SAFE_CALL = False
    #: Default root (home) entry method name or list of methods (find first).
    ROOT_ENTRY = ('home', 'root')

    _RE_TITLE_COLOR = re.compile(r'\[COLOR +:(\w+)\]')

    def __init__(self, argv=None):
        if argv is None:
            argv = sys.argv
        if len(argv) < 3 or (argv[1] != '-1' and not argv[1].isdigit()) or (argv[2] and argv[2][:1] != '?'):
            raise TypeError('Incorrect addon args: %s' % argv)
        # Addon handle (integer).
        self.handle = int(argv[1])
        # Names for paramteres to encode raw Python data, don't use it.
        self.encoded_keys = None
        # Kodi request to plugin://...
        self.req = Request(argv[0] + argv[2], self.encoded_keys)
        # Addon ID (unique name)
        self.id = self.req.url.host
        # XMBC (Kodi) Addon
        self.xbmc_addon = XbmcAddon(id=self.id)
        #: Addon settings.
        self.settings = Settings(self)
        #: Defined routes.
        self._routes = []
        #: User defined colors used in "[COLOR :NAME]...[/COLOR]"
        self.colors = {'gray': 'gray'}
        #: Resources
        self.resources = Resources(self)

    def __repr__(self):
        return 'Addon(%r, %r)' % (self.id, str(self.req.url))

    def info(self, key):
        """Get XBMC addon info (like "path", "version"...)."""
        return self.xbmc_addon.getAddonInfo(key)

    @property
    def media(self):
        """Media resources."""
        return self.resources.media

    def mkentry(self, title, endpoint=None):
        """Helper. Returns (title, url) for given endpoint."""
        flog('mkentry({title!r}, {endpoint!r})')
        if endpoint is None:
            if isinstance(title, str):
                # folder(title, endpoint=title)
                endpoint = title
            else:
                # folder(endpoint, title=None)
                title, endpoint = None, title
        params = {}
        if isinstance(endpoint, Call):
            endpoint, params = endpoint.method, endpoint.params
        if ismethod(endpoint):
            obj = get_method_self(endpoint)
            assert obj == self
        # elif callable(endpoint):
        #     raise TypeError('mkentry endpoint must be Addon method or str not %r' % type(endpoint))
        if title is None:
            if callable(endpoint):
                title = endpoint.__name__
                entry = getattr(endpoint, '_kodipl_endpoint', None)
                if entry is not None:
                    if entry.title is not None:
                        title = entry.title
        url = self.mkurl(endpoint, **params)
        if title is not None:
            if not isinstance(title, str):
                flog('WARNING!!! Incorrect title {title!r}')
            title = self.translate_title(title)
        return title, url

    def mkurl(self, endpoint, **kwargs):
        """
        Create plugin URL to given name/method with arguments.
        """
        path = None
        # if ismethod(endpoint):
        if callable(endpoint):
            entry = getattr(endpoint, '_kodipl_endpoint', None)
            if entry is not None:
                if path is not None:
                    path = entry.path
            elif self.SAFE_CALL:
                raise ValueError('URL to function %r is FORBIDEN, missing @entry' % endpoint)
            # endpoint = qualname(endpoint)
            endpoint = endpoint.__name__
        if path is None:
            path = '/%s' % endpoint
        # if path.startswith('/'):
        #     path = path[:1]
        return encode_url(self.req.url.link, path=path, params=kwargs)

    url_for = mkurl

    def dispatcher(self, root=None, missing=None):
        """
        Dispatcher. Call pointed method with request arguments.
        """
        path = self.req.url.path
        params = self.req.params
        # find handler pointed by URL path
        handler = None
        for route in self._routes:
            if route.entry.path == path:
                handler = route.method
                break
        if handler is None:
            if path.startswith('/'):
                path = path[1:]
            if path:
                handler = get_attr(self, path, sep='/')
            else:
                if root is None:
                    if self.ROOT_ENTRY:
                        if isinstance(self.ROOT_ENTRY, str):
                            handler = getattr(self, self.ROOT_ENTRY, None)
                        elif isinstance(self.ROOT_ENTRY, Sequence):
                            for name in self.ROOT_ENTRY:
                                handler = getattr(self, name, None)
                                if handler is not None:
                                    break
                else:
                    handler = root
        if handler is None:
            if missing is None:
                raise ValueError('Missing endpoint for %s (req: %s)' % (path, self.req.url))
            handler = missing
        # get pointed method specification
        spec = getfullargspec(handler)
        assert spec.args
        assert spec.args[0] == 'self'
        assert ismethod(handler)
        # prepare arguments for pointed method
        args, kwargs = [], {}
        if spec.args and spec.args[0] == 'self':
            pass
            # if not PY3:
            #     # fix unbound method in Py2
            #     args.append(self)
        if spec.defaults:
            # first fill default method arguments
            for k, v in zip(reversed(spec.args), reversed(spec.defaults)):
                kwargs[k] = v
        if spec.varkw:
            # the method has **kwargs, put all request arguments
            kwargs.update(params)
        else:
            # fill arguments only if method has them
            for k in spec.args:
                if k in params:
                    kwargs[k] = params[k]
        # call pointed method
        return handler(*args, **kwargs)

    @contextmanager
    def directory(self, safe=False, **kwargs):
        kd = AddonDirectory(self, **kwargs)
        try:
            yield kd
        except Exception:
            kd.end(False)
            if not safe:
                raise
        else:
            kd.end(True)
        finally:
            pass

    def get_color(self, name):
        return self.colors.get(name, 'gray')

    def translate_title(self, text):
        def get_color(m):
            return '[COLOR %s]' % self.get_color(m.group(1))

        text = self._RE_TITLE_COLOR.sub(get_color, text)
        return text

    @entry(path='/sets')  # TODO: remove decorator
    def openSettings(self):
        """Deprecated. Use Addon.settings()."""
        self.xbmc_addon.openSettings()

    def builtin(self, command):
        """Execute Kodi build-in command."""
        xbmc.executebuiltin(command)

    def refresh(self, endpoint=None):
        """Execute Kodi build-in command."""
        xbmc.executebuiltin('Container.Refresh(%s)' % (endpoint or ''))

    def get_default_art(self, name):
        """Returns path to default art."""


@python_2_unicode_compatible
class Plugin(Addon):
    """
    Abstract KodiPL Addon. Plugin is kind of Addon.
    """
