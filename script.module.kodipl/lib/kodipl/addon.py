# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals, print_function
from future.utils import PY2, python_2_unicode_compatible
if PY2:
    from builtins import *  # dirty hack
import sys
import re
from contextlib import contextmanager
from collections import namedtuple
# from functools import wraps
from inspect import ismethod
from future.utils import text_type, binary_type
from kodipl.py2n3 import inspect  # monkey-patching
from inspect import getfullargspec
from kodipl.py2n3 import get_method_self
from kodipl.utils import parse_url, encode_url
from kodipl.utils import get_attr
from kodipl.settings import Settings
from kodipl.logs import log, flog
from kodi_six import xbmcgui
from kodi_six import xbmcplugin
from kodi_six.xbmcaddon import Addon as XbmcAddon


Call = namedtuple('Call', 'method args')

EndpointEntry = namedtuple('EndpointEntry', 'path title')

Route = namedtuple('Route', 'method entry')


class MISSING:
    """Internal. Type to fit as missing."""


def entry(method=None, path=None, title=None):
    """Decorator for addon URL entry."""
    entry = EndpointEntry(path=path, title=title)

    def decorator(method):
        def make_call(**kwargs):
            return Call(method, ((), kwargs))

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


def fullcall(method, *args, **kwargs):
    """Addon action with arguments. Syntax suger. Don't use `args`. """
    return Call(method, (args, kwargs))


def call(method, **kwargs):
    """Addon action with arguments. Syntax suger. """
    return Call(method, ((), kwargs))


@python_2_unicode_compatible
class Request(object):
    """
    Addon call request.
    """

    def __init__(self, url, encoded_keys=None):
        self.url = parse_url(url, encoded_keys)
        self.params = self.url.args
        flog('XXXXX: argv: {sys.argv}')
        flog('XXXXX: url:  {list(self.url)}')
        flog('XXXXX: req={self.url}, link={self.url.link!r}, params={self.params!r}')


@python_2_unicode_compatible
class Addon(object):
    """
    Abstract KodiPL Addon.
    """

    #: Only method with @entry is allowed if True, else any method
    SAFE_CALL = False
    #: Default root (home) entry method name.
    ROOT_ENTRY = "root"

    _RE_TITLE_COLOR = re.compile(r'\[COLOR +:(\d+)\]')

    def __init__(self, argv=None):
        if argv is None:
            argv = sys.argv
        if len(argv) < 3 or not argv[1].isdigit() or (argv[2] and argv[2][:1] != '?'):
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
        self.colors = {}

    def __repr__(self):
        return 'Addon(%r, %r)' % (self.id, str(self.req.url))

    def mkentry(self, title, endpoint=None):
        """Helper. Returns (title, url) for given endpoint."""
        if endpoint is None:
            # folder(endpoint, title=None)
            title, endpoint = None, title
        params = {}
        if isinstance(endpoint, Call):
            endpoint, (_, params) = endpoint.method, endpoint.args
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

    def dispatcher(self, root=None, missing=None):
        """
        Dispatcher. Call pointed method with request arguments.
        """
        path = self.req.url.path
        params = self.req.params
        # find handle pointed by URL path
        handle = None
        for route in self._routes:
            if route.entry.path == path:
                handle = route.method
                break
        if handle is None:
            if path.startswith('/'):
                path = path[1:]
            if path:
                handle = get_attr(self, path, sep='/')
            else:
                if root is None:
                    handle = getattr(self, self.ROOT_ENTRY, None)
                else:
                    handle = root
        if handle is None:
            if missing is None:
                raise ValueError('Missing endpoint for %s (req: %s)' % (path, self.req.url))
            handle = missing
        # get pointed method specifiactaion
        spec = getfullargspec(handle)
        assert spec.args
        assert spec.args[0] == 'self'
        assert ismethod(handle)
        # prepare arguments for pointed method
        args, kwargs = [], {}
        if spec.args and spec.args[0] == 'self':
            pass
            # if not PY3:
            #     # fix unbound mathod in Py2
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
        return handle(*args, **kwargs)

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
        return self.colors.get(name, 'black')

    def translate_title(self, text):
        def get_color(m):
            return '[COLOR %s]' % self.get_color(m.group(1))

        text = self._RE_TITLE_COLOR.sub(get_color, text)
        return text

    @entry(path='/sets')  # TODO: remove decorator
    def openSettings(self):
        """Deprecated. Use Addon.settings()."""
        self.xbmc_addon.openSettings()


@python_2_unicode_compatible
class Plugin(Addon):
    """
    Abstract KodiPL Addon. Plugin is kind of Addon.
    """


@python_2_unicode_compatible
class AddonDirectory(object):
    """
    Thiny wrapper for plugin directory list.

    See: xbmcgui.ListItem, xbmcplugin.addDirectoryItem, xbmcplugin.endOfDirectory.
    """

    def __init__(self, addon=None, view=None):
        if addon is None:
            addon = globals()['addon']
        self.addon = addon
        self.view = view

    def end(self, success=True, cacheToDisc=False):
        if self.view is not None:
            xbmcplugin.setContent(self.addon.handle, self.view)
        xbmcplugin.endOfDirectory(self.addon.handle, success, cacheToDisc)

    def item(self, title, endpoint=None, folder=False, playable=False, image=None, properties=None,
             menu=None):
        """
        Add folder to current directory list.
        folder([title,] endpoint)

        Parameters
        ----------
        endpoint : method
            Addon method to call after user select.
        title : str
            Item title, if None endpoint name is taken.
        """
        title, url = self.addon.mkentry(title, endpoint)
        item = xbmcgui.ListItem(title)
        if properties is not None:
            item.setProperties(properties)
        if playable:
            item.setProperty('isPlayable', 'true')
        if menu is not None:
            if not isinstance(menu, AddonContextMenu):
                menu = AddonContextMenu(menu, addon=self.addon)
                log('############ %r' % menu)  # XXX
            item.addContextMenuItems(menu)
        xbmcplugin.addDirectoryItem(handle=self.addon.handle, url=url, listitem=item, isFolder=folder)
        return item

    def folder(self, title, endpoint=None, **kwargs):
        """
        Add folder to current directory list.
        folder([title,] endpoint)

        Parameters
        ----------
        endpoint : method
            Addon method to call after user select.
        title : str
            Item title, if None endpoint name is taken.

        For more arguments see AddonDirectory.item().
        """
        return self.item(title, endpoint, folder=True, **kwargs)

    #: Shortcut name
    menu = folder

    def play(self, title, endpoint=None, **kwargs):
        """
        Add playable item to current directory list.
        play([title,] endpoint)

        Parameters
        ----------
        endpoint : method
            Addon method to call after user select.
        title : str
            Item title, if None endpoint name is taken.

        For more arguments see AddonDirectory.item().
        """
        return self.item(title, endpoint, playable=True, **kwargs)

    # @contextmanager
    # def context_menu(self, safe=False, **kwargs):
    #     km = AddonContextMenu(self.addon, **kwargs)
    #     try:
    #         yield km
    #     except Exception:
    #         if not safe:
    #             raise
    #     else:
    #         pass
    #     finally:
    #         pass


@python_2_unicode_compatible
class AddonContextMenu(list):
    """
    Thiny wrapper for plugin list item context menu.

    See: xbmcgui.ListItem.
    """

    def __init__(self, menu=None, addon=None):
        if addon is None:
            addon = globals()['addon']
        self.addon = addon
        if menu is not None:
            for item in menu:
                self.add(*item[:2])

    def add(self, title, endpoint=None):
        self.append(self.addon.mkentry(title, endpoint))
