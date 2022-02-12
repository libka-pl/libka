from typing import (
    Union, Optional, TypeVar,
    Callable, Any,
    Tuple, Dict,
    get_origin, get_args,
)
from inspect import signature
from collections import namedtuple


# type aliases
Args = Tuple[Any]
KwArgs = Dict[str, Any]


T = TypeVar('T')


def is_optional(ann: T) -> bool:
    """True is `ann` is optional. Optional[X] is equivalent to Union[X, None]."""
    args = get_args(ann)
    return get_origin(ann) is Union and len(args) == 2 and args[1] is type(None)  # noqa E721


def remove_optional(ann: Union[Optional[T], T]) -> T:
    """Remove Optional[X] (if exists) and returns X."""
    args = get_args(ann)
    if get_origin(ann) is Union and len(args) == 2 and args[1] is type(None):  # noqa E721
        return args[0]
    return ann


Arguments = namedtuple('Arguments', 'args kwargs arguments positional indexes defaults')


def _bind_args(func: Callable, args: Tuple[Any], kwargs: Dict[str, Any],
               force_keyword_arguments: bool = False) -> Arguments:
    """
    Prepare args and kwargs for `func`.

    When force_keyword_arguments all POSITIONAL_OR_KEYWORD are forcead as keyword arguments
    even if was in `args`.
    """
    def mkargs():
        ait = iter(args)
        for p in sig.parameters.values():
            if p.kind == p.POSITIONAL_ONLY:
                try:
                    value = next(ait)
                    positional.append(p.name)
                except StopIteration:
                    value = p.default
                aa[p.name] = value
                yield value
            elif p.kind == p.POSITIONAL_OR_KEYWORD:
                try:
                    if force_keyword_arguments:
                        kwargs[p.name] = next(ait)
                    else:
                        value = next(ait)
                        positional.append(p.name)
                        aa[p.name] = value
                        yield value
                except StopIteration:
                    return
            elif p.kind == p.VAR_POSITIONAL:
                while True:
                    try:
                        yield next(ait)
                    except StopIteration:
                        return
            else:
                return

    aa = {}
    positional = []
    try:
        sig = signature(func)
    except TypeError:
        breakpoint()
        if not callable(func):
            raise
        sig = signature(func.__call__)

    sig.bind(*args, **kwargs)  # check arguments or raise TypeError
    args = tuple(mkargs())
    aa.update(kwargs)
    for p in sig.parameters.values():
        if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY):
            if p.default is not p.empty:
                aa.setdefault(p.name, p.default)
    return Arguments(args, kwargs, aa, tuple(positional),
                     indexes={n: i for i, n in enumerate(positional)},
                     defaults={p.name: p.default for p in sig.parameters.values() if p.default is not p.empty}
                     )


def bind_args(func: Callable, *args, **kwargs) -> Arguments:
    """Prepare args and kwargs for `func`."""
    return _bind_args(func, args, kwargs)


def uint(v):
    """Make unsigned int."""
    v = int(v)
    if v < 0:
        raise ValueError('Negative uint')
    return v


def pint(v):
    """Make positive int."""
    v = int(v)
    if v <= 0:
        raise ValueError('Non-positive int')
    return v


def mkbool(v):
    """Make bool."""
    if isinstance(v, str):
        v = v.lower()
        if v in mkbool.true:
            return True
        if v in mkbool.false:
            return False
        raise ValueError(f'Unknown bool format {v!r}')
    return bool(v)


mkbool.true = {'true', 'on', '1', 'hi', 'high', 'up', 'enable', 'enabled'}
mkbool.false = {'false', 'off', '0', 'lo', 'low', 'down', 'disable', 'disabled'}
