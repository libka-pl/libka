# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals, print_function
from future.utils import PY2, python_2_unicode_compatible
if PY2:
    from builtins import *  # dirty hack
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
from kodipl.kodi import version_info as kodi_ver
from kodipl.format import safefmt
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

    def __repr__(self):
        return 'Addon(%r, %r)' % (self.id, str(self.req.url))

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
                    handler = getattr(self, self.ROOT_ENTRY, None)
                else:
                    handler = root
        if handler is None:
            if missing is None:
                raise ValueError('Missing endpoint for %s (req: %s)' % (path, self.req.url))
            handler = missing
        # get pointed method specifiactaion
        spec = getfullargspec(handler)
        assert spec.args
        assert spec.args[0] == 'self'
        assert ismethod(handler)
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


@python_2_unicode_compatible
class Plugin(Addon):
    """
    Abstract KodiPL Addon. Plugin is kind of Addon.
    """


@python_2_unicode_compatible
class ListItem(object):
    """
    Tiny xbmcgui.ListItem wrapper to keep URL and is_folder flag.
    """

    def __init__(self, title, url=None, folder=None):
        if isinstance(title, xbmcgui.ListItem):
            self._kodipl_item = title
        else:
            self._kodipl_item = xbmcgui.ListItem(title)
        self._kodipl_url = url
        self._kodipl_folder = folder

    def __repr__(self):
        return 'ListItem(%r)' % self._kodipl_item

    def __getattr__(self, key):
        return getattr(self._kodipl_item, key)

    @property
    def mode(self):
        return

    @mode.setter
    def mode(self, value):
        playable = value in ('play', 'playable')
        folder = value in ('folder', 'menu')
        self.setProperty('isPlayable', 'true' if playable else 'false')
        self.setIsFolder(folder)
        self._kodipl_folder = folder


@python_2_unicode_compatible
class AddonDirectory(object):
    """
    Thiny wrapper for plugin directory list.

    Parameters
    ----------
    addon : Addon
        Current addon instance.
    view : str
        Directory view, see ...
    type : str
        Contnent type (video, music, pictures, game). Default is directory default (video).
    image : str
        Link to image or relative path to addon image.
    format : str
        Safe f-string title format. Keywoard arguemts are `title` and `info` dict.

    See: xbmcgui.ListItem, xbmcplugin.addDirectoryItem, xbmcplugin.endOfDirectory.
    """

    def __init__(self, addon=None, view=None, type='video', image=None, format=None):
        if addon is None:
            addon = globals()['addon']
        self.addon = addon
        self.view = view
        self.type = type
        self.image = image
        self.format = format

    def end(self, success=True, cacheToDisc=False):
        if self.view is not None:
            xbmcplugin.setContent(self.addon.handle, self.view)
        xbmcplugin.endOfDirectory(self.addon.handle, success, cacheToDisc)

    def new(self, title, endpoint=None, folder=False, playable=False, descr=None, format=None,
            image=None, fanart=None, thumb=None, properties=None, position=None, menu=None,
            type=None, info=None, art=None, season=None, episode=None):
        """
        Create new list item, can be added to current directory list.

        new([title,] endpoint, folder=False, playable=False, descr=None, format=None,
            image=None, fanart=None, thumb=None, properties=None, position=None, menu=None,
            type=None, info=None, art=None, season=None, episode=None)

        Parameters
        ----------
        endpoint : method
            Addon method to call after user select.
        title : str
            Item title, if None endpoint name is taken.
        folder : bool
            True if item is a folder. Default is False.
        playable : bool
            True if item is playable, could be resolved. Default is False.
        descr : str
            Video description. Put into info labels.
        format : str
            Safe f-string title format. Keywoard arguemts are `title` and `info` dict.
        image : str
            Link to image or relative path to addon image.
            Defualt is AddonDirectory image or addon `default_image`.
        fanart : str
            Link to fanart or relative path to addon fanart. Default is addon `fanart`.
        thumb : str
            Link to image thumb or relative path to addon image. Default is `image`.
        properties : dict[str, str]
            Dictionary with xmbcgui.ListItem properties.
        position : str
            Item spesial sort: "top" or "bottom"
        menu : list[(str, str | function)] | AddonContextMenu
            Context menu. AddonContextMenu or list of entries.
            Each entry is tuple of title (str) and handle (str or addon method).
        type : str
            Contnent type (video, music, pictures, game). Default is directory default (video).
        info : dict[str, str]
            Labels info, see xmbcgui.ListItem.setInfo().
        art : dict[str, str]
            Links to art images, see xmbcgui.ListItem.setArt().

        See: https://alwinesch.github.io/group__python__xbmcgui__listitem.html
        """
        title, url = self.addon.mkentry(title, endpoint)
        item = ListItem(title, url=url, folder=folder)
        if folder is True:
            item.setIsFolder(folder)
        # properties
        if properties is not None:
            item.setProperties(properties)
        if playable:
            item.setProperty('isPlayable', 'true')
        if position is not None:
            item.setProperty('SpecialSort', position)
        # menu
        if menu is not None:
            if not isinstance(menu, AddonContextMenu):
                menu = AddonContextMenu(menu, addon=self.addon)
            item.addContextMenuItems(menu)
        # info
        if type is None:
            type = 'video' if self.type is None else self.type
        info = {} if info is None else dict(info)
        info.setdefault('title', title)
        if descr is not None:
            info['plot'] = descr
            info.setdefault('plotoutline', descr)
            info.setdefault('tagline', descr)
        if season is not None:
            info['season'] = season
        if episode is not None:
            info['episode'] = episode
        item.setInfo(type, info or {})
        # art / images
        art = {} if art is None else dict(art)
        if fanart is not None:
            art['fanart'] = fanart
        if thumb is not None:
            art['thumb'] = fanart
        if image is None:
            image = self.image
        if image is None:
            image = getattr(self.addon, 'default_image', None)
        if image is not None:
            art.setdefault('thumb', image)
            art.setdefault('poster', image)
        landscape = art.get('landscape', image)
        if landscape is not None:
            art.setdefault('banner', landscape)
        def_fanart = getattr(self.addon, 'fanart', None)
        if def_fanart is not None:
            art.setdefault('fanart', def_fanart)
        art = {k: 'https:' + v if v and v.startswith('//') else v for k, v in art.items()}
        item.setArt(art)
        # serial
        if season is not None:
            if not isinstance(season, str) and isinstance(season, Sequence):
                item.addSeason(*season[:2])
            else:
                item.addSeason(season)
        # title tuning
        if format is None:
            format = self.format
        if format is not None:
            item.setLabel(safefmt(format, title=title, **info))
        return item

    def add(self, item, endpoint=None, folder=None):
        ifolder = False
        if isinstance(item, ListItem):
            # our list item, revocer utl and folder flag
            item, url, ifolder = item._kodipl_item, item._kodipl_url, item._kodipl_folder
            if endpoint is not None:
                _, url = self.addon.mkentry(item.getLabel(), endpoint)
        elif isinstance(item, xbmcgui.ListItem):
            # pure kodi list item, create url from endpoint
            _, url = self.addon.mkentry(item.getLabel(), endpoint)
            if kodi_ver >= (20,):
                ifolder = item.isFolder()
        else:
            # fallback, use "item" as title and create url from endpoint
            title, url = self.addon.mkentry(item, endpoint)
            item = xbmcgui.ListItem(title)
        if folder is None:
            folder = ifolder
        xbmcplugin.addDirectoryItem(handle=self.addon.handle, url=url, listitem=item, isFolder=folder)
        return item

    def item(self, *args, **kwargs):
        """
        Add folder to current directory list.
        folder([title,] endpoint)

        Parameters
        ----------
        endpoint : method
            Addon method to call after user select.
        title : str
            Item title, if None endpoint name is taken.

        For more arguments see AddonDirectory.new().
        """
        item = self.new(*args, **kwargs)
        self.add(item)
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

        For more arguments see AddonDirectory.new().
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

        For more arguments see AddonDirectory.new().
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
                if not isinstance(item, str) and isinstance(item, Sequence):
                    # tuple: (title, handle) or (handle,)
                    self.add(*item[:2])
                else:
                    # just directly: handle
                    self.add(item)

    def add(self, title, endpoint=None):
        self.append(self.addon.mkentry(title, endpoint))
