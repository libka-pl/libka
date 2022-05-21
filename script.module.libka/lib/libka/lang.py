
from typing import overload, Optional, Dict
from datetime import datetime, timedelta
from .base import LIBKA_ID
from xbmcaddon import Addon


_label_getters: Dict[str, Addon] = {}


class LabelGetter:
    """
    Simple label string getter (like getLocalizedString) for given addon ID.
    """

    def __init__(self, id=None):
        self.id = id
        self.addon = Addon() if self.id is None else Addon(self.id)

    @overload
    def getter(self, id: int, string: str):
        ...

    @overload
    def getter(self, id: int, string: str):
        ...

    def getter(self, *args):
        """
        L(). Get localized string. If there is no ID there string is returned without translation.
        """
        if len(args) == 2:
            sid, text = args
        elif len(args) == 1:
            if isinstance(args[0], int):
                sid, text = args[0], None
            else:
                sid, text = None, args[0]
        else:
            raise TypeError(f'L{args} – incorrect arguments')
        if sid:
            return self.addon.getLocalizedString(sid)
        return text


def get_label_getter(id=None):
    """
    Return label string getter (like getLocalizedString) for given addon ID.
    """
    try:
        return _label_getters[id].getter
    except KeyError:
        _label_getters[id] = getter = LabelGetter(id)
    return getter.getter


#: Language label getter (translation) for "libka" itself.
L = get_label_getter(LIBKA_ID)


#: some basic phrases to translate
text = type('Text', (), {})
text.ok = L(32201, 'OK')
text.yes = L(32202, 'Yes')
text.no = L(32203, 'No')
text.close = L(32204, 'Close')
text.cancel = L(32205, 'Cancel')
text.applay = L(32206, 'Apply')
text.settings = L(32301, 'Settings')
text.search = L(32302, 'Search')
text.options = L(32330, 'Options')
text.login = L(32331, 'Login')
text.logout = L(32332, 'Logout')

text.today = L(32327, "Today")
text.tomorrow = L(32328, "Tomorrow")
text.yesterday = L(32329, "Yesterday")
text.days = [L(32308, 'Monday'), L(32309, 'Tuesday'), L(32310, 'Wednesday'),
             L(32311, 'Thursday'), L(32312, 'Friday'), L(32313, 'Saturday'), L(32314, 'Sunday')]
text.isodays = [L(32314, 'Sunday'), L(32308, 'Monday'), L(32309, 'Tuesday'), L(32310, 'Wednesday'),
                L(32311, 'Thursday'), L(32312, 'Friday'), L(32313, 'Saturday'), L(32314, 'Sunday')]
text.months = [L(32315, 'January'), L(32316, 'February'), L(32317, 'March'),
               L(32318, 'April'), L(32319, 'May'), L(32320, 'June'),
               L(32321, 'July'), L(32322, 'August'), L(32323, 'September'),
               L(32324, 'October'), L(32325, 'November'), L(32326, 'December')]


def day_label(dt: datetime, *, now: Optional[datetime] = None) -> str:
    """Returns nice date label (today, Monday, 11.12.2013)."""
    if now is None:
        now = datetime.now
    if now.date() == dt.date():
        return L(32327, 'Today')
    if (now + timedelta(days=1)).date() == dt.date():
        return L(32328, 'Tomorrow')
    if (now - timedelta(days=1)).date() == dt.date():
        return L(32329, 'Yesterday')
    return f'{text.days[dt.weekday()]}, {dt:%d.%m.%Y}'
