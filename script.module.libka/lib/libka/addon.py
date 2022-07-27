import sys
import re
from collections.abc import Sequence
from contextlib import contextmanager
from datetime import datetime
from typing import (
    overload,
    Union, Optional, Callable, Any,
    List,
)
from .base import BaseAddonMixin, LIBKA_ID
from .utils import parse_url
from .settings import Settings
from .search import Search
from .logs import log
from .resources import Resources
from .storage import Storage
from .folder import AddonDirectory
from .routing import Router, subobject, DirEntry, Call
from .menu import MenuMixin
from .commands import Commands
from .format import SafeFormatter, StylizeSettings
from .tools import adict, SingletonMetaclass
import xbmc
from xbmcaddon import Addon as XbmcAddon


class Request:
    """
    Addon call request.
    """

    def __init__(self, url, *, raw_keys=None):
        #: Parsed URL of addon reguest.
        self.url = parse_url(url, raw=raw_keys)
        #: Request decoded query dict.
        self.params = self.url.query


class AddonMixin(BaseAddonMixin):
    """
    Abstract Libka Addon.

    Arguments
    ---------
    argv: list[str]
        Command line arguemnts. If None, sys.argv is used.
    router: Router
        Router for URL and method matching. If None, new one is created.

    Created router (if router is None) handle global @entry decorators.
    """

    settings = subobject()

    def __init__(self, *args, **kwargs):
        addon_id = kwargs.pop('id', None)
        super().__init__(*args, **kwargs)
        now = datetime.now()
        #: Timezone UTC offset
        self.tz_offset = now - datetime.utcfromtimestamp(now.timestamp())
        #: Names for paramteres to encode raw Python data, don't use it.
        self.encoded_keys = {'_'}
        #: XBMC (Kodi) Addon
        self.xbmc_addon = XbmcAddon() if addon_id is None else XbmcAddon(addon_id)
        #: Addon ID (unique name)
        self.id = self.xbmc_addon.getAddonInfo('id')
        #: Addon settings.
        self.settings = Settings(addon=self, default=None)
        #: Default userdata
        self.user_data = Storage(addon=self)
        #: User defined colors used in "[COLOR :NAME]...[/COLOR]"
        self.colors = adict({
            'gray': 'gray',
            'grey': 'gray',
        })
        #: User defined styles for text / label formatting.
        self.styles = adict({
        })
        #: Resources
        self.resources = Resources(self)
        #: Default text formatter.
        self.formatter = SafeFormatter(extended=True, styles=self.styles,
                                       stylize=StylizeSettings(colors=self.get_color))

    def __repr__(self):
        return f'{self.__class__.__name__}({self.id!r})'

    @property
    def media(self):
        """Media resources."""
        return self.resources.media

    def get_color(self, name):
        return self.colors.get(name, 'gray')

    def format_title(self, text, style, n=0, info=None):
        return self.formatter.stylize(text, style, n=n, info=info, color=self.colors)

    def open_settings(self):
        """Deprecated. Use Addon.settings()."""
        self.xbmc_addon.openSettings()

    def builtin(self, command):
        """Execute Kodi build-in command."""
        xbmc.executebuiltin(command)

    def refresh(self, endpoint=None):
        """Execute Kodi build-in command."""
        if callable(endpoint) or isinstance(endpoint, Call):
            endpoint = self.mkurl(endpoint)
        xbmc.executebuiltin(f'Container.Refresh({endpoint or ""})')

    def make_run_plugin(self, endpoint):
        if callable(endpoint) or isinstance(endpoint, Call):
            endpoint = self.mkurl(endpoint)
        return f'XBMC.RunPlugin({endpoint})'

    def get_default_art(self, name):
        """Returns path to default art."""

    def no_operation(self):
        """Do nothing. For fake menu."""


class Addon(MenuMixin, AddonMixin):
    """
    Abstract Libka Addon.

    Arguments
    ---------
    argv: list[str]
        Command line arguemnts. If None, sys.argv is used.
    router: Router
        Router for URL and method matching. If None, new one is created.

    Created router (if router is None) handle global @entry decorators.
    """

    #: Only method with @entry is allowed if True, else any method
    SAFE_CALL = False
    #: Default root (home) entry method name or list of methods (find first).
    ROOT_ENTRY = ('home', 'root')

    search = subobject()

    def __init__(self, argv=None, router=None):
        super().__init__()
        if argv is None:
            argv = sys.argv
        if len(argv) < 3 or (argv[1] != '-1' and not argv[1].isdigit()) or (argv[2] and argv[2][:1] != '?'):
            raise TypeError('Incorrect addon args: %s' % argv)
        #: Addon handle (integer).
        self.handle = int(argv[1])
        #: Kodi request to plugin://...
        self.req = Request(argv[0] + argv[2], raw_keys=self.encoded_keys)
        #: Addon ID (unique name)
        self.id = self.req.url.host
        # Set default addon for Call formating.
        Call.addon = self
        #: Router
        self.router = router
        if self.router is None:
            plugin_link = f'{self.req.url.scheme or "plugin"}://{self.id}'
            self.router = Router(plugin_link, obj=self, addon=self, standalone=False)
        #: Kodi commands
        self.cmd = Commands(addon=self, mkurl=self.router.mkurl)
        #: Addon default search.
        self.search = Search(self)
        #: Libka itself
        self._libka = None

    def __repr__(self):
        return f'{self.__class__.__name__}({self.id!r}, {str(self.req.url)!r})'

    @property
    def libka(self):
        """Libka addon itself."""
        if self._libka is None:
            self._libka = LibkaTheAddon()
        return self._libka

    @overload
    def mkentry(self, endpoint: Union[Callable, str], *, style: Union[str, List[str]] = None) -> DirEntry:
        ...

    @overload
    def mkentry(self, title: str, endpoint: Callable, *, style: Union[str, List[str]] = None) -> DirEntry:
        ...

    def mkentry(self, title, endpoint=None, *, style=None):
        """Helper. Returns (title, url) for given endpoint."""
        return self.router.mkentry(title, endpoint, style=style)

    def mkurl(self, endpoint: Union[str, Callable], *args, **kwargs) -> str:
        """
        Create plugin URL to given name/method with arguments.
        """
        return self.router.mkurl(endpoint, *args, **kwargs)

    url_for = mkurl

    def dispatch(self, *, sync: bool = True,
                 root: Optional[Callable] = None, missing: Optional[Callable] = None) -> Any:
        """
        Dispatcher. Call pointed method with request arguments.
        """
        if root is None:
            if callable(getattr(self, 'home', None)):
                root = self.home
            elif hasattr(self, 'MENU') and callable(getattr(self, 'menu', None)):
                root = self.menu
        if missing is None and callable(getattr(self, 'missing', None)):
            missing = self.missing
        # TODO: use async too
        if sync:
            return self.router.sync_dispatch(self.req.url, root=root, missing=missing)
        return self.router.dispatch(self.req.url, root=root, missing=missing)

    def run(self, *, sync: bool = True):
        """Run plugin. Dispatch url. Use sync=False to run asyncio."""
        try:
            res = self.dispatch(sync=sync)
        finally:
            self.user_data.save()
        return res

    @contextmanager
    def directory(self, *, safe: bool = False, **kwargs):
        kd = AddonDirectory(addon=self, **kwargs)
        try:
            yield kd
        except Exception as exc:
            kd.close(False)
            if safe:
                log.error(f'Build directory exception: {exc!r}')
            else:
                raise
        else:
            kd.close(True)
        finally:
            pass

    def play_failed(self):
        """Notice, that play failed."""
        item = xbmcgui.ListItem()
        xbmcplugin.setResolvedUrl(self.handle, False, listitem=item)


class Plugin(Addon):
    """
    Abstract Libka Addon. Plugin is kind of Addon.
    """


class LibkaTheAddon(AddonMixin, metaclass=SingletonMetaclass):
    """
    Libka addon itself.
    """

    def __init__(self):
        super().__init__(id=LIBKA_ID)
