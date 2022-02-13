import sys
import re
from contextlib import contextmanager
from typing import (
    overload,
    Union, Optional, Callable, Any,
    Tuple,
)
from .utils import parse_url
from .settings import Settings
from .logs import log
from .resources import Resources
from .folder import AddonDirectory
from .routing import Router, subobject, entry
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
        #: Router
        self.router = router
        if self.router is None:
            plugin_link = f'{self.req.url.scheme or "plugin"}://{self.id}'
            self.router = Router(plugin_link, obj=self, addon=self, standalone=False)
        # XMBC (Kodi) Addon
        # self.xbmc_addon = XbmcAddon(id=self.id)
        self.xbmc_addon = XbmcAddon()
        #: Addon settings.
        self.settings = Settings(self)
        #: Defined routes.
        self._routes = []
        #: User defined colors used in "[COLOR :NAME]...[/COLOR]"
        self.colors = {
            'gray': 'gray',
            'grey': 'gray',
        }
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

    @overload
    def mkentry(self, endpoint: Union[Callable, str]) -> Tuple[str, str]:
        ...

    @overload
    def mkentry(self, title: str, endpoint: Callable) -> Tuple[str, str]:
        ...

    def mkentry(self, title, endpoint=None):
        """Helper. Returns (title, url) for given endpoint."""
        return self.router.mkentry(title, endpoint)

    def mkurl(self, endpoint: Union[str, Callable], *args, **kwargs) -> str:
        """
        Create plugin URL to given name/method with arguments.
        """
        return self.router.mkurl(endpoint, *args, **kwargs)

    url_for = mkurl

    def dispatch(self, *, root: Optional[Callable] = None, missing: Optional[Callable] = None) -> Any:
        """
        Dispatcher. Call pointed method with request arguments.
        """
        if root is None and callable(getattr(self, 'home', None)):
            root = self.home
        if missing is None and callable(getattr(self, 'missing', None)):
            missing = self.missing
        # TODO: use async too
        return self.router.sync_dispatch(self.req.url, root=root, missing=missing)

    def run(self):
        """Run plugin. Dispatch url."""
        return self.dispatch()

    @contextmanager
    def directory(self, *, safe: Optional[bool] = False, **kwargs):
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

    def translate_title(self, text):
        def get_color(m):
            return '[COLOR %s]' % self.get_color(m.group(1))

        text = self._RE_TITLE_COLOR.sub(get_color, text)
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
