# -*- coding: utf-8 -*-

"""
Nothing to do. All job are done in __init__.py.

Remeber, every you file must start with:

# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals, print_function
from future.utils import PY2, python_2_unicode_compatible
if PY2:
    from builtins import *  # dirty hack, force py2 to be like py3
import kodi.future


And every class must be decorated:

@python_2_unicode_compatible
class MyClass(object):
    pass

Than write in Python3 style, except Python2 syntax issues like:

    - f-strings are not avaliavle, can NOT use f'{key} = {value!r}'

    - function's positional list can NOT be mixed with keyword arguments, ex.
      fun(*arg, kw=None, **kwargs)
      Use **kwargs and kwargs.pop('kw').
"""
