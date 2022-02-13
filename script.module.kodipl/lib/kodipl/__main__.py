#
# XXX  Test and debug only!
#


import sys
from . import Plugin, call, PathArg
from .lang import text
from .debug import xbmc_debug


xbmc_debug(fake=True, console=True, items=True)


class MyPlugin(Plugin):

    def __init__(self):
        super().__init__()

    def home(self):
        with self.directory(type='music') as kd:
            kd.menu(self.settings)
            kd.menu('Aaa', call(self.foo, 42))
            kd.menu('Bbb', call(self.bar, 42))
            kd.item(text.close, call(self.bar, 42))

    def foo(self, a):
        print(f'foo(a={a!r})')

    def bar(self, a: PathArg[int]):
        print(f'bar(a={a!r})')


del sys.argv[0]
MyPlugin().run()
