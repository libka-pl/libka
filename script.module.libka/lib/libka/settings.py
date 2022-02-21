from collections import namedtuple
# from kodi_six import xbmcplugin

from .logs import flog  # DEBUG,  TODO: remove it
from .routing import entry
from .lang import L


Call = namedtuple('Call', 'method args')

EndpointEntry = namedtuple('EndpointEntry', 'path title')


class MISSING:
    """Internal. Type to mark as missing."""


class Settings:
    """
    Proxy to Kodi (XMBC) settings.

    Settings(addon)

    - addon   - KodiPL Addon instance

    This class has own methods and all methods from xbmcplugin.Addon
    and xbmcplugin.Setting (since Kodi 20).

    To get settgins use get() ot get_auto(). To set use set().

    Keywoard access [key] uses get() and set().
    Attrubute access .key uses get_auto() and set().
    """

    def __init__(self, addon):
        self._addon = addon
        try:
            # since Kodi 20
            self._xbmc = self._addon.xbmc_addon.getSettings()
        except AttributeError:
            self._xbmc = None
        self._data = {}

    def __repr__(self):
        return 'Settings()'

    def _get(self, key, default=None, type='string'):
        """Get setting."""
        try:
            return self._data[key]
        except KeyError:
            pass
        if self._xbmc is None:
            # till K19 (inclusive)
            type = type.capitalize()
            if type == 'String' or type.endswith('List'):
                type = ''
            getter = getattr(self._addon.xbmc_addon, 'getSetting{}'.format(type))
        else:
            # since K20
            type = type.capitalize()
            getter = getattr(self._xbmc, 'get{}'.format(type))
        flog('_get({key!r}, {default!r}, {type!r}): getter={getter!r}')
        value = getter(key)
        self._data[key] = value
        return value

    def get(self, key, default=None):
        """Get setting."""
        try:
            return self._data[key]
        except KeyError:
            pass
        value = self._addon.xbmc_addon.getSetting(key)
        self._data[key] = value
        return value

    def set(self, key, value):
        """Set setting. Convert to string."""
        flog('Settings.set({key!r}, {value!r})...')
        if value is None:
            value = ''
        elif value is False:
            value = 'false'
        elif value is True:
            value = 'true'
        elif isinstance(value, bytes):
            value = value.decode('utf-8')
        elif not isinstance(value, str):
            value = str(value)
        self._data[key] = value
        flog('   ----> {value!r}')
        return self._addon.xbmc_addon.setSetting(key, value)

    def get_auto(self, key, default=None):
        """Get setting and guess a type."""
        value = self.get(key)
        if value.lower() == 'false':
            return False
        if value.lower() == 'true':
            return True
        for typ in (int, float):
            try:
                return typ(value)
            except ValueError:
                pass
        return value

    def get_bool(self, key, default=None):
        return self.get(key, default).lower() == 'true'

    def set_bool(self, key, value):
        return self.set(key, bool(value))

    def get_int(self, key, default=None):
        value = self.get(key, default)
        if value == '':
            value = default
        return int(value)

    def set_int(self, key, value):
        return self.set(key, int(value))

    def get_float(self, key, default=None):
        return float(self.get(key, default))

    def set_float(self, key, value):
        return self.set(key, float(value))

    @entry(label=L(32301, 'Settings'))
    def __call__(self):
        """Call opens a settings dialog."""
        self._addon.xbmc_addon.openSettings()

    def __getitem__(self, key):
        value = self.get(key, MISSING)
        if value is MISSING:
            raise AttributeError(key)
        return value

    def __setitem__(self, key, value):
        self.set(key, value)

    def __delitem__(self, key, value):
        self.set(key, None)

    def __getattr__(self, key):
        """Get unknown attribute. Try xbmcplugin.Settings, xbmcplugin.Addon, read setting."""
        if key.startswith('_'):
            raise AttributeError(key)
        if self._xbmc is not None:
            try:
                return getattr(self._xbmc, key)
            except AttributeError:
                pass
        try:
            return getattr(self._addon.xbmc_addon, key)
        except AttributeError:
            pass
        value = self.get_auto(key, MISSING)
        if value is MISSING:
            raise AttributeError(key)
        return value

    def __setattr__(self, key, value):
        if key.startswith('_'):
            super(Settings, self).__setattr__(key, value)
        else:
            self.set(key, value)

    def __delattr__(self, key):
        if key.startswith('_'):
            super(Settings, self).__delattr__(key)
        else:
            self.set(key, None)
