"""
Simple Kodi addon framework to make all dirty work.

.. include:: ../../../doc/en/introduction.md
"""

import sys
import os.path
import os
from kover import autoinstall  # noqa: F401

#: Libka version.
__version__ = '0.0.26'

# Support for remote `breakpoint()`.
os.environ.setdefault('PYTHONBREAKPOINT', 'remote_pdb.set_trace')
os.environ.setdefault('REMOTE_PDB_HOST', '0.0.0.0')
os.environ.setdefault('REMOTE_PDB_PORT', '4444')

# Add paths to 3rd-party libs
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '3rd'))

# Enable kodi-specific url schemes in utllib.parse.
from .tools import add_url_scheme  # noqa E402
add_url_scheme(['plugin', 'special', 'library', 'script'])

from .addon import Addon, Plugin   # noqa E402
from .libka import libka           # noqa E402
from .script import Script         # noqa E402
from .site import Site, SiteMixin  # noqa E402
from .kodi import K19, K20         # noqa E402
from .routing import (             # noqa E402
    call, entry, subobject,
    PathArg, RawArg, SafeQuoteStr,
)
from .lang import get_label_getter  # noqa E402
from .search import search          # noqa E402
from .logs import log               # noqa E402


#: Plugin / addon language label.
L = get_label_getter()


class SimpleAddon(SiteMixin, Plugin):
    pass


class SimplePlugin(SiteMixin, Plugin):
    pass


__all__ = ['K19', 'K20', 'libka', 'Script', 'Addon', 'Plugin', 'SimpleAddon', 'SimplePlugin', 'Site', 'SiteMixin',
           'call', 'entry', 'subobject', 'PathArg', 'RawArg', 'L', 'log']
