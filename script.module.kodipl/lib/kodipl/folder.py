import re
from collections import namedtuple
from collections.abc import Sequence, Mapping
from .utils import setdefaultx
from .kodi import version_info as kodi_ver
from .format import safefmt
from .logs import log
import xbmcgui
import xbmcplugin


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

    def __init__(self, name, *, url=None, folder=None, type=None, offscreen=True):
        if isinstance(name, xbmcgui.ListItem):
            self._kodipl_item = name
        else:
            self._kodipl_item = xbmcgui.ListItem(name, offscreen=offscreen)
        self._kodipl_url = url
        self._kodipl_folder = folder
        self.type = type
        self._info = {}
        self._props = {}
        if self.type is not None:
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
        if self.type is None:
            raise TypeError('setInfo: type is None')
        self._info.update(infoLabels)
        self._kodipl_item.setInfo(self.type, self._info)

    @property
    def title(self):
        return self._info.get('title')

    @title.setter
    def title(self, title):
        self._info['title'] = title
        self._kodipl_item.setInfo(self.type, self._info)

    def setProperties(self, values):
        """See Kodi ListItem.setProperties()."""
        self._props.update(values)
        self._kodipl_item.setProperties(values)

    def setProperty(self, key, value):
        """See Kodi ListItem.setProperty()."""
        self._props[key] = value
        self._kodipl_item.setProperty(key, value)

    def get_property(self, key):
        """Get set property."""
        return self._props.get(key)


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
    After bar (|) `label2Mask` can be applied.

    Note. If sort=None and `label2` is used, than item info `code` is overwritten, and mask is forced to "%P".

    ### Example

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

    _RE_ISORT_SPLIT = re.compile(r'[,;]')

    def __init__(self, *, addon=None, view=None, sort=None, type='video', image=None, fanart=None,
                 format=None, style=None, isort=None, cache=False, update=False, offscreen=True):
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
            if self._label2_used:
                self.sort_list = [Sort('', label2Mask='%P')]
                for it in self.item_list:
                    if isinstance(it.item, ListItem):
                        it.item.set_info('code', it.item.getLabel2())
            else:
                self.sort_list = [Sort('')]
        # internal sort
        if self.isort:
            for srt in reversed(self.isort):
                reverse = False
                if srt.startswith('-'):
                    srt = srt[1:]
                    reverse = True
                elif srt.startswith('+'):
                    srt = srt[1:]
                self.item_list.sort(key=lambda it: (Cmp(it.item.get_info(srt))
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
                method, sep2, mask2 = method.partition('|')
                mask1, sep1, mask2 = mask2.rpartition('|')
                if labelMask is None and mask1:
                    labelMask = mask1
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
    def new(self, _name, endpoint=None, *, offscreen=None, folder=False, playable=False,
            label=None, title=None, descr=None, format=None, style=None,
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
        # log.error('>>> ENTER...')  # DEBUG
        if offscreen is None:
            offscreen = self.offscreen
        if type is None:
            type = 'video' if self.type is None else self.type
        if style is None:
            style = self.style
        if label is not None and endpoint is None:
            _name, endpoint = label, _name
        entry = self.router.mkentry(_name, endpoint, title=title, style=style)
        label = entry.label
        if label is None:
            label = entry.title
        item = ListItem(label, url=entry.url, folder=folder, type=type, offscreen=offscreen)
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
        info = {} if info is None else dict(info)
        if entry.title is not None:
            info.setdefault('title', entry.title)
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
            if entry.title is not None:
                label.title = safefmt(format, entry.title, **info)
            label = safefmt(format, label, **info)
        label = self.addon.format_title(label, entry.style, n=len(self.item_list) + 1)
        item.setLabel(label)
        # log.error('>>> EXIT...')  # DEBUG
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
            item, url, ifolder = item._kodipl_item, item._kodipl_url, item._kodipl_folder
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


class AddonContextMenu(list):
    """
    Thiny wrapper for plugin list item context menu.

    See: xbmcgui.ListItem.
    """

    def __init__(self, menu=None, *, addon):
        self.addon = addon
        if menu is not None:
            for item in menu:
                if not isinstance(item, str) and isinstance(item, Sequence):
                    # tuple: (title, handle) or (handle,)
                    self.add(*item[:2])
                else:
                    # just directly: handle
                    self.add(item)

    def add(self, title, endpoint=None, *, format=None, style=None):
        entry = self.addon.mkentry(title, endpoint, style=style)
        label = entry.label
        if label is None:
            label = entry.title
        label = self.addon.format_title(label, entry.style, n=len(self) + 1)
        self.append((label, entry.url))
