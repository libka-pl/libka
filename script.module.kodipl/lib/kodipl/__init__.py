# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals, print_function

import sys
import os.path

__version__ = '0.0.1'


# Add paths to 3rd-party libs
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '3rd'))
if sys.version_info < (3, 0):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '3rdpy2'))

# Make aliases, most modules are located like in py3
from future import standard_library
standard_library.install_aliases()

# Missing aliases
if sys.version_info < (3, 0):
    import collections
    sys.modules['collections.abc'] = collections


from .addon import Addon, Plugin
from .site import Site
from .kodi import K18, K19, K20


class SimpleAddon(Site, Plugin):
    pass


class SimplePlugin(Site, Plugin):
    pass


__all__ = ['Addon', 'K18', 'K19', 'K20', 'Plugin', 'SimpleAddon', 'SimplePlugin', 'Site']
