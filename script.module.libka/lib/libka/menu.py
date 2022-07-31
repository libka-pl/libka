"""
Simple menu module to generate plugin root folders.

.. include:: ../../../doc/en/menu.md

"""

from typing import (
    Optional, Union, Any, Callable,
    List, Dict, Set, Iterator,
    NamedTuple,
    TYPE_CHECKING,
)
from .routing import PathArg, call, Call
from .types import regex
from .logs import log
from copy import copy
from fnmatch import fnmatch
if TYPE_CHECKING:
    from .folder import AddonDirectory


#: Multi-entry item type.
Item = Dict[str, Any]


class Menu:
    """
    Menu definition.

    Parameters
    ----------
    title : str
        Menu entry title.
    call : callable
        Menu entry destination.
    items : list or None
        List of submenu entries.
    entry_iter : callable
        Iterator for multi-entry to get items.
    order : dict
        Order of items in multi-entry. The key is order (higher on top) and values is a pattern of list of patterns.
    process_entry : callable
        Method to process the entry. Should add list-item to the kodi directory.
    process_item : callable
        Method to process single item from multi-entry. Should add list-item to the kodi directory.

    Any parameter name could be used. Those above have special meanings.

    Methods could be regular sub-class method or callable argument in the constructor.

    Dict `order` point order level and theirs patterns. Patterns could be a single pattern
    or a list of single patterns. Single pattern is (ignore case) `fnmatch` pattern
    or a compiled regex (`re.compile`).
    """

    #: Set of parameters name that are obligatory. Could be overwritten ins subclass.
    OBLIGATORY: Set[str] = set()

    #: Default values for some parameters. Value is copied, than `[]` could be used.
    DEFAULTS: Dict[str, Any] = {}

    #: Name of parameter used to ordering. It's taken from multi-entry item.
    ORDER_KEY: str = None

    #: Name of parameter used to sorting int the same order level.
    #: It's taken from multi-entry item. The item index is used if `SORT_KEY` is None.
    SORT_KEY: str = None

    def __init__(self, **kwargs):
        missing: Set[str] = self.OBLIGATORY - kwargs.keys()
        if missing:
            raise TypeError('Missing arguments in Menu: {}'.format(', '.join(missing)))
        self._data = kwargs
        self._updated_data = None

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, ', '.join(f'{k}={v!r}' for k, v in self._data.items()))

    def __getattr__(self, key: str) -> Any:
        if key[:1] == '_':
            raise KeyError(key)
        if self._updated_data is None:
            data = self._data
        else:
            data = self._updated_data
        return data.get(key, copy(self.DEFAULTS.get(key)))

    def _order(self, text: str) -> int:
        """
        Count order level (higher on top) based on `order` menu entry variable.

        Parameters
        ----------
        text : str
            String to match. Example a title.

        Returns
        -------
        int
            Negative order level (lower on top) useful to sort.

        Dict `order` point order level and theirs patterns. Patterns could be a single pattern
        or a list of single patterns. Single pattern is (ignore case) `fnmatch` pattern
        or a compiled regex.
        """
        text = text.lower()
        for k, vv in self._data.get('order', {}).items():
            if type(vv) is str:
                vv = (vv,)
            for v in vv:
                if type(v) is regex:
                    if v.match(text):
                        return -k
                if fnmatch(text, v):
                    return -k
        return 0

    def _item_order(self, *, addon: 'MenuMixin', item: Item, index: int):
        order_key = (self._updated_data or self._data).get('order_key', self.ORDER_KEY)
        if callable(order_key):
            order_key = order_key(item)
        else:
            order_key = item.get(order_key, '')
        return self._order(order_key)

    def _item_sort(self, *, addon: 'MenuMixin', item: Item, index: int) -> Union[int, str]:
        if self.SORT_KEY is None:
            return index
        return self.SORT_KEY

    def _process_entry(self, *, addon: 'MenuMixin', kdir: 'AddonDirectory', index_path: List[int],
                       data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Handle menu entry.
        """
        self._updated_data = data
        try:
            if self.when and not addon.settings[self.when]:
                return
            entry_iter = getattr(self, 'entry_iter', None)
            if entry_iter is not None:
                process_item = self._data.get('process_item', self.process_item)
                with kdir.items_block() as blk:
                    for j, it in enumerate(entry_iter(addon=addon)):
                        order = self._item_order(addon=addon, item=it, index=j)
                        sort = self._item_sort(addon=addon, item=it, index=j)
                        blk.set_sort_key((order, sort))
                        process_item(addon=addon, kdir=kdir, index_path=index_path, item=it)
                    blk.sort_items()
            elif self.call:
                method: Callable
                if isinstance(self.call, str):
                    target = method = getattr(addon, self.call, self.call)
                elif isinstance(self.call, Call) and self.call.method:
                    method = getattr(addon, self.call.method, self.call.method)
                    target = Call(method=method, args=self.call.args, kwargs=self.call.kwargs, raw=self.call.raw)
                else:
                    target = method = self.call
                title: str = self.title
                if title is None:
                    entry = getattr(method, '_libka_endpoint', None)
                    if entry is not None and entry.title is not None:
                        title = entry.title
                kdir.menu(title, target)
            elif self.items:
                kdir.menu(self.title, call(addon.menu, ','.join(map(str, index_path))))
            else:
                process_entry = self._data.get('process_entry', self.process_entry)
                return bool(process_entry(addon=addon, kdir=kdir, index_path=index_path))
            return True
        finally:
            self._updated_data = None

    def process_entry(self, *, addon: 'MenuMixin', kdir: 'AddonDirectory', index_path: List[int]) -> bool:
        """
        Method to process the entry. Should add list-item to the kodi directory.
        """
        return addon.menu_entry(kdir=kdir, entry=self, index_path=index_path)

    def process_item(self, *, addon: 'MenuMixin', kdir: 'AddonDirectory', index_path: List[int], item: Item) -> bool:
        """
        Method to process single item from multi-entry. Should add list-item to the kodi directory.
        """
        return addon.menu_entry_item(kdir=kdir, entry=self, item=item, index_path=index_path)

    @classmethod
    def menu_info(cls, *, addon: 'MenuMixin', index_path: str):
        index_path = [int(v) for v in index_path.split(',') if v]
        menu = getattr(addon, 'MENU', None)
        if menu is None:
            log.warning(f'MENU is not defined, skipping {addon.__class__.__name__}.menu()')
            return
        extra_data = dict(menu._data)
        for p in index_path:
            menu = menu.items[p]
            extra_data.update(menu._data)
        extra_data = {k: v for k, v in extra_data.items() if k in addon.MENU_INHERIT_KYES}
        return MenuEntryInfo(menu, index_path, extra_data)


class MenuItems(Menu):
    """
    Menu multi-entry. Entry generates dynamic items.

    See: `Menu`.
    """

    def entry_iter(self, *, addon: 'MenuMixin') -> Iterator[Item]:
        """
        Yield items for menu multi-entry.

        Parameters
        ----------
        addon : Addon
            Addon with `MenuMixin` mix-in.

        See: `MenuMixin.menu_entry_iter`.
        """
        yield from addon.menu_entry_iter(entry=self)


class MenuEntryInfo(NamedTuple):
    """Helper. Pass namu info in `MenuMixin` methods."""
    # Processed menu.
    menu: Menu
    # Menu path of indexes.
    index_path: List[int]
    # Extra data combined from root to `menu`.
    extra_data: Dict[str, Any]


class MenuMixin:
    """
    Menu mixin to use with Addon.
    """

    MENU_INHERIT_KYES = {'order_key', 'view'}

    def _menu(self, kdir: 'AddonDirectory', index_path: str = '', *, info: Optional[MenuEntryInfo] = None) -> None:
        """
        Method called on menu support. Call it from `home()`.

        Parameters
        ----------
        kdir : AddonDirectory
            Opened Kodi directory.
        pos : str
            Comma separated submenu index path.
        """
        if info is None:
            info = Menu.menu_info(addon=self, index_path=index_path)
        info.index_path.append(-1)
        for i, ent in enumerate(info.menu.items or ()):
            info.index_path[-1] = i
            data = {**info.extra_data, **ent._data}
            ent._process_entry(addon=self, kdir=kdir, index_path=info.index_path, data=data)

    def menu(self, index_path: PathArg[str] = '') -> None:
        """
        Build menu folder. Call it from `home()`.

        Parameters
        ----------
        index_path : str
            Comma separated submenu index path.

        Build folder for (sub)menu.
        """
        info = Menu.menu_info(addon=self, index_path=index_path)
        kwargs = {}
        if info.menu.view is not None and info.menu.view != 'none':
            kwargs['view'] = info.menu.view
        with self.directory(**kwargs) as kdir:
            self._menu(kdir, index_path, info=info)

    def menu_entry(self, *, kdir: 'AddonDirectory', entry: Menu, index_path: List[int]) -> bool:
        """
        Add `entry` to directory `kdir`.

        Parameters
        ----------
        kdir : AddonDirectory
            Opened Kodi directory.
        entry : Menu
            Menu entry, source of data for Kodi list item.
        index_path : str
            Comma separated submenu index path.
        """
        return False

    def menu_entry_iter(self, *, entry: Menu) -> Iterator[Item]:
        """
        Yield items for menu multi-entry.

        Parameters
        ----------
        entry : Menu
            Menu entry, source of data for Kodi list item.

        Example
        -------
        >>> def menu_entry_iter(self, *, entry):
        ...     for it in self.get_items(entry.id):
        ...         yield it
        ```
        """
        return ()

    def menu_entry_item(self, *, kdir: 'AddonDirectory', entry: Menu, item: Item, index_path: List[int]) -> bool:
        """
        Add `entry` to directory `kdir`.

        Parameters
        ----------
        kdir : AddonDirectory
            Opened Kodi directory.
        entry : Menu
            Menu entry, source of data for Kodi list item.
        item : any
            Item of menu multi-entry, source of data for Kodi list item.
        index_path : str
            Comma separated submenu index path.
        """
        return False
