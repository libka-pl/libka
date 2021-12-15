# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals, print_function
from future.utils import PY2, PY3
if PY2:
    from builtins import *  # dirty hack
import operator


import gzip
if not hasattr(gzip, 'compress'):
    from io import BytesIO

    def gzip_compress(data, compresslevel=9):
        """
        Missing gzip.compress implementation for older Python then 3.2.

        Compress the data, returning a bytes object containing
        the compressed data. compresslevel and mtime have the same
        meaning as in the GzipFile constructor above.
        """
        buf = BytesIO()
        with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=compresslevel) as f:
            f.write(data)
        return buf.getvalue()

    def gzip_decompress(data):
        """
        Missing gzip.decompress implementation for older Python then 3.2.

        Decompress the data, returning a bytes object containing the uncompressed data.
        """
        buf = BytesIO(data)
        with gzip.GzipFile(fileobj=buf, mode='rb') as f:
            return f.read(data)

    gzip.compress = gzip_compress
    gzip.decompress = gzip_decompress


import inspect
if not hasattr(inspect, 'getfullargspec'):
    from collections import namedtuple

    FullArgSpec = namedtuple('FullArgSpec', 'args varargs varkw defaults kwonlyargs kwonlydefaults annotations')

    def getfullargspec(func):
        """
        Get the names and default values of a callable object's parameters.

        A tuple of seven things is returned:
        (args, varargs, varkw, defaults, kwonlyargs, kwonlydefaults, annotations).
        'args' is a list of the parameter names.
        'varargs' and 'varkw' are the names of the * and ** parameters or None.
        'defaults' is an n-tuple of the default values of the last n parameters.
        'kwonlyargs' is a list of keyword-only parameter names.
        'kwonlydefaults' is a dictionary mapping names from kwonlyargs to defaults.
        'annotations' is a dictionary mapping parameter names to annotations.

        Notable differences from inspect.signature():
          - the "self" parameter is always reported, even for bound methods
          - wrapper chains defined by __wrapped__ *not* unwrapped automatically

        Missing inspect.getfullargspec implementation for older Python then 3.0.
        """
        spec = inspect.getargspec(func)
        return FullArgSpec(*(spec + ([], None, {})))

    inspect.getfullargspec = getfullargspec


# Compability access. Taken from module "six".
if PY3:
    _meth_func = "__func__"
    _meth_self = "__self__"

    _func_closure = "__closure__"
    _func_code = "__code__"
    _func_defaults = "__defaults__"
    _func_globals = "__globals__"
else:
    _meth_func = "im_func"
    _meth_self = "im_self"

    _func_closure = "func_closure"
    _func_code = "func_code"
    _func_defaults = "func_defaults"
    _func_globals = "func_globals"

get_method_function = operator.attrgetter(_meth_func)
get_method_self = operator.attrgetter(_meth_self)
get_function_closure = operator.attrgetter(_func_closure)
get_function_code = operator.attrgetter(_func_code)
get_function_defaults = operator.attrgetter(_func_defaults)
get_function_globals = operator.attrgetter(_func_globals)
