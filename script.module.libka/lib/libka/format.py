r"""
Some string and format tools.
"""

import re
import string
from inspect import isclass, currentframe
from dataclasses import dataclass
from collections import namedtuple
from collections.abc import Mapping
from typing import (
    Optional, Union, Callable, Any, Type,
    List, Dict,
)
try:
    from simpleeval import InvalidExpression, EvalWithCompoundTypes, SimpleEval, simple_eval
# except ModuleNotFoundError:
except ImportError:
    simple_eval = None
try:
    import xbmc
except ImportError:
    xbmc = None
from .iter import neighbor_iter
from .tools import adict


class MISSING:
    """Helper. Missing value."""


#: Regex type
regex = type(re.compile(''))


#: RegEx for UUID
re_uuid = re.compile(r'[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}')

#: RegEx for quote: ', ", ''', """
re_quote = re.compile(r'''(?:"""(?P<q1>(?:\\.|.)*?)""")|(?:"(?P<q2>(?:\\.|.)*?)")'''
                      r"""|(?:'''(?P<q3>(?:\\.|.)*?)''')|(?:'(?P<q4>(?:\\.|.)*?)')""", re.DOTALL)

#: RegEx for quote: ', ", ''', """ with optional spaces
re_quote_s = re.compile(fr'\s*(?:{re_quote.pattern})\s*', re.DOTALL)

#: RegEx for find field-name matching style
re_field_name = re.compile((fr'[^\W\d]+(?P<part>\.[^\W\d]+|\[\s*\w+\s*\]|\[\s*(?:{re_quote.pattern})\s*\])*'
                            r'(?P<any>\.\*|\[\*\])?'),
                           re.IGNORECASE | re.DOTALL)

#: RegEx for replace custom-named color to regular color
RE_TITLE_COLOR = re.compile(r'\[COLOR +:(\w+)\]')

#: Translate dict for string escape.
ESCAPE_TRANS = {
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


def str_escape(s):
    r"""Escape string, e.g. `\n` -> `\\n`."""
    esc = ESCAPE_TRANS
    return ''.join(esc.get(c, c) for c in s)


def fparser(s, *, eol_escape=False):
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
                if eol_escape:
                    vec[oi] += s[a:b].replace('\n', '\\n')
                else:
                    vec[oi] += s[a:b]
                i += b - a - 1
            else:
                vec[oi] += c
        i += 1
    if lvl:
        raise ValueError("Single '{' encountered in format string")
    if vec[0] or vec[1] is not None:
        yield vec


@dataclass
class StylizeSettings:
    #: Default style.
    style: Union[List[str], str] = None
    #: Info values (kept by reference).
    info: Dict[str, Any] = None
    #: Method to resolve cutom color names `[COLOR :name]` or
    #: color dict (to find missing custom colors).
    colors: Union[Callable, Dict[str, str]] = None
    #: Default extra keyword arguments for format styles (kept by reference).
    kwargs: Dict[str, Any] = None


#: Helper. Filed name info.
FieldInfo = namedtuple('FieldInfo', 'field_name, args kwargs')


class SafeFormatter(string.Formatter):
    r"""
    Safe string formatter.

    Leave unknown arguments (when `safe` is true), or use default value or evaluate expr:
    >>> ("{a:!!def} {999}") # -> "def {999}"
    >>> ("{a + 2}", a=42)   # -> "44"

    All dicts (`names`, `functions`, `default_formats`, `styles`) are stored directly, you can update them in runtime.
    """

    def __init__(self, *, safe: bool = True, evaluate: bool = True, escape: bool = True, extended: bool = False,
                 names: Optional[Dict[str, Any]] = None,
                 functions: Optional[Dict[str, Callable]] = None,
                 raise_empty: bool = False,
                 default_formats: Optional[Dict[str, str]] = None,
                 stylize: Optional[StylizeSettings] = None,
                 styles: Optional[Dict[str, Union[List[str], str]]] = None):
        super().__init__()
        #: True, for safe formatting: ${unkown}.
        self.safe: bool = safe
        #: Evaluator instance, created in `vformat()`.
        self.evaluator = None
        #: Evaluator class used to create evaluator instance.
        self.evaluator_class: Type = None
        if isclass(evaluate):
            self.evaluator_class = evaluate
        elif simple_eval and evaluate:
            if evaluate == 'simple':
                self.evaluator_class = SimpleEval
            else:
                self.evaluator_class = EvalWithCompoundTypes
        #: Default variable names for evaluator.
        self.evaluator_names: Dict[str, Any] = names
        #: Functions for evaluator.
        self.evaluator_functions: Dict[str, Callable] = functions
        #: Add support for `!e` convert for escape strings.
        self.escape: bool = escape
        #: Use extended parser. Should be true for most `evaluate` expresions.
        self.extended: bool = extended
        #: Raise exception if value is empty (not only non-exists). Usefull with `sectfmt()`.
        self.raise_empty: bool = raise_empty
        #: Default formats for variables.
        self.default_formats: Dict[str, str] = {} if default_formats is None else default_formats
        #: Method to stylize values.
        self.stylize_settings: StylizeSettings = StylizeSettings() if stylize is None else stylize
        #: Styles for values. Name of value is key in `styles` dict (kept by reference).
        self.styles: Dict[str, Union[List[str], str]] = {} if styles is None else styles
        #: Stack for filed names. Appended in `get_field`, popped in `format_field`.
        self._field_name_stack: List[FieldInfo] = []

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
        try:
            return super().vformat(format_string, args, kwargs)
        except Exception as exc:
            if self.safe:
                if xbmc:
                    xbmc.log(f'Formatter {format_string!r} failed: {exc!r}', xbmc.LOGINFO)
            else:
                raise

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
            return str_escape(str(value))
        # if conversion in '!?$':
        #     conversion = ''
        return super().convert_field(value, conversion)

    def get_field(self, field_name, args, kwargs):
        self._field_name_stack.append(FieldInfo(field_name.strip(), args, kwargs))
        try:
            return super().get_field(field_name, args, kwargs)
        except (KeyError, AttributeError, IndexError, ValueError):
            if field_name.isdigit():
                self._field_name_stack.pop()
                raise  # missing positional argument
        if self.evaluator:
            try:
                return self.evaluator.eval(field_name), field_name
            except (InvalidExpression, SyntaxError):
                pass
        return self.missing_field(field_name, args, kwargs)

    def missing_field(self, field_name, args, kwargs):
        return '{%s}' % field_name, field_name

    _RE_FORMAT_FIELD_EXTRA = re.compile(r'(?P<format_spec>.*?)(?P<conds>![$?].*?)?(?:!!(?P<default>.*))?')
    _RE_FORMAT_FIELD_SPLIT = re.compile(r'(![$?])')

    def format_field(self, value, format_spec):
        info: FieldInfo = self._field_name_stack.pop()
        field_name: str = info.field_name
        # orig_format_spec: str = format_spec
        m = self._RE_FORMAT_FIELD_EXTRA.fullmatch(format_spec)
        assert m
        format_spec = m.group('format_spec')
        default_val: Optional[str] = m.group('default')
        spec_cond = style_cond = None
        if m.group('conds'):
            it = iter(self._RE_FORMAT_FIELD_SPLIT.split(m.group('conds'))[1:])
            conds = dict(zip(it, it))
            conds = {k: info.kwargs.get(v.strip()) for k, v in conds.items()}
            spec_cond = conds.get('!?')
            style_cond = conds.get('!$')

        if not format_spec:
            norm_field_name = re_quote_s.sub(r'\g<q1>\g<q2>\g<q3>\g<q4>', field_name)
            format_spec = (self.default_formats.get(norm_field_name)
                           # TODO:  add wildcards to default_formats (like in field_style)
                           or self.default_formats.get(norm_field_name.rpartition('.')[0] + '.*') or '')
            if isinstance(format_spec, Mapping):
                format_spec = format_spec.get(spec_cond, format_spec.get(None, ''))
            format_spec, dsep, val = format_spec.partition('!!')
            if dsep and default_val is None:
                default_val = val

        input_spec: str = format_spec
        unknown = isinstance(value, str) and value[:1] == '{' and value[-1:] == '}'
        if default_val is not None and unknown:
            try:
                if '::' in default_val:
                    value, sep, format_spec = default_val.partition('::')
                elif format_spec[-1:] in 'bcdoxX':
                    value = int(default_val)
                elif format_spec[-1:] in 'eEfFgG':
                    value = float(default_val)
                else:
                    value = default_val
            except ValueError:
                # format_spec = format_spec[:-1] + 's'
                format_spec = 's'
                value = default_val
        elif unknown and not self.safe:
            raise KeyError(value)
        try:
            result = super().format_field(value, format_spec)
            last_field_name = ''  # only for assertion
            while field_name:
                assert field_name != last_field_name
                last_field_name = field_name
                field_style = self.styles.get(field_name)
                if field_style is None:
                    norm_field_name = re_quote_s.sub(r'\g<q1>\g<q2>\g<q3>\g<q4>', field_name)
                    field_style = self.styles.get(norm_field_name)
                if field_style is not None:
                    if isinstance(field_style, Mapping):
                        field_style = field_style.get(style_cond, field_style.get(None, ''))
                    if field_style is not None:
                        result = self.stylize(result, field_style)
                        break
                if field_name == '*':
                    # print(f' - {field_name=!r}, m=')
                    break
                m = re_field_name.fullmatch(field_name)
                if not m:
                    break
                # print(f' - {field_name=!r}, m={m.groupdict()}')
                part = m.group('part')
                if m['any']:
                    end = m.start('any')
                    field_name = f'{field_name[:end]}'
                elif not part:
                    field_name = '*'
                elif '[' in part:
                    end = m.start('part')
                    field_name = f'{field_name[:end]}[*]'
                else:
                    end = m.start('part')
                    field_name = f'{field_name[:end]}.*'
            return result
        except Exception:
            if self.safe:
                return '{%r:%r}' % (value, input_spec)
            raise

    def stylize(self,
                text:            str,
                style:           Optional[Union[str, List[str]]] = None,
                *,
                info:            Optional[Dict[str, Any]] = None,
                colors:          Optional[Dict[str, str]] = None,
                default_formats: Optional[Dict[str, str]] = None,
                **kwargs):
        """
        Style formatting.

        Parameters
        ----------
        text: str
            A text to stylize.
        style: str or list of str
            Style(s) to apply on the text.
        info: dict of str, str
            Optional extra values in the `info` variable. Update a `self.stylize.info`.
        colors: dict of str, str
            Optional color dictionary used in `[COLOR :<name>]`. Update a `self.stylize.colors`.
        default_formats: dict of str, str
            Optional string format for any `kwargs` variable. Update a `self.default_formats`.
        kwargs:
            Extra variables for text formatting.

        The `text` is formatted as safe f-string. `style` is a single format or list of formats
        starting from outside one. Every Kodi label style could be used or special characters
        (length of one or two) like `[]` or `*` or text format.

        Colors could be in a format `COLOR :name` when the `name` is a key in `colors` dict.

        Every f-string variable is taken from the `kwargs` arguments or `info` dict.

        Exapmle
        -------
        >>> fmt.stylize('abc', 'B')
        >>> # '[B]abc[/B]'

        >>> fmt.stylize('abc', ['COLOR red', '«»', 'B'])
        >>> # '[COLOR red]«[B]abc[/B]»[COLOR]'

        >>> fmt.stylize('abc: {answer}', 'B', answer=42)
        >>> # '[B]abc: 42[/B]'

        >>> fmt.stylize('abc', '>>>{}<<<')
        >>> # '>>>abc<<<'

        >>> fmt.stylize('', 'a={a}, bc={b.c}', default_formats('a': '02d', 'b.c': '03d'),
        ...             a=1, b={'c': 2})
        >>> # 'a=01, bc=002'
        """
        ss = self.stylize_settings
        if style is None:
            style = ss.style
        if ss.info is not None:
            if info is None:
                info = ss.info
            else:
                info = {**ss.info, **info}
        my_default_format = self.default_formats
        try:
            if default_formats:
                self.default_formats = {**self.default_formats, **default_formats}
            if ss.kwargs is not None:
                info = {**ss.kwargs, **kwargs}
            if callable(ss.colors):
                # external color getter, skip `colors` dict update
                if not callable(colors):
                    colors = ss.colors
            elif ss.colors is not None:
                if colors is None:
                    colors = ss.colors
                else:
                    colors = {**ss.colors, **colors}
            result = stylize(text, style, info=info, formatter=self, colors=colors, **kwargs)
        finally:
            self.default_formats = my_default_format
        return result


def safefmt(fmt, *args, **kwargs):
    """Realize safe string formatting."""
    return SafeFormatter().vformat(fmt, args, kwargs)


def vfstr(fmt, args, kwargs, *, depth=1, extended=False):
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
    return SafeFormatter(functions=functions, extended=extended).vformat(fmt, args, data)


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
        formatter = SafeFormatter(safe=False, raise_empty=True)
    try:
        parts = (_vsectfmt(text, args, kwargs, formatter=formatter) if sect
                 else formatter.vformat(re_sectfmt_text.sub(r'\1', text), args, kwargs)
                 for sect, text in join(re_sectfmt_split.split(fmt)))
        parts = (ss[1] for ss in neighbor_iter(parts, False) if all(s is not None for s in ss))
        return ''.join(parts)
    except (KeyError, AttributeError, ValueError, ValueError):
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


def stylize(text: str, style: Union[str, List[str]], *,
            info:      Optional[Dict[str, Any]] = None,
            formatter: Optional[string.Formatter] = None,
            colors:    Optional[Dict[str, str]] = None,
            **kwargs):
    """
    Style formatting.

    Parameters
    ----------
    text: str
        A text to stylize.
    style: str or list of str
        Style(s) to apply on the text.
    info: dict of str, str
        Optional extra values in the `info` variable.
    formatter: string.Formatter
        String formatter, default is `SafeFormatter(safe=True, extended=True)`.
    colors: dict of str, str
        Optional color dictionary used in `[COLOR :<name>]`.
    kwargs:
        Extra variables for text formatting.

    The `text` is formatted as safe f-string. `style` is a single format or list of formats
    starting from outside one. Every Kodi label style could be used or special characters
    (length of one or two) like "[]" or "*" or text format.

    Colors could be in a format `COLOR :name` when the `name` is a key in `colors` dict.

    Every f-string variable is taken from the `kwargs` arguments or `info` dict.

    Exapmle
    -------
    >>> stylize('abc', 'B')
    >>> # '[B]abc[/B]'

    >>> stylize('abc', ['COLOR red', '«»', 'B'])
    >>> # '[COLOR red]«[B]abc[/B]»[COLOR]'

    >>> stylize('abc: {answer}', 'B', answer=42)
    >>> # '[B]abc: 42[/B]'

    >>> stylize('abc', '>>>{}<<<')
    >>> # '>>>abc<<<'
    """
    if colors is None:
        def replace_color(m):
            if xbmc:
                xbmc.log(f'Incorrect label/title type {type(text)}', xbmc.LOGWARNING)
            return '[COLOR gray]'
    elif callable(colors):
        def replace_color(m):
            return '[COLOR %s]' % colors(m.group(1))
    else:
        def replace_color(m):
            return colors.get(m.group(1), 'gray')

    if style is not None:
        if formatter is None:
            formatter = SafeFormatter(safe=True, extended=True)
        info = adict(info or ())
        if isinstance(style, str):
            style = (style, )
        for s in reversed(style):
            if not s:
                pass
            elif s[0].isalpha():
                text = f'[{s}]{text}[/{s.split(None, 1)[0]}]'
            elif s == '[]':  # brackets with zero-width spaces to avoid BB-code sequence
                text = f'[\u200b{text}\u200b]'
            elif len(s) <= 2:  # another brackets etc. (one or two characters)
                text = f'{s[0]}{text}{s[-1]}'
            else:
                # reformat the text, the text is first `{0}` and `text` argument
                text = formatter.format(s, text, text=text, info=info, **kwargs)
    try:
        text = RE_TITLE_COLOR.sub(replace_color, text)
    except TypeError:
        if xbmc:
            xbmc.log(f'Incorrect label/title type {type(text)}', xbmc.LOGWARNING)
        raise
    return text


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
    print(SafeFormatter(extended=True).format('>{"To jest\tto\n"!e}<'))
    print(SafeFormatter(default_formats={'0': '05d', 'a.b': '03d'}).format('{},{a.b}', 42, a=adict(b=44)))
    f1 = SafeFormatter(default_formats={'a': '03d'})
    print(f1.stylize('abc', '{a}/{text}/{b}/{c.d}', default_formats={'b': '04d', 'c.d': '02d'}, a=1, b=2, c={'d': 3}),
          f1.default_formats)
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
    fmt = '[{series[title]} – ][B][S{info[season]:02d}][E{info[episode]:02d}][/B][: {title}]'
    print(sectfmt(fmt, series=series, info=info, **data))
    print(sectfmt(fmt, series=series, info=info, title=''))
    s = 'To jest\tto\n'
    print(safefmt('>{!e}<', s))
    print(SafeFormatter(extended=True).format('>{"To jest\tto\n"!e}<'))
    # SafeFormatter(extended=True).format('{a.b.c}', styles={'a': 'A'}, a={'b': {'c': 2}})
    # SafeFormatter(extended=True).format('{a[b][c]}', styles={'a': 'A'}, a={'b': {'c': 2}})
    c = adict(x=11, y=22, z=[330, 331])
    d = adict(a=42)
    styles = {
        'a': 'I',
        'b': ['B', '*'],
        'c': 'C',
        'c.x': 'X',
        'c.*': 'Y',
        'c.z[0]': 'Z0',
        'c.z[*]': 'ZZ',
        'c[*]': 'Z',
        'c[y]': 'ZY1',
        # 'c["y"]': 'ZY2',
        # "c['y']": 'ZY3',
        'd': 'D',
    }
    default_formats = {
        'c.y': '03d',
        'c[y]': '04d',
        'c["y"]': '05d',
    }
    fmt = SafeFormatter(extended=True, styles=styles, default_formats=default_formats).format
    print(fmt('{a}, {b}, ({c.x}, {c.y}, {c.z[0]}, {c.z[1]}, {c["x"]}, {c["y" ]}, {c.y}), ({d.a})',
              a=1, b=2, c=c, d=d))
    styles.update({
        'e': {None: 'A', 'x': 'X', 'y': 'B'},
    })
    default_formats.update({
        'e': {None: '05d', 'x': '+d', 'y': '+09d'},
    })
    print(fmt('{e},{e:!?o},{e:!$s},{e:!$s},{e:!?o!$s},{e:!?q!?o}.', e=42, o='x', s='y'))
