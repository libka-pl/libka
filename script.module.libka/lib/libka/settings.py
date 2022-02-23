"""
Module handles Kodi settings in nice interface. Settings caches set and read values.

Main class `Settings` hold whole API. It's built in `Addon` and any class that inherits from it
like `Plugin`, `SimpleAddon`, `SimplePlugin`. Just use `self.settings.my_key` in your plugin class
for access to `my_key` setting.
"""

from collections.abc import Sequence
from collections import namedtuple
from typing import (
    TYPE_CHECKING,
    Any, Callable,
    Dict, Tuple,
)
from .logs import log
from .routing import entry
from .lang import L
if TYPE_CHECKING:
    from .addon import Addon
    from xbmcaddon import Settings as XmbcSettings
    from xmbcaddon import Addon as XbmcAddon


class MISSING:
    """Helper. Type to mark as missing."""


class Settings:
    """
    Proxy to Kodi (XMBC) settings.

    Parameters
    ----------
    addon: Addon or None
        Libka Addon instance or None.

    This class has own methods and all methods from `xbmcplugin.Addon`
    and `xbmcplugin.Setting` (since Kodi 20).

    To get settings use `get()`. To set use `set()`.
    Both methods handle type auto-conversion.
    Reading missing key returns `default` value (`None` is omitted).

    Keyword access `[key]` uses `get()` and `set()` methods.
    Reading missing key raises `KeyError`.

    Attribute access `.key` uses `get()` and `set()` methods.
    Reading missing key raises `AttributeError`.

    Delete keyword or attribute or `set(None)` sets empty string.

    If `addon` is `None` the Settings uses `xbmcaddon.Addon().Settings()` directly.
    Should be avoided.

    **Note.** Preferred access method is by attribute: `settings.key`.

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

    def __init__(self, *, addon: 'Addon' = None):
        if addon is None:
            from xmbcaddon import Addon as XbmcAddon
            self._xbmc_addon: XbmcAddon = XbmcAddon()
        else:
            self._xbmc_addon: 'XbmcAddon' = addon.xbmc_addon
        self._addon: 'Addon' = addon
        try:
            # since Kodi 20
            self._xbmc: 'XmbcSettings' = self._xbmc_addon.getSettings()
        except AttributeError:
            self._xbmc: 'XmbcSettings' = None
        self._data: Dict[str, Any] = {}
        if self._xbmc is None:
            self._xbmc_setters: Dict[Type, Tuple[Callable, Callable]] = {}
        else:
            self._xbmc_setters: Dict[Type, Tuple[Callable, Callable]] = {
                #       value-setter          list-setter
                bool:  (self._xbmc.setBool,   self._xbmc.setBoolList),
                int:   (self._xbmc.setInt,    self._xbmc.setIntList),
                float: (self._xbmc.setNumber, self._xbmc.setNumberList),
            }

    def __repr__(self):
        addon = '' if self._addon is None else repr(self._addon)
        return f'Settings({addon})'

    def _get(self, key: str, default: Any = None, type: str = 'string') -> Any:
        """Helper. Get setting form cache or from XBMC (and set cache)."""
        try:
            return self._data[key]
        except KeyError:
            pass
        if self._xbmc is None:
            # till K19 (inclusive)
            type = type.capitalize()
            if type == 'String' or type.endswith('List'):
                type = ''
            getter = getattr(self._xbmc_addon, f'getSetting{type}')
        else:
            # since K20
            type = type.capitalize()
            getter = getattr(self._xbmc, f'get{type}')
        log.debug(f'_get({key!r}, {default!r}, {type!r}): getter={getter!r}')
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

        # K20 support, detect `value` type
        if self._xbmc is not None:
            if value is None:
                return self._xbmc.setString('')
            setter = self._xbmc_setters.get(type(value))
            if setter:
                return setter[0](key, value)
            if isinstance(value, bytes):
                value = value.decode('utf-8')
            if not isinstance(value, str):
                if value and isinstance(value, Sequence):  # list of...
                    v0 = value[0]
                    setter = self._xbmc_setters.get(type(v0))
                    if setter:
                        return setter[1](key, value)
                    if isinstance(v0, str):
                        return self._xbmc.setStringtList(key, value)
                    return self._xbmc.setStringtList(key, [str(v) for v in value])
                value = str(value)
            return self._xbmc.setStringt(key, value)

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
        if self._xbmc is not None:
            return self._xbmc.getString(key)
        return self._get(key, default)

    def set_string(self, key: str, value: str) -> bool:
        """
        Sets a string (`str`) value of a setting. Bytes are decoded as utf-8.

        Returns true if the value of the setting was set, false otherwise.
        """
        if isinstance(value, bytes):
            value = value.decode('utf-8')
        if self._xbmc is not None:
            return self._xbmc.setString(key, value)
        return self.set(key, value)

    def get_bool(self, key: str, default: bool = None) -> bool:
        """Gets the value of a setting as a boolean (`bool`)."""
        if self._xbmc is not None:
            return self._xbmc.getBool(key)
        return self._get(key, default).lower() == 'true'

    def set_bool(self, key: str, value: bool) -> bool:
        """
        Sets a boolean (`bool`) value of a setting.

        Returns true if the value of the setting was set, false otherwise.
        """
        if self._xbmc is not None:
            return self._xbmc.setBool(key, bool(value))
        return self.set(key, bool(value))

    def get_int(self, key: str, default: int = None) -> int:
        """Gets the value of a setting as an integer (`int`)."""
        if self._xbmc is not None:
            return self._xbmc.getInt(key)
        value = self._get(key, default)
        if value == '':
            value = default
        return int(value)

    def set_int(self, key: str, value: int) -> bool:
        """
        Sets an integer (`int`) value of a setting.

        Returns true if the value of the setting was set, false otherwise.
        """
        if self._xbmc is not None:
            return self._xbmc.setInt(key, value)
        return self.set(key, int(value))

    def get_float(self, key: str, default: float = None) -> float:
        """Gets the value of a setting as a floating point number (`float`)."""
        if self._xbmc is not None:
            return self._xbmc.getNumber(key)
        return float(self._get(key, default))

    def set_float(self, key: str, value: float) -> bool:
        """
        Sets a floating point number (`float`) value of a setting.

        Returns true if the value of the setting was set, false otherwise.
        """
        if self._xbmc is not None:
            return self._xbmc.setNumber(key, value)
        return self.set(key, float(value))

    @entry(label=L(32301, 'Settings'))
    def __call__(self):
        """Call opens a settings dialog."""
        self._xbmc_addon.openSettings()

    def __getitem__(self, key):
        value = self.get(key, MISSING)
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
            try:
                return getattr(self._xbmc, key)
            except AttributeError:
                pass
        try:
            return getattr(self._xbmc_addon, key)
        except AttributeError:
            pass
        value = self.get(key, MISSING)
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
