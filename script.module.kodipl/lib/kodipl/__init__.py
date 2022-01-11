# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals, print_function

import sys
import os.path

__version__ = '0.0.2'


# Add paths to 3rd-party libs
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '3rd'))


from .addon import Addon, Plugin
from .site import Site
from .kodi import K19, K20


class SimpleAddon(Site, Plugin):
    pass


class SimplePlugin(Site, Plugin):
    pass


__all__ = ['Addon', 'K19', 'K20', 'Plugin', 'SimpleAddon', 'SimplePlugin', 'Site']
