# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals, print_function
from future.utils import PY2
if PY2:
    from builtins import *  # dirty hack
from future.utils import python_2_unicode_compatible, text_type, binary_type

from collections import namedtuple
from kodi_six import xbmcplugin


Call = namedtuple('Call', 'method args')

EndpointEntry = namedtuple('EndpointEntry', 'path title')


class MISSING:
    """Internal. Type to mark as missing."""


@python_2_unicode_compatible
class Settings(object):
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
        self.__name__ = 'settings'
        try:
            # since Kodi 20
            self._xbmc = self._addon.xbmc_addon.getSettings()
        except AttributeError:
            self._xbmc = None
        self._data = {}

    def __repr__(self):
        return 'Settings()'
        # return 'Settings(Addon(%r))' % self._addon.id

    def get(self, key, default=None):
        """Get setting."""
        try:
            return self._data[key]
        except KeyError:
            pass
        value = xbmcplugin.getSetting(self._addon.handle, key)
        self._data[key] = value
        return value

    def set(self, key, value):
        """Set setting. Convert to string."""
        if key is None:
            value = ''
        elif key is False:
            value = 'false'
        elif key is True:
            value = 'true'
        elif isinstance(value, binary_type):
            value = value.decode('utf-8')
        elif not isinstance(value, text_type):
            value = text_type(value)
        self._data[key] = value
        return xbmcplugin.setSetting(self._addon.handle, key, value)

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
        return self.get(key, default=default).lower() == 'true'

    def set_bool(self, key, value):
        return self.set(key, bool(value))

    def get_int(self, key, default=None):
        return int(self.get(key, default=default))

    def set_int(self, key, value):
        return self.set(key, int(value))

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
        self.set(key, '')

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
            self.set(key, '')