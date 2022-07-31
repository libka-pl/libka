from __future__ import annotations

from collections import namedtuple
import xbmc
# traversal modules (ready to monkey-pathing)
import xbmcvfs
import xbmcaddon
import xbmcdrm
import xbmcgui
import xbmcplugin


version_info_type = namedtuple('version_info_type', 'major minor build')
version_info_type.__new__.__defaults__ = 2*(0,)


def get_kodi_version_info():
    """Return major kodi version as int."""
    default = '19'
    ver = xbmc.getInfoLabel('System.BuildVersion') or default
    ver = ver.partition(' ')[0].split('.', 3)[:3]
    return version_info_type(*(int(v.partition('-')[0]) for v in ver))


version_info = get_kodi_version_info()

version = version_info.major + (version_info.minor >= 90)

K18 = ((17, 9, 910) <= version_info < (18, 9, 701))
K19 = ((18, 9, 701) <= version_info < (19, 90))
K20 = ((19, 90) <= version_info < (20, 90))
K21 = ((20, 90) <= version_info < (21, 90))


if version < 20:

    import json

    class Settings:
        """
        New K20 kodi settings API for older kodi (K19).

        This light implementation does not check `resource/settigns.xml`
        there is no type checking.

        See: https://alwinesch.github.io/group__python__settings.html

        Todos:
            * Add `resource/settigns.xml` type parse.
        """

        def __init__(self, *, xbmc_addon: xbmcaddon.Addon = None):
            if xbmc_addon is None:
                xbmc_addon = xbmcaddon.Addon()
            self._addon: xbmcaddon.Addon = xbmc_addon

        def getBool(self, id: str) -> bool:
            """
            Returns the value of a setting as a boolean.

            Parameters
            ----------

            id : str
                id of the setting that the module needs to access.

            Returns
            -------
            bool
                setting as a boolean.
            """
            return self._addon.getSetting(id).lower() == 'true'

        def setBool(self, id: str, value: bool) -> bool:
            """
            Sets the value of a setting.

            Parameters
            ----------

            id : str
                id of the setting that the module needs to access.
            value : bool
                value of the setting.

            Returns
            -------
            bool
                true if the value of the setting was set, false otherwise.
            """
            value = 'true' if value else 'false'
            return self._addon.setSetting(id, value)

        def getInt(self, id: str) -> int:
            """
            Returns the value of a setting as an integer.

            Parameters
            ----------

            id : str
                id of the setting that the module needs to access.

            Returns
            -------
            int
                setting as an integer.
            """
            return int(self._addon.getSetting(id))

        def setInt(self, id: str, value: int) -> bool:
            """
            Sets the value of a setting.

            Parameters
            ----------

            id : str
                id of the setting that the module needs to access.
            value : int
                value of the setting.

            Returns
            -------
            bool
                true if the value of the setting was set, false otherwise.
            """
            return self._addon.setSetting(id, str(value))

        def getNumber(self, id: str) -> float:
            """
            Returns the value of a setting as a floating point number.

            Parameters
            ----------

            id : str
                id of the setting that the module needs to access.

            Returns
            -------
            int
                setting as a floating point number.
            """
            return int(self._addon.getSetting(id))

        def setNumber(self, id: str, value: float) -> bool:
            """
            Sets the value of a setting.

            Parameters
            ----------

            id : str
                id of the setting that the module needs to access.
            value : int
                value of the setting.

            Returns
            -------
            bool
                true if the value of the setting was set, false otherwise.
            """
            return self._addon.setSetting(id, str(value))

        def getString(self, id: str) -> str:
            """
            Returns the value of a setting as a unicode string.

            Parameters
            ----------

            id : str
                id of the setting that the module needs to access.

            Returns
            -------
            str
                setting as a unicode string.
            """
            return int(self._addon.getSetting(id))

        def setString(self, id: str, value: str) -> bool:
            """
            Sets the value of a setting.

            Parameters
            ----------

            id : str
                id of the setting that the module needs to access.
            value : int
                value of the setting.

            Returns
            -------
            bool
                true if the value of the setting was set, false otherwise.
            """
            if isinstance(value, bytes):
                value = value.decode('utf-8')
            return self._addon.setSetting(id, value)

        def getBoolList(self, id: str) -> list[bool]:
            """
            Returns the value of a setting as a boolean.

            Parameters
            ----------

            id : str
                id of the setting that the module needs to access.

            Returns
            -------
            bool
                setting as a boolean.
            """
            return json.loads(self._addon.getSetting(id))

        def setBoolList(self, id: str, values: list[bool]) -> bool:
            """
            Sets the value of a setting.

            Parameters
            ----------

            id : str
                id of the setting that the module needs to access.
            values : list of bool
                value of the setting.

            Returns
            -------
            bool
                true if the value of the setting was set, false otherwise.
            """
            values = ['true' if v else 'false' for v in values]
            return self._addon.setSetting(id, json.dumps(values))

        def getIntList(self, id: str) -> list[int]:
            """
            Returns the value of a setting as an integer.

            Parameters
            ----------

            id : str
                id of the setting that the module needs to access.

            Returns
            -------
            int
                setting as an integer.
            """
            return json.loads(self._addon.getSetting(id))

        def setIntList(self, id: str, values: list[int]) -> bool:
            """
            Sets the value of a setting.

            Parameters
            ----------

            id : str
                id of the setting that the module needs to access.
            values : list of int
                value of the setting.

            Returns
            -------
            bool
                true if the value of the setting was set, false otherwise.
            """
            return self._addon.setSetting(id, json.dumps(values))

        def getNumberList(self, id: str) -> list[float]:
            """
            Returns the value of a setting as a floating point number.

            Parameters
            ----------

            id : str
                id of the setting that the module needs to access.

            Returns
            -------
            int
                setting as a floating point number.
            """
            return json.loads(self._addon.getSetting(id))

        def setNumberList(self, id: str, values: list[float]) -> bool:
            """
            Sets the value of a setting.

            Parameters
            ----------

            id : str
                id of the setting that the module needs to access.
            values : list of int
                value of the setting.

            Returns
            -------
            bool
                true if the value of the setting was set, false otherwise.
            """
            return self._addon.setSetting(id, json.dumps(values))

        def getStringList(self, id: str) -> list[str]:
            """
            Returns the value of a setting as a unicode string.

            Parameters
            ----------

            id : str
                id of the setting that the module needs to access.

            Returns
            -------
            str
                setting as a unicode string.
            """
            return json.loads(self._addon.getSetting(id))

        def setStringList(self, id: str, values: list[str]) -> bool:
            """
            Sets the value of a setting.

            Parameters
            ----------

            id : str
                id of the setting that the module needs to access.
            values : list of int
                value of the setting.

            Returns
            -------
            bool
                true if the value of the setting was set, false otherwise.
            """
            return self._addon.setSetting(id, json.dumps(values))

    class Addon(xbmcaddon.Addon):
        """
        Creates a new AddOn class.

        Parameters
        ----------
        id : [opt] string
            id of the addon as specified in addon.xml

        Notes:
            * Specifying the addon id is not needed.
            * Important however is that the addon folder has the same name as the AddOn id provided in addon.xml.
            * You can optionally specify the addon id from another installed addon to retrieve settings from it.
        """

        def getSettings(self):
            """
            Returns a wrapper around the addon's settings.

            Settings
                Settings wrapper.
            """
            return Settings(xbmc_addon=self)

    xbmcaddon.Addon = Addon
