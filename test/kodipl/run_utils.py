import sys
from pathlib import Path
import asyncio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'script.module.libka' / 'lib'))

from libka.routing import (  # noqa: E402
    subobject,
    entry,
    PathArg,
    Call,
    Router,
)


if __name__ == '__main__':
    log = print

    class Bar:
        def foo(self, a):
            print(f'{self.__class__.__name__}.foo({a!r})')

        @entry(path='/<self>/GOO/<a>')
        def goo(self, a):
            print(f'{self.__class__.__name__}.foo({a!r})')

    class Baz:
        bar = subobject()

        def __init__(self):
            self.bar = Bar()

        def foo(self, a):
            print(f'{self.__class__.__name__}.foo({a!r})')

    class Class:
        bar = subobject()
        baz = subobject()
        z = subobject()

        def __init__(self):
            self.bar = Bar()
            self.baz = Baz()

        @subobject
        def abc(self):
            print('Here is "abc", I am creating Baz()')
            return Baz()

        def foo(self, a):
            print(f'{self.__class__.__name__}.foo({a!r})')

        def goo(self, a: PathArg, /, b: PathArg[int], c: float = 42, *, d: str):
            print(f'{self.__class__.__name__}.goo({a!r}, {b!r}, {c!r}, {d!r})')

        @entry(path='/o/auu/<a>/buu/<uint:b>/ccc/<float:c>', object='obj')
        def aoo(self, a: PathArg, /, b: PathArg[int], c: float = 42, *, d: str):
            print(f'{self.__class__.__name__}.aoo({a!r}, {b!r}, {c!r}, {d!r})')

        @entry(path='/<self>/0/auu/<0>/buu/<uint:b>/ccc/<float:c>')
        def a00(self, a: PathArg, /, b: PathArg[int], c: float = 42, *, d: str):
            print(f'{self.__class__.__name__}.a00({a!r}, {b!r}, {c!r}, {d!r})')

        async def adef(self, a: PathArg, b: PathArg[int] = 44):
            print(f'{self.__class__.__name__}.adef({a!r}, {b!r})')

        def __call__(self, a):
            print(f'{self.__class__.__name__}({a!r})')

    def foo(a):
        print(f'foo({a!r})')

    class Z:
        def __call__(self):
            pass

    bar = foo
    # del foo

    def test(*args, **kwargs):
        print(f'----- {args} {kwargs}')
        url = router.mkurl(*args, **kwargs)
        print(url)
        entry = router._dispatcher_entry(url, root=None)
        print(f'  --> {entry!r}')
        if entry:
            print('  ==> ', end='')
            entry.method(*entry.args, **entry.kwargs)
            print('')

    def xxx(a, b=1, /, c=2, *d, e, f=5, **g):
        print(f'xxx({a!r}, {b!r}, c={c!r}, d={d}, e={e!r}, f={f!r}, g={g})')

    def yyy(a, b, /, c, d=3, *, e, f=5):
        pass

    def zzz(a, b=1, /, c=2, d=3, *, e, f=5):
        pass

    if 1:
        print('--- :')
        obj = Class()
        print('ABC', obj.abc)
        print('ABC', obj.abc)
        router = Router(url='plugin://this')
        test(Call(xxx, (11,), {'e': 14}, {'z': 99}))  # XXX
        xxx(10, 11, 12, 13, 14, e=24, g=26, h=27)  # XXX XXX
        test(xxx, 10, 11, 12, 13, 14, e=24, g=26, h=27)  # XXX XXX
        test(obj.aoo, 123, 44, d='xx')  # XXX
        test(obj.a00, 123, 44, d='xx')  # XXX
        test(obj.goo, 123, 44, d='xx')  # XXX
        test(obj.adef, 11, 22)  # XXX
        test(foo, 33)
        test('foo', 33)
        test(obj.foo, a=33)
        test(obj.baz.foo, 33)
        test(obj.bar.goo, 66)

    if 1:
        print('--- obj')
        obj = Class()
        obj2 = Class()
        obj.obj = obj2
        obj.z = Z()
        router = Router(url='plugin://this', obj=obj)
        test(foo, 33)
        test(bar, 44), bar.__name__
        test(obj.foo, 33)
        test(obj.goo, 99, b=44, d='dd')
        test(obj.baz.foo, 33)
        test(obj.baz.bar.foo, 33)
        test(obj.abc.bar.foo, 33)
        test(obj2.foo, 33)
        test(obj2.baz.foo, 33)
        test(obj2.baz.bar.foo, 33)
        test(obj2.abc.bar.foo, 33)
        test(obj, 55)
        test(obj.obj, 55)
        test(obj.z)
        test(obj.bar.goo, 66)
        # print(obj.abc)

        def root():
            print('root /')

        router._dispatcher_entry('plugin://this', root=root)
        router._dispatcher_entry('plugin://this/', root=root)

    if 1:
        print('--- non-global obj')
        d = {'obj': Class()}
        d['obj'].z = Z()
        router = Router(url='plugin://this', obj=d['obj'])
        test(d['obj'].foo, 33)
        test(d['obj'].baz.foo, 33)
        test(d['obj'], 55)
        test(d['obj'].z)

    if 1:
        print('--- run disptacher')

        async def aroot():
            print('ROOT')
            return 42

        async def arun():
            return await Router().dispatch('/', root=aroot)

        print('sync ', Router().dispatch('/', root=aroot))
        print('async', asyncio.run(arun()))

    if 1:
        print('--- disptach args and kwargs')
        default_router = Router(standalone=True)

        @entry(path='/Foo/<a>/<int:b>')
        def foo(a, /, b, c=1, *, d: int, e=2):
            print(f'foo(a={a!r}, b={b!r}, c={c!r}, d={d!r}, e={e!r})')

        def bar(a: PathArg, /, b: PathArg[int], c=1, *, d: int, e=2):
            print(f'bar(a={a!r}, b={b!r}, c={c!r}, d={d!r}, e={e!r})')

        def baz(a: PathArg, /, b: PathArg[int], *c: tuple[int], d: int, e=2, **z: dict[str, int]):
            print(f'bar(a={a!r}, b={b!r}, c={c!r}, d={d!r}, e={e!r}, z={z!r})')

        rt = Router('plugin://this')
        print(rt.url_for(foo, 11, 12, 13, d=14))  # plugin://this/bar/11/12?c=13&d=14
        print(rt.url_for(bar, 11, 12, 13, d=14))  # plugin://this/bar/11/12?c=13&d=14
        print(rt.url_for(baz, 11, 12, 131, 132, d=14, x=21, z=23))  # plugin://this/bar/11/12?c=13&d=14

        rt.dispatch('plugin://this/Foo/11/12?c=13&d=14')  # foo(a='11', b=12, c='13', d=14, e=2)
        rt.dispatch('plugin://this/bar/11/12?c=13&d=14')  # bar(a='11', b=12, c='13', d=14, e=2)
        rt.dispatch('plugin://this/baz/11/12?2=131&3=132&d=14&x=21&z=23')  # bar(a='11', b=12, c='13', d=14, e=2)

        def play(vid: PathArg):
            print(f'Playing video with ID {vid}')

        url = rt.url_for(play, 123)
        print(f'URL {url} -> ', end='')
        rt.dispatch(url)

    if 1:
        print('--- disptach the same path with different arg types')
        default_router = Router(standalone=True)

        @entry(path='/aaa/<a>/<int:b>')
        def foo(a, /, b, c=1):
            print(f'foo(a={a!r}, b={b!r}, c={c!r})')

        @entry(path='/aaa/<a>/<b>')
        def bar(a, /, b, c=1):
            print(f'bar(a={a!r}, b={b!r}, c={c!r})')

        rt = Router('plugin://this')

        print(rt.url_for(foo, 'A', 99))   # plugin://this/aaa/A/99
        print(rt.url_for(bar, 'A', 'B'))  # plugin://this/aaa/A/B

        rt.sync_dispatch('plugin://this/aaa/A/99')  # foo(a='A', b=99, c=1)
        rt.sync_dispatch('plugin://this/aaa/A/B')   # bar(a='A', b='B', c=1)

    print('--- ...')
