from typing import Optional, Union, Any, Tuple, List, Dict, Callable, TYPE_CHECKING
import re
from collections import namedtuple
from collections.abc import Sequence, Mapping
from contextlib import contextmanager
from inspect import signature
from datetime import datetime, date
from .tools import setdefaultx
from .kodi import version_info as kodi_ver
from .format import safefmt
from .types import Literal
from .path import Path
from .url import URL
from .logs import log
import xbmcgui
import xbmcplugin
from xbmc import Actor
# from xbmc import VideoStreamDetail

if TYPE_CHECKING:
    from xbmc import InfoTagVideo


Date = [date, datetime]


class Cmp:
    """Helper. Object to compare values without TypeError exception."""

    __slots__ = ('value', )

    def __init__(self, value=None):
        self.value = value

    # The sort routines are guaranteed to use __lt__() when making comparisons between two objects.
    def __lt__(self, other):
        """True if self is less-then other."""
        if not self.value:
            return bool(other.value)  # '' < '' or '' < '...'
        if not other.value:
            return False  # '...' < ''
        try:
            return self.value < other.value
        except TypeError:
            return str(self.value) < str(other.value)

    # def __eq__(self, other):
    #     if not self.value and not other.value:
    #         return True
    #     if self.value and other.value:
    #         return str(self.value) == str(other.value)
    #     return False


class ListItem:
    """
    Tiny xbmcgui.ListItem wrapper to keep URL and is_folder flag.
    """

    def __init__(self, name, *, url=None, folder=None, type=None, offscreen=True, sort_key=None, custom=None,
                 addon=None):
        log.info(f'[LI] {name=}')
        if isinstance(name, xbmcgui.ListItem):
            self._libka_item = name
        else:
            self._libka_item = xbmcgui.ListItem(name, offscreen=offscreen)
        self._libka_url = url
        self._libka_folder = folder
        self.type = type
        self._info = {}
        self._props = {}
        self.sort_key = sort_key
        self.custom = custom
        self._menu = None
        self._addon = addon
        if self.type is not None:
            self._libka_item.setInfo(self.type, self._info)

    def __repr__(self):
        return 'ListItem(%r)' % self._libka_item

    def __getattr__(self, key):
        return getattr(self._libka_item, key)

    def __call__(self):
        """Execute item, apply all virtual settings into Kodi ListItem."""
        if self._menu is not None:
            self._libka_item.addContextMenuItems(self._menu)

    @property
    def mode(self):
        return

    @mode.setter
    def mode(self, value):
        playable = value in ('play', 'playable')
        folder = value in ('folder', 'menu')
        self.setProperty('IsPlayable', 'true' if playable else 'false')
        self.setIsFolder(folder)
        self._libka_folder = folder

    @property
    def label(self):
        return self.getLabel()

    @label.setter
    def label(self, label):
        self.setLabel(label)

    @property
    def info(self):
        return self._info

    def get(self, info):
        """Get single info value or another value or None if not exists."""
        if info == 'label':
            return self.getLabel()
        return self._info.get(info)

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
        self._libka_item.setInfo(self.type, self._info)

    def setInfo(self, type, infoLabels):
        """See Kodi ListItem.setInfo()."""
        if self.type is None:
            self.type = type
        if type != self.type:
            raise ValueError('Type mismatch %r != %r' % (self.type, type))
        if self.type is None:
            raise TypeError('setInfo: type is None')
        self._info.update(infoLabels)
        self._libka_item.setInfo(self.type, self._info)

    @property
    def title(self):
        return self._info.get('title')

    @title.setter
    def title(self, title):
        self._info['title'] = title
        self._libka_item.setInfo(self.type, self._info)

    def setProperties(self, values):
        """See Kodi ListItem.setProperties()."""
        self._props.update(values)
        self._libka_item.setProperties(values)

    def setProperty(self, key, value):
        """See Kodi ListItem.setProperty()."""
        self._props[key] = value
        self._libka_item.setProperty(key, value)

    def get_property(self, key):
        """Get set property."""
        return self._props.get(key)

    @property
    def menu(self):
        """Get context menu, create if missing."""
        if self._menu is None:
            self._menu = AddonContextMenu(addon=self._addon)
        return self._menu

    @menu.setter
    def menu(self, menu):
        if not isinstance(menu, AddonContextMenu):
            menu = AddonContextMenu(menu, addon=self._addon)
        self._menu = menu


#: Helper. Sort item.
Sort = namedtuple('Sort', 'method labelMask label2Mask')
Sort.__new__.__defaults__ = (None, None)
Sort.auto = 'auto'

Item = namedtuple('Item', 'item endpoint folder')

#: Resolved xbmcplugin.addDirectoryItems item.
DirectoryItem = namedtuple('DirectoryItem', 'url listitem is_folder')


class AddonDirectory:
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
    style : str or list of str
        Safe f-string title style or list of styles like ['B', 'COLOR red'].
    isort : str or bool
        Internal list sort. See bellow.
    cache : bool
        Cache to disc on directory end.
    update : bool
        Update listing on directory end.
    offscreen : bool
        Default offcreen flag for directory items.

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

    Note. If `sort=None` and `label2` is used, than item info `code` is overwritten, and mask is forced to `"%P"`.

    See all label masks:

    ### label2Mask

    The single sort command can contain `label2Mask` after a bar (|).

    To show year without sorting use `|%Y`.

    ### labelMask

    The single sort command can also contain `labelMask` between bars (|).

    To show tv-show title (as a label) without sorting use `|%Z|`. Could be combined with `label2Mask`: `|%Z:%Y`.


    ### Examples

    Three sort methods:

    - SORT_METHOD_UNSORTED with "%Y, %D" mask
    - SORT_METHOD_YEAR
    - SORT_METHOD_DURATION
    >>> sort='|%Y, %D; year; duration'

    Single method with show genre (skin hide sort button):
    >>> sort='|%G'


    ### Internal sort

    To sort data *before* add to Kodi Directory, `isort` can be used. It should contains
    info key or sequence of info key (tuple, list or string separated by comma).
    If minus (-) is a first character of a key, there reverse order will be used.

    See: xbmcgui.ListItem, xbmcplugin.addDirectoryItem, xbmcplugin.endOfDirectory.
    """

    #: Keywors paramters for `AddonDirectory` item. Will be updated from `AddonDirectory.new()` signature.
    ITEM_KEYS = ('descr', 'label2', 'info', 'art', 'image', 'fanart', 'thumb', 'menu',
                 'style', 'format', 'menu', 'type')

    _RE_ISORT_SPLIT = re.compile(r'[,;]')

    def __init__(self, *, addon=None, view='videos', sort=None, type='video', image=None, fanart=None,
                 format=None, style=None, isort=None, cache=False, update=False, offscreen=True, menu=None):
        if addon is None:
            addon = globals()['addon']
        self.addon = addon
        self.router = self.addon.router
        self.item_list = []
        self.view = view
        self.type = type
        self.image = image
        self.fanart = fanart
        self.format = format
        self.style = style
        self._label_used = False
        self._label2_used = False
        self.sort_list = []
        self._initial_sort = sort
        if isinstance(sort, str):
            sort = [s.strip() for s in sort.split(';')]
        if sort is not None and not isinstance(sort, bool):
            for s in sort:
                self._add_sort(s)
        if isinstance(isort, str):
            self.isort = [s.strip() for s in self._RE_ISORT_SPLIT.split(isort)]
        elif isinstance(isort, Sequence):
            self.isort = list(isort)
        else:
            self.isort = []
        self.cache = cache
        self.update = update
        self.offscreen = offscreen
        self._next_sort_key = None
        if menu is not None and not isinstance(menu, AddonContextMenu):
            menu = AddonContextMenu(menu, addon=self.addon)
        self._menu = menu
        self._next_item_menu = None
        handler = getattr(self.addon, 'on_directory_enter', None)
        if handler is not None:
            handler(self)

    def close(self, success=True):
        def add_sort_method(sortMethod, labelMask, label2Mask):
            xbmcplugin.addSortMethod(self.addon.handle, sortMethod=sortMethod,
                                     labelMask=labelMask, label2Mask=label2Mask)

        # custom exiting
        handler = getattr(self.addon, 'on_directory_exit', None)
        if handler is not None:
            handler(self)
        # set view
        if self.view is not None:
            xbmcplugin.setContent(self.addon.handle, self.view)
        # force label2
        if self._initial_sort is None and not self.sort_list:
            if self._label_used and self._label2_used:
                self.sort_list = [Sort('', labelMask='%L', label2Mask='%P')]
            elif self._label_used:
                self.sort_list = [Sort('', labelMask='%L')]
            elif self._label2_used:
                self.sort_list = [Sort('', label2Mask='%P')]
            else:
                self.sort_list = [Sort('')]
            if self._label2_used:
                for it in self.item_list:
                    if isinstance(it.item, ListItem):
                        it.item.set_info('code', it.item.getLabel2())
        # internal sort
        if self.isort:
            for srt in reversed(self.isort):
                reverse = False
                if srt.startswith('-'):
                    srt = srt[1:]
                    reverse = True
                elif srt.startswith('+'):
                    srt = srt[1:]
                self.item_list.sort(key=lambda it: (Cmp(it.item.get(srt))
                                                    if isinstance(it.item, ListItem)
                                                    else Cmp()),
                                    reverse=reverse)
        # ... always respect "SpecialSort" property, even wth SORT_METHOD_UNSORTED
        spec_sort = {'top': -1, 'bottom': 1}
        self.item_list.sort(key=lambda it: spec_sort.get(((it.item.get_property
                                                          if isinstance(it.item, ListItem)
                                                          else it.item.getProperty)('SpecialSort') or '').lower(), 0))
        # add all items
        xitems = [self._prepare(*it) for it in self.item_list]
        xbmcplugin.addDirectoryItems(self.addon.handle, xitems, len(xitems))
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
        handler = getattr(self.addon, 'on_directory_close', None)
        if handler is not None:
            handler(self)
        xbmcplugin.endOfDirectory(self.addon.handle, succeeded=success,
                                  updateListing=self.update, cacheToDisc=self.cache)

    def sort_items(self, *, key=None, reverse=False):
        """
        Sort items **before** `AddonDirectory.close()`.

        Return a new list containing all items from the iterable in ascending order.

        A custom key function can be supplied to customize the sort order, and the
        reverse flag can be set to request the result in descending order.
        """
        if key is None:
            def key(item):
                return item.label

        self.item_list.sort(key=lambda item: key(item.item), reverse=reverse)

    def _find_auto_sort(self):
        """Helper. Sort method auto generator."""
        try:
            SORT_METHOD_YEAR = xbmcplugin.SORT_METHOD_YEAR
        except AttributeError:
            SORT_METHOD_YEAR = xbmcplugin.SORT_METHOD_VIDEO_YEAR
        # "auto" should not generate SORT_METHOD_UNSORTED, it is easy to get directly.
        # yield xbmcplugin.SORT_METHOD_UNSORTED
        for method, keys in {
                # Kodi-sort-method:              (list-of-info-keys)
                xbmcplugin.SORT_METHOD_TITLE:    ('title',),
                SORT_METHOD_YEAR:                ('year', 'aired'),
                xbmcplugin.SORT_METHOD_DURATION: ('duration',),
                xbmcplugin.SORT_METHOD_GENRE:    ('genre',),
        }.items():
            if any(it.item.get(key)
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
                method, sep2, mask2 = method.partition('|')
                mask1, sep1, mask2 = mask2.rpartition('|')
                if labelMask is None and mask1:
                    labelMask = mask1
                elif not sep1:
                    labelMask = '%L'
                if label2Mask is None and mask2:
                    label2Mask = mask2
                if method in ('', 'auto'):
                    # to process later
                    self.sort_list.append(Sort(method, labelMask, label2Mask))
                    return
                elif method == 'year' and not hasattr(xbmcplugin, 'SORT_METHOD_YEAR'):
                    method = 'video_year'
                method = getattr(xbmcplugin, 'SORT_METHOD_%s' % method.replace(' ', '_').upper())
            self.sort_list.append(Sort(method, labelMask, label2Mask))

    # @trace
    def new(self,
            _name: Union[str, Callable, Dict, 'MediaItem', ListItem],
            endpoint: Optional[Callable] = None,
            *,
            offscreen: Optional[bool] = None,
            folder: bool = False,
            playable: bool = False,
            label: Optional[str] = None,
            title: Optional[str] = None,
            descr: Optional[str] = None,
            format: Optional[str] = None,
            style: Optional[str] = None,
            image: Optional[Union[str, URL]] = None,
            fanart: Optional[Union[str, URL]] = None,
            thumb: Optional[Union[str, URL]] = None,
            properties: Optional[Dict[str, Any]] = None,
            position: Optional[Literal['top', 'bottom']] = None,
            menu: Optional[Union[List[str], List[Tuple[str, Callable]], 'AddonContextMenu']] = None,
            type: Optional[Literal['video', 'music', 'pictures', 'game']] = None,
            info: Optional[Dict[str, Any]] = None,
            art: Optional[Dict[str, Union[str, URL]]] = None,
            season: Optional[int] = None,
            episode: Optional[int] = None,
            label2: Optional[str] = None,
            sort_key: Optional[Any] = None,
            custom: Optional[Any] = None):
        """
        Create new list item, can be added to current directory list.

        new([name,] endpoint, folder=False, playable=False, descr=None, format=None,
            image=None, fanart=None, thumb=None, properties=None, position=None, menu=None,
            type=None, info=None, art=None, season=None, episode=None)

        Parameters
        ----------
        endpoint : method
            Addon method to call after user select.
        _name : str
            Label name as positional argument.
        offscreen : bool or None
            True if item is created offscreen and GUI based locks should be avoided.
        folder : bool
            True if item is a folder. Default is False.
        playable : bool
            True if item is playable, could be resolved. Default is False.
        label : str
            Item title, if None endpoint name is taken. If still missing, title is taken.
        title : str
            Item title, used in `info`
        descr : str
            Video description. Put into info labels.
        style : str ot list[str]
            Safe f-string style title format made by mkentry().
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
            Dictionary with xbmcgui.ListItem properties.
        position : str
            Item spesial sort: "top" or "bottom"
        menu : list[(str, str | function)] | AddonContextMenu
            Context menu. AddonContextMenu or list of entries.
            Each entry is tuple of title (str) and handle (str or addon method).
        type : str
            Contnent type (video, music, pictures, game). Default is directory default (video).
        info : dict[str, str]
            Labels info, see xbmcgui.ListItem.setInfo().
        art : dict[str, str]
            Links to art images, see xbmcgui.ListItem.setArt().
        season : int
            Season number or None if not a season nor an episode.
        episode : int
            Episode number or None if not an episode.
        label2 : str
            Item right label, forced by Kodi in many sort methods.
        sort_key: any
            Custom sort key, holt only in libka drirectory, not used in the Kodi
        custom: any
            Custom filed, holt only in libka drirectory, not used in the Kodi

        See: https://alwinesch.github.io/group__python__xbmcgui__listitem.html

        Item label
        ----------

        An item label is taken from (in the order):

        - parameter `label`
        - first argument (aka *name*)
        - endpoint title: `@entry(title=...)`
        - parameter `title`
        - `info['title']`

        In the case of `label` or *name* default label mask `|%L|` is used if no `sort` is defined.
        """
        # log.error('>>> ENTER...')  # DEBUG
        if offscreen is None:
            offscreen = self.offscreen
        if type is None:
            type = 'video' if self.type is None else self.type
        if style is None:
            style = self.style
        if sort_key is None:
            sort_key = self._next_sort_key
        name = _name
        log.xdebug(f'NEW: {label=!r}, {endpoint=!r}, {name=!r}')
        if label is not None and endpoint is None:
            name, endpoint = label, name
        if title is None and info and info.get('title'):
            _title = info['title']
        else:
            _title = title
        entry = self.router.mkentry(name, endpoint, title=_title, style=style)
        log.xdebug(f'new: {entry=!r}')
        if label is None:
            if isinstance(_name, dict):  # dict & MediaItem
                label = _name.get('label', _name.get('title'))
            elif isinstance(_name, xbmcgui.ListItem):
                label = _name.getLabel()
            else:
                label = entry.label
        if label is None:
            if entry.title is None:
                label = str(entry.url)
            else:
                label = entry.title
        else:
            self._label_used = True
        list_item_label = label
        if isinstance(_name, MediaItem):
            list_item_label = _name.create()
        elif isinstance(_name, xbmcgui.ListItem):
            list_item_label = _name
        item = ListItem(list_item_label, url=entry.url, folder=folder, type=type, offscreen=offscreen,
                        sort_key=sort_key, custom=custom)
        if folder is True:
            item.setIsFolder(folder)
        if label2 is not None:
            item.setLabel2(label2)
            self._label2_used = True
        # properties
        if properties is not None:
            item.setProperties(properties)
        if playable:
            item.setProperty('IsPlayable', 'true')
        if position is not None:
            item.setProperty('SpecialSort', position)
        # menu
        if menu is not None:
            item.menu = AddonContextMenu(self._menu, self._next_item_menu, menu, addon=self.addon)
        self._next_item_menu = None
        # info
        info = {} if info is None else dict(info)
        if entry.title is not None:
            info.setdefault('title', entry.title)
        if descr is not None:
            info['plot'] = descr
            # info.setdefault('plotoutline', descr)
            # info.setdefault('tagline', descr)
        if season is not None:
            info['season'] = season
        if episode is not None:
            info['episode'] = episode
        if info:
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
        art = {k: (f'https:{im}' if v.startswith('//')
                   else im if '://' in im or Path(im).is_absolute()
                   else self.addon.media.image(im))
               for k, v in art.items() if v for im in (str(v),)}
        if art:
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
            if entry.title is not None:
                label.title = safefmt(format, entry.title, **info)
            label = safefmt(format, label, **info)
        label = self.addon.format_title(label, entry.style, n=len(self.item_list) + 1)
        log.xdebug(f'[new]: {label=!r}, {info=!r}')
        item.setLabel(label)
        return item

    def add(self, item, endpoint=None, folder=None):
        if item is not None:
            self.item_list.append(Item(item, endpoint, folder))
        return item

    def _prepare(self, item, endpoint=None, folder=None):
        """Helper. Add item to xbmcplugin directory."""
        ifolder = False
        if isinstance(item, ListItem):
            # our list item, recover url and folder flag
            item()
            item, url, ifolder = item._libka_item, item._libka_url, item._libka_folder
            if endpoint is not None:
                url, *_ = self.router.mkentry(item.getLabel(), endpoint)
        elif isinstance(item, xbmcgui.ListItem):
            # pure kodi list item, create url from endpoint
            url, *_ = self.router.mkentry(item.getLabel(), endpoint)
            if kodi_ver >= (20,):
                ifolder = item.isFolder()
        else:
            # fallback, use "item" as title and create url from endpoint
            title, url, style = self.router.mkentry(item, endpoint)
            title = self.addon.format_title(title, style=style)
            item = xbmcgui.ListItem(title)
        if folder is None:
            folder = ifolder
        # log(f'FOLDER.prepare: {url!r}, item={item!r}, folder={folder!r} label={item.getLabel()!r}')
        return DirectoryItem(url, item, folder)

    def _add(self, item, endpoint=None, folder=None):
        """Helper. Add item to xbmcplugin directory."""
        return xbmcplugin.addDirectoryItem(*self._prepare(item, endpoint, folder=folder))

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

    def separator(self, title='———————', *, folder=None, **kwargs):
        """
        Add separator item to current directory list.

        Parameters
        ----------
        title : str
            Separator title, if None default is taken.
        folder: None or call
            Folder endpoint if not None.

        For more arguments see AddonDirectory.new().
        """
        if folder is None or folder is False:
            endpoint, folder = self.addon.no_operation, False
        elif folder is True:
            raise ValueError('Separator folder have to be folder-endpoint or None')
        else:
            endpoint, folder = folder, True
        kwargs.setdefault('style', self.addon.styles.get('folder_list_separator', ['COLOR khaki', 'B', 'I']))
        kwargs.setdefault('thumb', self.addon.libka.media.image('transparent.png'))
        return self.item(title, endpoint, playable=False, folder=folder, **kwargs)

    def parse(self, *args, **kwargs):
        """
        Custom parse. Call Addon.parse_list_item(kd, *args, **kwargs) if exists.
        """
        handler = getattr(self.addon, 'parse_list_item', None)
        if handler is not None:
            return handler(self, *args, **kwargs)

    def item_count(self):
        """
        Returns number of items on the list.
        """
        return len(self.item_list)

    @contextmanager
    def context_menu(self, safe=False, **kwargs):
        if self._next_item_menu is None:
            self._next_item_menu = AddonContextMenu(addon=self.addon, **kwargs)
        try:
            yield self._next_item_menu
        except Exception:
            if not safe:
                raise
        else:
            pass
        finally:
            pass

    @contextmanager
    def items_block(self):
        block = AddonDirectoryBlock(self)
        next_sort_key = self._next_sort_key
        try:
            yield block
        except Exception:
            ...
            raise
        finally:
            self._next_sort_key = next_sort_key
            pass


# Update AddonDirectory.ITEM_KEYS form `AddonDirectory.new() signature`
AddonDirectory.ITEM_KEYS = tuple(p.name for p in signature(AddonDirectory.new).parameters.values()
                                 if p.kind == p.KEYWORD_ONLY)


class AddonDirectoryBlock:
    """
    Block of items added to folder `AddonDirectory`.
    """

    _AddonDirectoryMethods = {'new', 'add', 'item', 'folder', 'play'}

    def __init__(self, directory):
        self.directory = directory
        self.start = len(self.directory.item_list)
        self._sort_key = None

    def sort_items(self, *, key=None, reverse=False):
        """
        Sort items added in the block.

        Return a new list containing all items from the iterable in ascending order.

        A custom key function can be supplied to customize the sort order, and the
        reverse flag can be set to request the result in descending order.
        """
        if key is None:
            def key(item):
                if item.sort_key is None:
                    return item.label
                return item.sort_key

        if len(self.directory.item_list) > self.start:
            self.directory.item_list[self.start:] = sorted(self.directory.item_list[self.start:],
                                                           key=lambda item: key(item.item), reverse=reverse)

    def item_count(self):
        """
        Returns number of items on the list block.
        """
        return len(self.item_list) - self.start

    def __getattr__(self, key):
        """
        All unknown attrobutes are forwarded to `AddonDirectory` (include methods).
        """
        if key in self._AddonDirectoryMethods:
            return getattr(self.directory, key)
        raise KeyError(key)

    def set_sort_key(self, sort_key):
        """
        Set default sort key for all next new items.
        """
        self.directory._next_sort_key = sort_key


class AddonContextMenu(list):
    """
    Thiny wrapper for plugin list item context menu.

    See: `xbmcgui.ListItem`.
    """

    def __init__(self, *menus, addon):
        self.addon = addon
        for menu in menus:
            if menu is not None:
                self.add_items(menu)

    def add(self, title, endpoint=None, *, format=None, style=None):
        method = title if endpoint is None else endpoint
        entry = self.addon.mkentry(title, endpoint, style=style)
        label = entry.label
        if label is None:
            label = entry.title
        label = self.addon.format_title(label, entry.style, n=len(self) + 1)
        if isinstance(method, str):
            self.append((label, entry.url))
        else:
            self.append((label, f'Container.Update({entry.url})'))
            # self.append((label, f'Container.Refresh({entry.url})'))
            # self.append((label, f'XBMC.RunPlugin({entry.url})'))

    def add_items(self, menu):
        for item in menu or ():
            if not isinstance(item, str) and isinstance(item, Sequence):
                # tuple: (title, handle) or (handle,)
                self.add(*item[:2])
            else:
                # just directly: handle
                self.add(item)

    append_items = add_items


class AddonStuff:
    """
    Dict with Kodi media infos. With extra API.
    """
    def __init__(self):
        # self.addonPoster = control.addonPoster()
        # self.addonBanner = control.addonBanner()
        # self.addonFanart = control.addonFanart()
        # self.settingFanart = control.setting('fanart')
        self.addonPoster = None
        self.addonBanner = None
        self.addonFanart = None
        self.settingFanart = True


class MediaItemAttr:
    """
    Proxy to MediaItem dict with an attribute access.
    Missing attributes return ''.
    """

    def __init__(self, *, media: 'MediaItem'):
        self._media = media

    def __repr__(self) -> str:
        return f'MediaItemAttr({self._media})'

    def __getattr__(self, key: str) -> Any:
        return self._media.get(key, '')

    def __setattr__(self, key: str, value: Any) -> None:
        if key.startswith('_'):
            object.__setattr__(self, key, value)  # skip super(), there is no other bases
        else:
            self._media[key] = value

    def __delattr__(self, key: str) -> None:
        self._media.pop(key, None)

    def __getitem__(self, key: str) -> Any:
        return self._media.get(key, '')

    def __setitem__(self, key: str, value: Any) -> None:
        self._media[key] = value

    def __delitem__(self, key: str) -> None:
        self._media.pop(key, None)


class MediaItem(dict):
    """
    Dict with Kodi media infos. With extra API.
    """
    _addon_stuff: AddonStuff = None

    _re_date: re.Pattern = re.compile(r'([12]\d{3})(?:-([01]\d)-([123]\d)(?:[ t].*)?)?')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = 'video'

    def __getattr__(self, key: str) -> Any:
        """Returns None for any unknown attribite."""
        return None

    @property
    def attr(self) -> MediaItemAttr:
        """Access via attributes."""
        return MediaItemAttr(media=self)

    a = attr
    an = attr
    the = attr

    @property
    def tmdb(self) -> str:
        """TMDB ID."""
        return self.get('tmdb', '')

    @property
    def imdb(self) -> str:
        """IMDB ID."""
        return self.get('imdb', '')

    @property
    def title(self) -> str:
        """Title."""
        return self.get('title', '')

    def clone(self) -> 'MediaItem':
        media: MediaItem = MediaItem(self)
        media.__dict__.update(self.__dict__)
        return media

    def create(self, label: Optional[str] = None) -> xbmcgui.ListItem:
        """
        Create a ListItem and set all infos into Kodi ListItem.
        """
        if label is None:
            label = self.get('title', '')
        li: ListItem = xbmcgui.ListItem(label)
        self.set(li)
        return li

    def set(self, list_item: xbmcgui.ListItem) -> None:
        """
        Set all infos into Kodi ListItem.
        Only video media is supporteed at the moment.
        """
        def has(key: str) -> Any:
            val = self.get(key)
            return val and val != '0'

        def get(key: str, default: str = '') -> Any:
            val = self.get(key)
            return val if val and val != '0' else default

        stuff: AddonStuff = self.addon_stuff()
        vtag: 'InfoTagVideo' = list_item.getVideoInfoTag()

        # --- IDs ---
        ids: Dict[str, str] = {key: self[key] for key in ('tmdb', 'imdb', ) if has(key)}
        if ids:
            vtag.setUniqueIDs(ids, 'tmdb' if 'tmdb' in ids else '')

        # --- title etc. ---
        for name in ('Title', 'OriginalTitle', 'Plot', 'TagLine', 'Mpaa'):  # str
            # Names are from InfoTagVideo (func name) and string media data (lower),
            # then Title → vtag.setTitle(str(self['title']))
            key: str = name.lower()
            if has(key):
                setter: Callable = getattr(vtag, f'set{name}')
                if setter:
                    setter(str(self[key]))

        for name in ('Year', 'Duration'):  # int
            # Names are from InfoTagVideo (func name) and integer media data (lower),
            # then Year → vtag.setYear(int(self['year']))
            key: str = name.lower()
            if has(key):
                setter: Callable = getattr(vtag, f'set{name}')
                if setter:
                    val = self[key]
                    if isinstance(val, (date, datetime)):
                        setter(val.year)
                    else:
                        setter(int(val))

        for name in ('Genres', 'Directors', 'Writers', 'Countries', 'Studios'):  # list[str]
            # Names are from InfoTagVideo (func name) and list of str media data (lower),
            # then Genres → vtag.setGenres(list(self['genres']))
            key: str = name.lower()
            if has(key):
                setter: Callable = getattr(vtag, f'set{name}')
                if setter:
                    lst = self[key]
                    if isinstance(lst, str):
                        lst = [str]
                    setter(lst)

        for name in ('Premiered',):  # date
            # Names are from InfoTagVideo (func name) and list of str media data (lower),
            # then Genres → vtag.setGenres(list(self['genres']))
            key: str = name.lower()
            if has(key):
                setter: Callable = getattr(vtag, f'set{name}')
                if setter:
                    val = self[key]
                    if isinstance(val, datetime):
                        val = val.date()
                    setter(str(val))

        # --- casts, directors etc. ---
        castwiththumb = self.get('castwiththumb')
        if castwiththumb:
            castwiththumb = [Actor(**a) for a in castwiththumb]
            vtag.setCast(castwiththumb)
        if has('rating'):
            vtag.setRating(self['rating'], self.get('votes', -1), 'tmdb', True)

        # --- art ---
        poster: str = self.get('poster', stuff.addonPoster)
        art: Dict[str, str] = {'icon': poster, 'thumb': poster, 'poster': poster}
        fanart: str = self['fanart'] if stuff.settingFanart and has('fanart') else stuff.addonFanart

        art['fanart'] = fanart
        art['landscape'] = get('landscape', fanart)
        art['banner'] = get('banner', stuff.addonBanner)

        for key in ('clearlogo', 'clearart'):
            if has(key):
                art[key] = self[key]

        list_item.setArt(art)

        # --- info ---
        info = {}
        for key in ('status', ):
            if has(key):
                info[key] = self[key]
        if info:
            list_item.setInfo(self.type, info)
        # L(f'{self.keys()=}')

        # --- misc ---
        # vtag.addVideoStream(VideoStreamDetail(codec='h264'))  # XXX: Why 'h264' for all videos???

    @classmethod
    def addon_stuff(cls) -> ...:
        if cls._addon_stuff is None:
            cls._addon_stuff = AddonStuff()
        return cls._addon_stuff

    @classmethod
    def parse_date(cls, value: str) -> date:
        if value:
            if isinstance(value, int):
                return date(value, 1, 1)
            if isinstance(value, date):
                return value
            if isinstance(value, datetime):
                return value.date()
            mch = cls._re_date.match(value)
            if mch:
                y, m, d = mch.groups()
                return date(int(y), int(m or 1), int(d or 1))
        return None

    @classmethod
    def parse_year(cls, value: str) -> int:
        if value:
            if isinstance(value, int):
                return value
            if isinstance(value, (date, datetime)):
                return value.year
            mch = cls._re_date.match(value)
            if mch:
                return int(mch[1])
        return None


class MediaList(list):
    """
    List of MediaItem with some extra properties.
    """

    def __init__(self, *args,
                 next: Optional[Union[str, URL]] = None,
                 page: Optional[int] = None,
                 total: Optional[int] = None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        #: URL to next page or None.
        self.next_url: URL = None if next is None else URL(next)
        #: The Page number or zero.
        self.page: int = int(page or 0)
        #: The total page number or zero.
        self.total: int = int(total or 0)
