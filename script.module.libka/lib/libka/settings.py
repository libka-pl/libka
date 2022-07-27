"""
Module handles Kodi settings in nice interface. Settings caches set and read values.

Main class `Settings` hold whole API. It's built in `Addon` and any class that inherits from it
like `Plugin`, `SimpleAddon`, `SimplePlugin`. Just use `self.settings.my_key` in your plugin class
for access to `my_key` setting.
"""

import re
from collections.abc import Sequence
from collections import namedtuple
from typing import (
    TYPE_CHECKING,
    Any, Union, Callable, Type,
    Dict, List, Tuple,
)
from .logs import log
from .routing import entry
from .lang import L
from .format import stylize
from .tools import adict
if TYPE_CHECKING:
    from .addon import Addon
    from xbmcaddon import Settings as XbmcSettings
    from xbmcaddon import Addon as XbmcAddon


#: Split regex for settings style value list.
re_style_split = re.compile(r'(?<!\\);')
#: Replace escape sequences in settings style value.
re_style_unescape = re.compile(r'\\([:;,.$\\])')
#: Escape settings style value (on style writting).
re_style_escape = re.compile(r'[;\\]')


class MISSING:
    """Helper. Type to mark as missing."""


class Settings:
    """
    Proxy to Kodi (XBMC) settings.

    Parameters
    ----------
    addon: Addon or None
        Libka Addon instance or None.
    default: Any
        Default value for keyword access `[key]` and attribute access `.key`.

    This class has own methods and all methods from:

    - `xbmcplugin.Addon` – for all helper methods,
    - `xbmcplugin.Setting` (since Kodi 20) – for new API only.

    To get settings use `get()`. To set use `set()`.
    Both methods handle type auto-conversion.
    Reading missing key returns `default` value (`None` is omitted).

    Keyword access `[key]` uses `get()` and `set()` methods.
    Reading missing key raises `KeyError`.
    It can be changed by `Settings.set_default_value()`.

    Attribute access `.key` uses `get()` and `set()` methods.
    Reading missing key raises `AttributeError`.
    It can be changed by `Settings.set_default_value()`.

    Delete keyword or attribute or `set(None)` sets empty string.

    If `addon` is `None` the Settings uses `xbmcaddon.Addon().Settings()` directly.
    Should be avoided.

    **Note.** Preferred access method is by attribute: `settings.key`.

    **Note.** `libka.addon.Addon` creates instance of `Settings` with `None` as `default`.

    Example.
    >>> class MyPluguin(SimplePlugin):
    >>>     def foo(self):
    >>>         self.settings.my_settings = 0.5
    >>>         assert self.settings.my_settings == 0.5
    >>>         assert self.settings['my_settings'] == 0.5
    >>>         assert self.settings.get('my_settings', 1.2) == 0.5
    >>>         assert self.settings.get('no_settings', 1.2) == 1.2
    >>>         assert self.settings.get_float('my_settings') == 0.5
    >>>         assert self.settings.get_string('my_settings') == '0.5'
    """

    def __init__(self, *, addon: 'Addon' = None, default: Any = MISSING):
        if addon is None:
            from xbmcaddon import Addon as XbmcAddon  # noqa F811
            self._xbmc_addon: XbmcAddon = XbmcAddon()
        else:
            self._xbmc_addon: 'XbmcAddon' = addon.xbmc_addon
        self._addon: 'Addon' = addon
        try:
            # since Kodi 20
            self._xbmc: 'XbmcSettings' = self._xbmc_addon.getSettings()
        except AttributeError:
            from .kodi import Settings as XbmcSettings  # noqa F811
            self._xbmc: 'XbmcSettings' = XbmcSettings(xbmc_addon=self._xbmc_addon)
        self._data: Dict[str, Any] = {}
        self._default = default

    def __repr__(self):
        addon = '' if self._addon is None else repr(self._addon)
        return f'Settings({addon})'

    def set_default_value(self, default: Any) -> None:
        """
        Set default value to use in attribute access `.key` and
        keyword access `[key]`. This allows to avoid raise exceptions
        in those access methods.
        """
        self._default = default

    def _get(self, key: str, default: Any = None, type: str = 'string') -> Any:
        """Helper. Get setting form cache or from XBMC (and set cache)."""
        try:
            return self._data[key]
        except KeyError:
            pass
        type = type.capitalize()
        if type == 'String' or type.endswith('List'):
            type = ''
        getter = getattr(self._xbmc_addon, f'getSetting{type}')
        log.xdebug(f'_get({key!r}, {default!r}, {type!r}): getter={getter!r}')
        try:
            value = getter(key)
        except Exception:
            value = default
        self._data[key] = value
        return value

    def get(self, key: str, default: Any = None) -> Any:
        """
        Gets setting and guess a type.

        Parameters
        ----------
        key: str
            Settings ID.
        default: Any
            Default value. Used if there is no `key` settings.

        Returns
        -------
        bool
            if value is "true" or "false" (case-insensitive)
        int
            if could be converted to integer
        float
            if could be converted to floating point number
        str
            otherwise

        This method is used also on keyword access `settings[key]`
        and attribute access `settings.key`.
        """
        value = self._get(key, default=default)
        if value is MISSING:
            return value
        if isinstance(value, str):
            if not value and default is not None and not isinstance(default, str):
                return default
            if value.lower() == 'false':
                return False
            if value.lower() == 'true':
                return True
        for typ in (int, float):
            try:
                return typ(value)
            except (ValueError, TypeError):
                pass
        return value

    def set(self, key: str, value: Any) -> bool:
        """
        Set setting. Convert to string.

        Returns true if the value of the setting was set, false otherwise.
        """
        log.debug(f'Settings.set({key!r}, {value!r})')
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
        return self._xbmc_addon.setSetting(key, value)

    def get_string(self, key: str, default: str = None) -> str:
        """Gets the value of a setting as a unicode string (`str`)."""
        return self._get(key, default)

    def set_string(self, key: str, value: str) -> bool:
        """
        Sets a string (`str`) value of a setting. Bytes are decoded as utf-8.

        Returns true if the value of the setting was set, false otherwise.
        """
        if isinstance(value, bytes):
            value = value.decode('utf-8')
        return self.set(key, value)

    def get_bool(self, key: str, default: bool = None) -> bool:
        """Gets the value of a setting as a boolean (`bool`)."""
        return self._get(key, default).lower() == 'true'

    def set_bool(self, key: str, value: bool) -> bool:
        """
        Sets a boolean (`bool`) value of a setting.

        Returns true if the value of the setting was set, false otherwise.
        """
        return self.set(key, bool(value))

    def get_int(self, key: str, default: int = None) -> int:
        """Gets the value of a setting as an integer (`int`)."""
        value = self._get(key, default)
        if value == '':
            value = default
        return int(value)

    def set_int(self, key: str, value: int) -> bool:
        """
        Sets an integer (`int`) value of a setting.

        Returns true if the value of the setting was set, false otherwise.
        """
        return self.set(key, int(value))

    def get_float(self, key: str, default: float = None) -> float:
        """Gets the value of a setting as a floating point number (`float`)."""
        return float(self._get(key, default))

    def set_float(self, key: str, value: float) -> bool:
        """
        Sets a floating point number (`float`) value of a setting.

        Returns true if the value of the setting was set, false otherwise.
        """
        return self.set(key, float(value))

    @entry(label=L(32301, 'Settings'))
    def __call__(self):
        """Call opens a settings dialog."""
        self._xbmc_addon.openSettings()

    def __getitem__(self, key):
        value = self.get(key, self._default)
        if value is MISSING:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value):
        self.set(key, value)

    def __delitem__(self, key: str, value):
        self.set(key, None)

    def __getattr__(self, key):
        """Get unknown attribute. Try xbmcplugin.Settings, xbmcplugin.Addon, read setting."""
        if key.startswith('_'):
            raise AttributeError(key)
        if self._xbmc is not None:
            # access to new K20 Kodi-settings API
            try:
                return getattr(self._xbmc, key)
            except AttributeError:
                pass
        # access to old Kodi-settings API
        try:
            return getattr(self._xbmc_addon, key)
        except AttributeError:
            pass
        # access to value
        value = self.get(key, self._default)
        if value is MISSING:
            raise AttributeError(key)
        return value

    def __setattr__(self, key: str, value):
        if key.startswith('_'):
            super(Settings, self).__setattr__(key, value)
        else:
            self.set(key, value)

    def __delattr__(self, key):
        if key.startswith('_'):
            super(Settings, self).__delattr__(key)
        else:
            self.set(key, None)

    def get_style(self, name: str):
        """Get style from settings."""
        return [re_style_unescape.sub(r'\1', val)
                for val in re_style_split.split(self.get_string(f'{name}_style_value'))]

    def set_style(self, name: str, style: Union[str, List[str]]):
        """Set style value and preview."""
        if isinstance(style, str):
            style = [style]
        # value (semicolon separated list)
        val = ';'.join(re_style_escape.sub(r'\\\1', s) for s in style)
        self.set_string(f'{name}_style_value', val)
        # preview
        self.set_string(f'{name}_style_preview', stylize('ABC', style))

    def get_styles(self, *names):
        """Get the styles and return `adict`."""
        return adict((name, self.get_style(name)) for name in names)
