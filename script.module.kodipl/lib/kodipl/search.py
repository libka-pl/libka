
from typing import (
    Union, Optional,
    List, Dict,
)
from collections import namedtuple
from datetime import datetime
from .routing import entry, call
from .lang import L
from .logs import log
from .storage import AddonUserData
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
                 style: Optional[Union[str, List[str]]] = None):
        if site is None:
            site = addon
        self.addon = addon
        self.site = site
        self.name = name
        self.udata = AddonUserData('search.json', addon=addon)
        self._history = None
        self.size = size
        self.style = style
        if self.style is None:
            self.style = ['B']

    def _json_search_name(self):
        """Key-path in JSON search file."""
        if self.name is None:
            return ['history', 'items']
        return ['history', 'search', self.name, 'items']

    @property
    def history(self) -> List[str]:
        """Lazy load history entries."""
        if self._history is None:
            self._history = [SearchItem(**d) for d in self.udata.get(self._json_search_name(), [])]
        return self._history

    @history.setter
    def history(self, entries: List[str]) -> None:
        """Save history entries."""
        self._history = list(entries[:self.size])
        self.udata.set(self._json_search_name(), [d._asdict() for d in self._history])
        self.udata.save(indent=2)

    def _add(self, query: str, options: Dict[str, str] = None) -> None:
        history = self.history
        now = datetime.now().replace(microsecond=0)
        now = str(now.astimezone())  # TODO: handle datetime directly
        history.insert(0, SearchItem(query, options, now))
        self.history = history

    def refresh(self) -> None:
        self.addon.refresh(self.addon.mkurl(self))

    @entry(label=L(32302, 'Search'))
    def __call__(self) -> None:
        """Call enter search main view (list of last searches)."""
        with self.addon.directory(cache=False) as kd:
            kd.menu(self.new, label=L(32303, 'New search'), style=self.style, position='top')
            # kd.item(self.options, label=L(32304, 'Search options'), style=self.style, position='top')
            for index, query in enumerate(self.history):
                if query.options is None:
                    endpoint = call(self.it, query=query.query)
                else:
                    endpoint = call(self.it, query=query.query, options=query.options)
                kd.menu(endpoint, label=query.query, menu=(
                    (L(32305, 'Remove'), self.addon.cmd.RunPlugin(self.remove, index)),
                    (L(32306, 'Clear all'), self.addon.cmd.RunPlugin(self.clear)),
                ))

    def it(self, query: str, options: Dict[str, str] = None) -> None:
        """
        Search query and list found items.
        """
        # self.site.yield_query_list(query)
        # XXX --- XXX --- XXX  (DEBUG)
        data = [
            {'title': f'Aaa of {query}', },
            {'title': f'Bbb of {query}', },
            {'title': f'Ccc of {query}', },
        ]
        with self.addon.directory() as kd:
            for index, item in enumerate(data):
                kd.item(self.addon.settings, title=item['title'])

    def new(self, query: Optional[str] = None) -> None:
        """
        New search query. Opens dialog is `query` is None.
        """
        if not query:
            query = xbmcgui.Dialog().input(L(32307, 'Search: enter query'), type=xbmcgui.INPUT_ALPHANUM)
        if query:
            self._add(query)
            self.it(query)

    def remove(self, index: int) -> None:
        """
        Remove search from history by query index (start from zero).
        """
        history = self.history
        try:
            del history[index]
        except IndexError:
            log.warning(f'Can not remove history at {index!r}')
        else:
            self.history = history
            self.refresh()

    def remove_query(self, query: str) -> None:
        """
        Remove search from history by query text.
        """
        self.history = [item for item in self.history if item.query != query]
        self.refresh()

    def clear(self) -> None:
        """
        Clear all search history.
        """
        self.udata.remove(self._json_search_name())
        self.refresh()
