
from typing import (
    Union, Optional, Callable, Any,
    List, Dict,
)
from inspect import signature
from collections import namedtuple
from datetime import datetime
from .routing import entry, call
from .lang import L
from .logs import log
from .storage import Storage
from .purpose import purpose_decorator, find_purpose
import xbmcgui


#: Search item in JSON file.
SearchItem = namedtuple('SearchItem', 'query options creation_date', defaults=(None,))
# SearchItem.json = lambda self:  {
#     'query': self.query,
#     'options': self.options,
#     'creation_date': self.creation_date and str(self.creation_date.astimezone()),
# }


class Search:
    """
    Serach engene for a Plugin.

    Implements search sub-menu. Stores last searchs.
    Calls plugin to make site requests.
    """

    def __init__(self, addon, site=None, *, name: str = None, size: int = 50,
                 style: Optional[Union[str, List[str]]] = None,
                 method: Callable = None):
        if site is None:
            site = addon
        self.addon = addon
        self.site = site
        self.name = name
        self.udata = Storage('search.json', addon=addon, pretty=True)
        self._history = None
        self.size = size
        self.style = style
        if self.style is None:
            self.style = ['B']
        self.method = method

    def _json_search_name(self, *, scope: Optional[str] = None):
        """Key-path in JSON search file."""
        path = ['history']
        if self.name is not None:
            path.extend(('search', self.name))
        if scope is not None:
            path.extend(('scope', scope))
        path.append('items')
        return path

    def get_history(self, *, scope: Optional[str] = None) -> List[str]:
        """Lazy load history entries."""
        if self._history is None:
            self._history = [SearchItem(**d) for d in self.udata.get(self._json_search_name(scope=scope), [])]
        return self._history

    def set_history(self, entries: List[str], *, scope: Optional[str] = None) -> None:
        """Save history entries."""
        self._history = list(entries[:self.size])
        self.udata.set(self._json_search_name(scope=scope), [d._asdict() for d in self._history])
        self.udata.save()

    def delete_history(self, *, scope: Optional[str] = None) -> None:
        """
        Remove all search history.
        """
        self.udata.remove(self._json_search_name(scope=scope))
        self.udata.save()

    history = property(get_history, set_history, delete_history)

    def _add(self, query: str, options: Dict[str, Any] = None, *, scope: Optional[str] = None) -> None:
        history = self.get_history(scope=scope)
        now = datetime.now().replace(microsecond=0)
        now = str(now.astimezone())  # TODO: handle datetime directly
        history.insert(0, SearchItem(query, options, now))
        self.set_history(history, scope=scope)

    def refresh(self) -> None:
        self.addon.refresh(self.addon.mkurl(self))

    @entry(label=L(32302, 'Search'))
    def __call__(self, *, scope: Optional[str] = None) -> None:
        """Call enter search main view (list of last searches)."""
        with self.addon.directory(cache=False) as kd:
            kd.menu(self.new, label=L(32303, 'New search'), style=self.style, position='top')
            # kd.item(self.options, label=L(32304, 'Search options'), style=self.style, position='top')
            for index, query in enumerate(self.get_history(scope=scope)):
                if query.options is None:
                    endpoint = call(self.it, query=query.query)
                else:
                    endpoint = call(self.it, query=query.query, options=query.options)
                kd.menu(endpoint, label=query.query, menu=(
                    (L(32305, 'Remove'), self.addon.cmd.RunPlugin(self.remove, index)),
                    (L(32306, 'Clear all'), self.addon.cmd.RunPlugin(self.clear)),
                ))

    def _call(self, method: Callable, query: str, options: Dict[str, Any] = None) -> Any:
        """Call custom search query folder."""
        sig = signature(method)
        if sum(1 for p in sig.parameters.values() if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)) > 1:
            return method(query, options)
        elif len(sig.parameters) > 1 and 'options' in sig.parameters:
            return method(query, options=options)
        else:
            return method(query)

    def it(self, query: str, options: Dict[str, Any] = None, *, scope: Optional[str] = None) -> None:
        """
        Search query and list found items.
        """
        method = self.method
        if method is None:
            method = find_purpose(self.site, 'search_folder')
        if method is not None:
            self._call(method, query, options)
            return

        # TODO: remove
        method = find_purpose(self.site, 'search_data')
        if method is not None:
            data = self._call(method, query, options)
            with self.addon.directory() as kd:
                for index, item in enumerate(data):
                    kd.item(self.addon.settings, title=item['title'])
            return
        log.error(f'No search method for search({self.name or ""}).')

    def new(self, query: Optional[str] = None, *, scope: Optional[str] = None) -> None:
        """
        New search query. Opens dialog is `query` is None.
        """
        if not query:
            query = xbmcgui.Dialog().input(L(32307, 'Search: enter query'), type=xbmcgui.INPUT_ALPHANUM)
        if query:
            self._add(query, scope=scope)
            self.it(query, scope=scope)

    def remove(self, index: int, *, scope: Optional[str] = None) -> None:
        """
        Remove search from history by query index (start from zero).
        """
        history = self.get_history(scope=scope)
        try:
            del history[index]
        except IndexError:
            log.warning(f'Can not remove history at {index!r}')
        else:
            self.set_history(history, scope=scope)
            self.refresh()

    def remove_query(self, query: str, *, scope: Optional[str] = None) -> None:
        """
        Remove search from history by query text.
        """
        history = [item for item in self.get_history(scope=scope) if item.query != query]
        self.set_history(history, scope=scope)
        self.refresh()

    def clear(self, *, scope: Optional[str] = None) -> None:
        """
        Clear all search history.
        """
        self.delete_history(scope=scope)
        self.refresh()


class search:
    """Decorators for searches."""

    @staticmethod
    def folder(method: Callable = None):
        return purpose_decorator(name='search_folder', method=method)

    @staticmethod
    def data(method: Callable = None):
        return purpose_decorator(name='search_data', method=method)
