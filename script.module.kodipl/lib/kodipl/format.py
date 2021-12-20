# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals, print_function
from future.utils import PY2
if PY2:
    from builtins import *  # dirty hack
from future.utils import python_2_unicode_compatible

r"""
Some sstring and format tools.
"""
# COPY od transys.toold.format and some other private code

import re
import string
from inspect import isclass, currentframe
try:
    from simpleeval import InvalidExpression, EvalWithCompoundTypes, SimpleEval, simple_eval
# except ModuleNotFoundError:
except ImportError:
    simple_eval = None


#: Regex type
regex = type(re.compile(''))


#: RegEx for UUID
re_uuid = re.compile(r'[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}')


re_quote = re.compile(r'''(?:"""(?:\\.|.)*?""")|(?:"(?:\\.|.)*?")'''
                      r"""|(?:'''(?:\\.|.)*?''')|(?:'(?:\\.|.)*?')""")


def fparser(s):
    """
    Like _string.formatter_parser() returns (literal_text, field_name, format_spec, conversion).
    Supports "{}" inside field_name, can work with simple_eval.
    Ex. f-string inside {} inside join with list comprehension):
    >>> fmt('out: {", ".join(f"({x})" for x in hosts)}...', hosts=("a", "bb", "ccc"))
    >>> # 'out: (a), (bb), (ccc)'
    """
    i, lvl = 0, 0
    # literal_text, field_name, format_spec, conversion
    oi, vec = 0, ['', None, None, None]
    while i < len(s):
        c = s[i]
        nc = s[i+1:i+2]
        if c in '{}' and c == nc:
            vec[oi] += c
            i += 1
        elif c == '{':
            if lvl == 0:
                oi = 1
                vec[1] = vec[2] = ''
            else:
                vec[oi] += c
            lvl += 1
        elif c == '}':
            lvl -= 1
            if lvl < 0:
                raise ValueError("Single '}' encountered in format string")
            if lvl == 0:
                yield vec
                oi, vec = 0, ['', None, None, None]
            else:
                vec[oi] += c
        elif lvl == 1 and c == '!' and oi == 1:
            oi = 3
            vec[oi] = ''
        elif lvl == 1 and c == ':' and oi in (1, 3):
            oi = 2
            vec[oi] = ''
        else:
            rx = re_quote.match(s, i) if lvl > 0 and c in ('"', "'") else None
            if rx:
                a, b = rx.span()
                vec[oi] += s[a:b]
                i += b - a - 1
            else:
                vec[oi] += c
        i += 1
    if lvl:
        raise ValueError("Single '{' encountered in format string")
    if vec[0] or vec[1] is not None:
        yield vec


@python_2_unicode_compatible
class SafeFormatter(string.Formatter):
    r"""
    Safe string formatter.

    Leave unknown arguments, or use default value or evaluate expr:
    ("{a:!!def} {999}") -> "def {999}"
    ("{a + 2}", a=42)   -> "44"
    """

    _escape_trans = {
        '\\': '\\\\',
        '\'': '\\\'',
        '\"': '\\\"',
        '\a': '\\a',
        '\b': '\\b',
        '\f': '\\f',
        '\n': '\\n',
        '\r': '\\r',
        '\t': '\\t',
        '\v': '\\v',
        '\000': '\\000',
    }

    # def __init__(self, *, evaluate=True, escape=True, extended=False, names=None, functions=None):
    def __init__(self, evaluate=True, escape=True, extended=False, names=None, functions=None):
        super().__init__()
        self.evaluator = None
        self.evaluator_class = None
        if isclass(evaluate):
            self.evaluator_class = evaluate
        elif simple_eval and evaluate:
            if evaluate == 'simple':
                self.evaluator_class = SimpleEval
            else:
                self.evaluator_class = EvalWithCompoundTypes
        self.evaluator_names = names
        self.evaluator_functions = functions
        self.escape = escape
        self.extended = extended

    def parse(self, format_string):
        if self.extended:
            return fparser(format_string)
        return super().parse(format_string)

    def vformat(self, format_string, args, kwargs):
        if self.evaluator_class:
            if self.evaluator_names:
                names = {}
                names.update(self.evaluator_names)
                names.update(kwargs)
            else:
                names = kwargs
            self.evaluator = self.evaluator_class(names=names, functions=self.evaluator_functions)
        return super().vformat(format_string, args, kwargs)

    def convert_field(self, value, conversion):
        if self.escape and conversion == 'e':
            esc = self._escape_trans
            return ''.join(esc.get(c, c) for c in str(value))
        return super().convert_field(value, conversion)

    def get_field(self, field_name, args, kwargs):
        try:
            return super().get_field(field_name, args, kwargs)
        except (KeyError, AttributeError, IndexError):
            if field_name.isdigit():
                raise  # missing positional argument
        if self.evaluator:
            try:
                return self.evaluator.eval(field_name), ()
            except InvalidExpression:
                pass
        return self.missing_field(field_name, args, kwargs)

    def missing_field(self, field_name, args, kwargs):
        return '{%s}' % field_name, ()

    def format_field(self, value, format_spec):
        input_spec = format_spec
        format_spec, sep, val = format_spec.partition('!!')
        unknown = isinstance(value, str) and value[:1] == '{' and value[-1:] == '}'
        if sep and unknown:
            try:
                if '::' in val:
                    value, sep, format_spec = val.partition('::')
                elif format_spec[-1:] in 'bcdoxX':
                    value = int(val)
                elif format_spec[-1:] in 'eEfFgG':
                    value = float(val)
                else:
                    value = val
            except ValueError:
                # format_spec = format_spec[:-1] + 's'
                format_spec = 's'
                value = val
        try:
            return super().format_field(value, format_spec)
        except Exception as exc:
            return '{%r:%r}' % (value, input_spec)


def safefmt(fmt, *args, **kwargs):
    """Realize safe string formatting."""
    return SafeFormatter().vformat(fmt, args, kwargs)


def vfstr(fmt, args, kwargs, depth=1):
    """Realize f-string formatting."""
    frame = currentframe().f_back
    for _ in range(depth):
        frame = frame.f_back
    data = {}
    data.update(frame.f_globals)
    data.update(frame.f_locals)
    data.update(kwargs)
    functions = {f.__name__: f for f in (
        dir, vars,
    )}
    return SafeFormatter(functions=functions).vformat(fmt, args, data)


def fstr(*args, **kwargs):
    """fstr(format) is f-string format like. Uses locals and globlas. Useful in Py2."""
    if not args:
        raise TypeError('missing format in fstr(format, *args, **kwargs)')
    fmt, args = args[0], args[1:]
    return vfstr(fmt, args, kwargs)


if __name__ == '__main__':
    # debug
    import random

    def foo(a):
        b = 2
        print(fstr('{a} + {b} = {a+b}, {x} / {y}, {SafeFormatter.parse}, {random.randint(5, 9)}, {0}', 11, y=9))

    x = 8
    foo(1)
