import sys
import os.path

__version__ = '0.0.3'


# Add paths to 3rd-party libs
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '3rd'))


from .addon import Addon, Plugin  # noqa E402
from .site import Site            # noqa E402
from .kodi import K19, K20        # noqa E402
from .routing import (            # noqa E402
    call, entry, subobject,
    PathArg, RawArg,
)
from .lang import get_label_getter  # noqa E402
from .search import search          # noqa E402


L = get_label_getter()


class SimpleAddon(Site, Plugin):
    pass


class SimplePlugin(Site, Plugin):
    pass


__all__ = ['Addon', 'K19', 'K20', 'Plugin', 'SimpleAddon', 'SimplePlugin', 'Site',
           'call', 'entry', 'subobject', 'PathArg', 'RawArg', 'L']
