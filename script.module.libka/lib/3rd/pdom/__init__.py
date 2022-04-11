# -*- coding: utf-8 -*-
u"""
Read DBF files with Python.

Example:

    >>> import requests, pdom
    >>> with requests.Session() as sess:
    ...     for (link,), (logo,) in dom.select(sess.get('http://wizja.tv'), 'a[href*=watch](href) img(src)'):
    ...         print('url={link!r}, logo={logo!r}.format(link=link, logo=logo))
    url='watch.php?id=15', logo='ch_logo/elevensports1.png'
    url='watch.php?id=16', logo='ch_logo/elevensports2.png'
"""

from __future__ import absolute_import, division, unicode_literals, print_function

__author__ = "Robert Kalinowski"
__email__  = "robert.kalinowski@sharkbits.com"
__url__    = "https://github.com/rysson/pdom"

#try:
#    from future import standard_library
#    from future.builtins import *
#    standard_library.install_aliases()
#except ImportError:
#    print('WARNING: no furure module')

#import sys
#import re
#from collections import defaultdict
#from collections import namedtuple
#from inspect import isclass
#try:
#    from requests import Response
#except ImportError:
#    Response = None


#from .base import type_str, type_bytes, Enum
#from .base import AttrDict, RoAttrDictView
#from .base import NoResult, Result, MissingAttr, ResultParam
#from .base import regex, pats, remove_tags_re
#from .base import _tostr, _make_html_list, find_node
#from .base import Node, DomMatch
#from .base import aWord, aWordStarts, aStarts, aEnds, aContains

from .version import version_info, version as __version__

# low level serach
from .msearch import dom_search as search
# high level selector search
from .mselect import dom_select as select

# emulates https://kodi.wiki/view/Add-on:Parsedom_for_xbmc_plugins, MrKnow
from .backward import parseDOM
# emulates old CherryTV
from .backward import parse_dom

