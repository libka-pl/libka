r"""
Some string and format tools.
"""

import re
import string
from inspect import isclass, currentframe
from typing import (
    Union,
)
try:
    from simpleeval import InvalidExpression, EvalWithCompoundTypes, SimpleEval, simple_eval
# except ModuleNotFoundError:
except ImportError:
    simple_eval = None
from kodipl.iter import neighbor_iter


#: Regex type
regex = type(re.compile(''))


#: RegEx for UUID
re_uuid = re.compile(r'[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}')

#: RegEx for quote: ', ", ''', """
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

    def __init__(self, *, safe=True, evaluate=True, escape=True, extended=False, names=None, functions=None,
                 raise_empty=False):
        super().__init__()
        self.safe = safe
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
        self.raise_empty = raise_empty

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

    def get_value(self, key, args, kwargs):
        try:
            value = super().get_value(key, args, kwargs)
        except IndexError:
            if not self.safe:
                raise
            value = '{%r}' % key
        if self.raise_empty and not value:
            raise ValueError(f'{key!r} is not empty')
        return value

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
        elif unknown and not self.safe:
            raise KeyError(value)
        try:
            return super().format_field(value, format_spec)
        except Exception:
            if self.safe:
                return '{%r:%r}' % (value, input_spec)
            raise


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
        str,
    )}
    return SafeFormatter(functions=functions).vformat(fmt, args, data)


def fstr(*args, **kwargs):
    """fstr(format) is f-string format like. Uses locals and globlallas. Useful in Py2."""
    if not args:
        raise TypeError('missing format in fstr(format, *args, **kwargs)')
    fmt, args = args[0], args[1:]
    return vfstr(fmt, args, kwargs)


def _build_re_sectfmt_split(depth=3):
    f = r'(?<!\{)\{(?!\{)[^}]*\}'
    x = r'\\.|%[][%\\]_|{}|[^]]'.format(f)
    z = x = r'(?<![\\%%])\[(?:%s)*\]' % x
    for _ in range(depth):
        z = z.replace('_', '|' + x, 1)
    return re.compile('({}|{})'.format(z.replace('_', ''), f))


#: RegEx for split in sectfmt()
re_sectfmt_split = _build_re_sectfmt_split()
#: RegEx for escape in sectfmt()
re_sectfmt_text = re.compile(r'[%\\]([][%\\])')


def _vsectfmt(fmt, args, kwargs, *, formatter=None):
    """Realise Format in sections. See: sectfmt()."""
    def join(seq):
        text = ''
        for i, s in enumerate(seq):
            if i % 2:
                if s[0] == '[':
                    yield False, text
                    yield True, s[1:-1]
                    text = ''
                else:
                    text += s
            else:
                text += s
        yield False, text

    if formatter is None:
        formatter = SafeFormatter(safe=False)
    try:
        parts = (_vsectfmt(text, args, kwargs, formatter=formatter) if sect
                 else formatter.vformat(re_sectfmt_text.sub(r'\1', text), args, kwargs)
                 for sect, text in join(re_sectfmt_split.split(fmt)))
        parts = (ss[1] for ss in neighbor_iter(parts, False) if all(s is not None for s in ss))
        return ''.join(parts)
    except (KeyError, AttributeError, ValueError):
        return None


def vsectfmt(fmt, args, kwargs, *, allow_empty=False):
    """
    Realize format in sections. See sectfmt()

    Extra argument:
    allow_empty : bool
        If true, allow use section in value is empty string.
        If false (defualt), remove section if any value is empty
        If value doesn't exist section is removed always.
    """
    formatter = SafeFormatter(safe=False, raise_empty=not allow_empty)
    return _vsectfmt(fmt, args, kwargs, formatter=formatter) or ''


def sectfmt(fmt, *args, **kwargs):
    """
    Format in sections. If anything is wrong in section, whole section and adjacent text disappear.

    Example:
    >>> sectfmt('[a={a}], [b={b}][: ][c={c}], [{a}/{c}]', a=42)
    'a=42: '


    Sections are defined inside `[...]`.
    Use `%[`, `%]` and `%%` to get `[`, ']' and '%'. Instead of `%` backslash can be uesd.
    """
    return vsectfmt(fmt, args, kwargs, allow_empty=False)


def find_re(pattern: Union[str, regex], text: str, default: str = '', flags: int = 0, many: bool = True) -> str:
    """
    Search regex pattern, return sub-expr(s) or whole found text or default.

    Pattern can be text (str or unicode) or compiled regex.

    When no sub-expr defined returns whole matched text (whole pattern).
    When one sub-expr defined returns sub-expr.
    When many sub-exprs defined returns all sub-exprs if `many` is True else first sub-expr.

    Ofcourse unnamed sub-expr (?:...) doesn't matter.
    """
    if not isinstance(pattern, regex):
        pattern = re.compile(pattern, flags)
    rx = pattern.search(text)
    if not rx:
        return default
    groups = rx.groups()
    if not groups:
        rx.group(0)
    if len(groups) == 1 or not many:
        return groups[0]
    return groups


if __name__ == '__main__':
    # debug
    import random

    def foo(a):
        b = 2
        print(fstr('{a} + {b} = {a+b}, {x} / {y}, {SafeFormatter.parse}, {random.randint(5, 9)}, {0} | {9}', 11, y=9))

    x = 8
    foo(1)

    print(sectfmt(r'\[-\] [a={a}], [b={b}][: ][c={c}], [{a}/{c}]; [-\[\]]-].', a=42))
    # SafeFormatter(safe=False).vformat('{a}', (), {})

    series = {'title': 'Serial'}
    info = {'season': 2, 'episode': 3}
    data = {'title': 'Go to...'}
    fmt = '[{series[title]} – ][S{info[season]:02d}][E{info[episode]:02d}][: {title}]'
    print(sectfmt(fmt, series=series, info=info, **data))
    print(sectfmt(fmt, series=series, info=info, title=''))
