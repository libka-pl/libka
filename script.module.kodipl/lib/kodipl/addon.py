# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals, print_function
from future.utils import PY2, python_2_unicode_compatible
if PY2:
    from builtins import *  # dirty hack
import sys
import re
from contextlib import contextmanager
from collections import namedtuple
from collections.abc import Sequence, Mapping
# from functools import wraps
from inspect import ismethod
# from future.utils import text_type, binary_type
from kodipl.py2n3 import inspect  # monkey-patching
from inspect import getfullargspec
from kodipl.py2n3 import get_method_self
from kodipl.utils import parse_url, encode_url
from kodipl.utils import get_attr
from kodipl.utils import setdefaultx
from kodipl.settings import Settings
from kodipl.kodi import version_info as kodi_ver
from kodipl.format import safefmt
from kodipl.logs import log, flog
from kodipl.resources import Resources
from kodipl.kodi import K18
from kodi_six import xbmc
from kodi_six import xbmcgui
from kodi_six import xbmcplugin
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


@python_2_unicode_compatible
class ListItem(object):
    """
    Tiny xbmcgui.ListItem wrapper to keep URL and is_folder flag.
    """

    def __init__(self, name, url=None, folder=None, type='video'):
        if isinstance(name, xbmcgui.ListItem):
            self._kodipl_item = name
        else:
            self._kodipl_item = xbmcgui.ListItem(name)
        self._kodipl_url = url
        self._kodipl_folder = folder
        self.type = type
        self._info = {}
        self._kodipl_item.setInfo(self.type, self._info)

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

    @property
    def label(self):
        return self.getLabel()

    @label.setter
    def label(self, label):
        self.setLabel(label)

    @property
    def info(self):
        return self._info

    def get_info(self, info):
        """Get single info value or None if not exists."""
        return self._info.get(info)

    def set_info(self, info, value=None):
        """
        Set info value or info dict.

        set_info(name, value)
        set_info({'name': 'value', ...})
        """
        if isinstance(info, Mapping):
            if value is not None:
                raise TypeError('Usage: set_info(name, value) or set_info(dict)')
            self._info.update(info)
        else:
            self._info[info] = value
        self._kodipl_item.setInfo(self.type, self._info)

    def setInfo(self, type, infoLabels):
        """See Kodi ListItem.setInfo()."""
        if self.type is None:
            self.type = type
        if type != self.type:
            raise ValueError('Type mismatch %r != %r' % (self.type, type))
        self._info.update(infoLabels)
        self._kodipl_item.setInfo(self.type, self._info)

    @property
    def title(self):
        return self._info.get('title')

    @title.setter
    def title(self, title):
        self._info['title'] = title
        self._kodipl_item.setInfo(self.type, self._info)


Sort = namedtuple('Sort', 'method labelMask label2Mask')
Sort.__new__.__defaults__ = (None, None)
Sort.auto = 'auto'

Item = namedtuple('Item', 'item endpoint folder')


@python_2_unicode_compatible
class AddonDirectory(object):
    """
    Tiny wrapper for plugin directory list.

    Parameters
    ----------
    addon : Addon
        Current addon instance.
    view : str
        Directory view, see ...
    sort : str or bool
        Default list sort. See bellow.
    type : str
        Content type (video, music, pictures, game). Default is directory default (video).
    image : str
        Link to image or relative path to addon image.
    fanart : str
        Link to fanart image or relative path to addon image.
    format : str
        Safe f-string title format. Keyword arguments are `title` and `info` dict.

    Sort
    ----
    None means default behavior. If add_sort() is used nothing happens. If no any sort
    function is called it means "auto".

    "auto" means auto sorting. All added items are scanned for detect witch info data
    is available. Than corresponding sort method are added to directory, including "unsorted".

    Empty string means "unsorted".

    False means do not sort at all. Even seep any add_sort() calls.

    True means... [I'm not sure yet ;-P]

    Another str is spited by semicolon (;) to separate sort command.

    Single sort command is Kodi case insensitive name (without "SORT_METHOD_"). Then "title" -> SORT_METHOD_TITLE.
    After bar (|) `lebel2Mask` can be applied. 

    Note. If sort=None and `label2` is used, than item info `code` is overwritten, and mask is forced to "%P".

    ### Example

    Three sort methods:
    - SORT_METHOD_UNSORTED with "%Y, %D" mask
    - SORT_METHOD_YEAR
    - SORT_METHOD_DURATION
    >>> sort='|%Y, %D; year; duration'

    Single method with show genre (skin hide sort button):
    >>> sort='|%G'

    See: xbmcgui.ListItem, xbmcplugin.addDirectoryItem, xbmcplugin.endOfDirectory.
    """

    def __init__(self, addon=None, view=None, sort=None, type='video', image=None, fanart=None, format=None):
        if addon is None:
            addon = globals()['addon']
        self.addon = addon
        self.item_list = []
        self.view = view
        self.type = type
        self.image = image
        self.fanart = fanart
        self.format = format
        self._label2_used = False
        self.sort_list = []
        self._initial_sort = sort
        if isinstance(sort, str):
            sort = [s.strip() for s in sort.split(';')]
        if sort is not None and not isinstance(sort, bool):
            for s in sort:
                self._add_sort(s)

    def end(self, success=True, cacheToDisc=False):
        def add_sort_method(sortMethod, labelMask, label2Mask):
            if K18:
                xbmcplugin.addSortMethod(self.addon.handle, sortMethod=sortMethod, label2Mask=label2Mask)
            else:
                xbmcplugin.addSortMethod(self.addon.handle, sortMethod=sortMethod,
                                         labelMask=labelMask, label2Mask=label2Mask)

        # set view
        if self.view is not None:
            xbmcplugin.setContent(self.addon.handle, self.view)
        # force label2
        if self._initial_sort is None and not self.sort_list and self._label2_used:
            self.sort_list = [Sort('', label2Mask='%P')]
            for it in self.item_list:
                if isinstance(it.item, ListItem):
                    it.item.set_info('code', it.item.getLabel2())
        # add all items
        for it in self.item_list:
            self._add(*it)
        # add sort methods
        if self._initial_sort is True:
            pass  # I'm not sure – ignore at the moment
        if self._initial_sort is False:
            pass  # skip sorting at all
        else:
            if self._initial_sort is None and not self.sort_list:
                if not self._label2_used:
                    self.sort_list = [Sort('auto')]
            for sort in self.sort_list:
                if sort.method == '':
                    method = xbmcplugin.SORT_METHOD_UNSORTED
                    add_sort_method(sortMethod=method, labelMask=sort.labelMask, label2Mask=sort.label2Mask)
                elif sort.method == 'auto':
                    for method in self._find_auto_sort():
                        add_sort_method(sortMethod=method, labelMask=sort.labelMask, label2Mask=sort.label2Mask)
                else:
                    add_sort_method(sortMethod=sort.method, labelMask=sort.labelMask, label2Mask=sort.label2Mask)
        # close directory
        xbmcplugin.endOfDirectory(self.addon.handle, success, cacheToDisc)

    def _find_auto_sort(self):
        """Helper. Sort method auto generator."""
        try:
            SORT_METHOD_YEAR = xbmcplugin.SORT_METHOD_YEAR
        except AttributeError:
            SORT_METHOD_YEAR = xbmcplugin.SORT_METHOD_VIDEO_YEAR
        yield xbmcplugin.SORT_METHOD_UNSORTED
        for method, keys in {
                # Kodi-sort-method:              (list-of-info-keys)
                SORT_METHOD_YEAR:                ('year', 'aired'),
                xbmcplugin.SORT_METHOD_DURATION: ('duration',),
                xbmcplugin.SORT_METHOD_GENRE:    ('genre',),
        }.items():
            if any(it.item.get_info(key)
                   for it in self.item_list if isinstance(it.item, ListItem)
                   for key in keys):
                yield method

    def _add_sort(self, data):
        """Helper. Add sort method, `data` is str, dict or tuple."""
        if data == 'auto':                  # auto_sort()
            self.add_sort(data)
        elif isinstance(data, Sort):        # add_sort(Sort(...))
            self.add_sort(data)
        elif isinstance(data, int):         # add_sort(xbmcplugin.SORT_METHOD_method)
            self.add_sort(data)
        elif isinstance(data, str):         # add_sort("method") or add_sort("method|label2Mask")
            self.add_sort(data)
        elif isinstance(data, Mapping):     # add_sort(method=..., labelMask=..., label2Mask=...)
            self.add_sort(**data)
        elif isinstance(data, Sequence):    # add_sort(method, labelMask, label2Mask)
            self.add_sort(*data)

    def add_sort(self, method, labelMask=None, label2Mask=None):
        """Add single sort method. See AddonDirectory `sort` description."""
        if isinstance(method, Sort):
            self.sort_list.append(method)
        else:
            if isinstance(method, str):
                method, sep, mask = method.partition('|')
                if label2Mask is None and sep:
                    label2Mask = mask
                if method in ('', 'auto'):
                    # to process later
                    self.sort_list.append(Sort(method, labelMask, label2Mask))
                    return
                elif method == 'year' and not hasattr(xbmcplugin, 'SORT_METHOD_YEAR'):
                    method = 'video_year'
                method = getattr(xbmcplugin, 'SORT_METHOD_%s' % method.replace(' ', '_').upper())
            self.sort_list.append(Sort(method, labelMask, label2Mask))

    # @trace
    def new(self, title, endpoint=None, folder=False, playable=False, descr=None, format=None,
            image=None, fanart=None, thumb=None, properties=None, position=None, menu=None,
            type=None, info=None, art=None, season=None, episode=None, label2=None):
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
        season : int
            Season number or None if not a season nor an episode.
        episode : int
            Episode number or None if not an episode.

        See: https://alwinesch.github.io/group__python__xbmcgui__listitem.html
        """
        log.error('>>> ENTER...')
        title, url = self.addon.mkentry(title, endpoint)
        item = ListItem(title, url=url, folder=folder)
        if folder is True:
            item.setIsFolder(folder)
        if label2 is not None:
            item.setLabel2(label2)
            self._label2_used = True
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
        setdefaultx(art, 'icon', image, self.image)
        setdefaultx(art, 'fanart', fanart, self.fanart)
        setdefaultx(art, 'thumb', thumb)
        if not (set(art) - {'fanart', 'thumb'}):
            # missing image, take defaults
            for iname in ('icon', 'landscape', 'poster', 'banner', 'clearlogo', 'keyart'):
                image = self.addon.media.image('default/%s' % iname)
                if image is not None:
                    art.setdefault(iname, image)
            # setdefaultx(art, 'icon', addon_icon)
        art = {k: 'https:' + v if isinstance(v, str) and v.startswith('//') else str(v) for k, v in art.items()}
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
        log.error('>>> EXIT...')
        return item

    def add(self, item, endpoint=None, folder=None):
        self.item_list.append(Item(item, endpoint, folder))
        return item

    def _add(self, item, endpoint=None, folder=None):
        """Helper. Add item to xbmcplugin directory."""
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

    def parse(self, *args, **kwargs):
        """
        Custom parse. Call Addon.parse_list_item(kd, *args, **kwargs) if exists.
        """
        handler = getattr(self.addon, 'parse_list_item', None)
        if handler is not None:
            return handler(self, *args, **kwargs)

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
