import sys
import re
from collections.abc import Sequence
from contextlib import contextmanager
from typing import (
    overload,
    Union, Optional, Callable, Any,
    List,
)
from .utils import parse_url
from .settings import Settings
from .search import Search
from .logs import log
from .resources import Resources
from .storage import Storage
from .folder import AddonDirectory
from .routing import Router, subobject, DirEntry, Call
from .commands import Commands
from .format import SafeFormatter
import xbmc
from xbmcaddon import Addon as XbmcAddon


class Request:
    """
    Addon call request.
    """

    def __init__(self, url, *, raw_keys=None):
        self.url = parse_url(url, raw=raw_keys)
        self.params = self.url.args
        # flog('XXXXX: argv: {sys.argv}')
        # flog('XXXXX: url:  {list(self.url)}')
        # flog('XXXXX: req={self.url}, link={self.url.link!r}, params={self.params!r}')


class Addon:
    """
    Abstract KodiPL Addon.

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

    _RE_TITLE_COLOR = re.compile(r'\[COLOR +:(\w+)\]')

    settings = subobject()
    search = subobject()

    def __init__(self, argv=None, router=None):
        if argv is None:
            argv = sys.argv
        if len(argv) < 3 or (argv[1] != '-1' and not argv[1].isdigit()) or (argv[2] and argv[2][:1] != '?'):
            raise TypeError('Incorrect addon args: %s' % argv)
        #: Addon handle (integer).
        self.handle = int(argv[1])
        #: Names for paramteres to encode raw Python data, don't use it.
        self.encoded_keys = {'_'}
        #: Kodi request to plugin://...
        self.req = Request(argv[0] + argv[2], raw_keys=self.encoded_keys)
        #: Addon ID (unique name)
        self.id = self.req.url.host
        #: XMBC (Kodi) Addon
        self.xbmc_addon = XbmcAddon()
        # Set default addon for Call formating.
        Call.addon = self
        #: Router
        self.router = router
        if self.router is None:
            plugin_link = f'{self.req.url.scheme or "plugin"}://{self.id}'
            self.router = Router(plugin_link, obj=self, addon=self, standalone=False)
        #: Kodi commands
        self.cmd = Commands(addon=self, mkurl=self.router.mkurl)
        #: Addon settings.
        self.settings = Settings(self)
        #: Addon default search.
        self.search = Search(self)
        #: Default userdata
        self.user_data = Storage(addon=self)
        #: Defined routes.
        self._routes = []
        #: User defined colors used in "[COLOR :NAME]...[/COLOR]"
        self.colors = {
            'gray': 'gray',
            'grey': 'gray',
        }
        #: Resources
        self.resources = Resources(self)
        #: Defualt dafe text formatter
        self.formatter = SafeFormatter(extended=True)

    def __repr__(self):
        return 'Addon(%r, %r)' % (self.id, str(self.req.url))

    def info(self, key):
        """Get XBMC addon info (like "path", "version"...)."""
        return self.xbmc_addon.getAddonInfo(key)

    @property
    def media(self):
        """Media resources."""
        return self.resources.media

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
        if root is None and callable(getattr(self, 'home', None)):
            root = self.home
        if missing is None and callable(getattr(self, 'missing', None)):
            missing = self.missing
        # TODO: use async too
        if sync:
            return self.router.sync_dispatch(self.req.url, root=root, missing=missing)
        return self.router.dispatch(self.req.url, root=root, missing=missing)

    def run(self, *, sync: bool = True):
        """Run plugin. Dispatch url. Use sync=False to run asyncio."""
        return self.dispatch(sync=sync)

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

    def get_color(self, name):
        return self.colors.get(name, 'gray')

    def format_title(self, text, style, n=0):
        def get_color(m):
            return '[COLOR %s]' % self.get_color(m.group(1))

        if style is not None:
            if not isinstance(style, str) and isinstance(style, Sequence):
                style = '%s{}%s' % (''.join(f'[{a}]' for a in style),
                                    ''.join(f'[/{a.split(None, 1)[0]}]' for a in reversed(style)))
            text = self.formatter.format(style, text, title=text, text=text, n=n, colors=self.colors)
        try:
            text = self._RE_TITLE_COLOR.sub(get_color, text)
        except TypeError:
            log.error(f'Incorect label/title type {type(text)}')
            raise
        return text

    def open_settings(self):
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


class Plugin(Addon):
    """
    Abstract KodiPL Addon. Plugin is kind of Addon.
    """
