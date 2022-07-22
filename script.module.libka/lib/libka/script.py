"""
Script module to handle `RuncScript()` entry.
"""

import sys
from typing import (
    Optional, Callable, Any,
    List,
)
from .addon import AddonMixin, LibkaTheAddon, Request
from .url import URL
from .routing import Router
from .commands import Commands


class Script(AddonMixin):
    """
    Script `RuncScript()` entry support.
    """

    def __init__(self, argv: Optional[List[str]] = None, router: Optional[Router] = None):
        super().__init__()
        if argv is None:
            argv = sys.argv
        #: Arguments [0] = script name.
        self.argv: List[str] = argv
        # build script pseudo-URL
        n: int = 0
        query: List[str] = []
        for val in self.argv[2:]:
            if '=' not in val:
                val = f'{n}={val}'
                n += 1
            query.append(val)
        query = '&'.join(query)
        path: str = self.argv[1] if len(self.argv) > 1 else ''
        url: URL = URL(f'script://{self.id}/{path}?{query}')
        from .logs import log
        log(f'SCRIPT URL {url!r}')
        #: Kodi script pseudo-request to script://...
        self.req: Request = Request(url, raw_keys=self.encoded_keys)
        #: Router
        self.router: Optional = router
        if self.router is None:
            self.router = Router(f'script://{self.id}', obj=self, addon=self, standalone=False)
        #: Kodi commands
        self.cmd: Commands = Commands(addon=self, mkurl=self.router.mkurl)
        #: Libka itself
        self._libka: LibkaTheAddon = None

    def __repr__(self):
        return f'{self.__class__.__name__}({self.id!r}, {self.argv!r})'

    @property
    def libka(self) -> LibkaTheAddon:
        """Libka addon itself."""
        if self._libka is None:
            self._libka = LibkaTheAddon()
        return self._libka

    def dispatch(self, *, sync: bool = True,
                 root: Optional[Callable] = None, missing: Optional[Callable] = None) -> Any:
        """
        Dispatcher. Call pointed method with request arguments.
        """
        if missing is None and callable(getattr(self, 'missing', None)):
            missing = self.missing
        # TODO: use async too
        if sync:
            return self.router.sync_dispatch(self.req.url, root=None, missing=missing)
        return self.router.dispatch(self.req.url, root=None, missing=missing)

    def run(self, *, sync: bool = True):
        """Run plugin. Dispatch url. Use sync=False to run asyncio."""
        try:
            res = self.dispatch(sync=sync)
        finally:
            self.user_data.save()
        return res

    def style(self, name, *, addon=None):
        """Open style-chooser dialog."""
        if addon is None:
            addon = self
        elif isinstance(addon, str):
            addon = AddonMixin(id=addon)
