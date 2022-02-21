#
# XXX  Test and debug only!
#

import sys
from .debug import xbmc_debug
from . import Plugin, call, PathArg, search
from .lang import text

xbmc_debug(fake=True, console=True, items=True)


class MyPlugin(Plugin):

    def __init__(self):
        super().__init__()
        # self.s1 = Search(addon=self, asdasdasdaasdasdasdasd)
        # self.s2 = Search(addon=self)
        # self.search.set_option(...)  # nazwa: wartości  jakość: auto 720p 1080 UHD
        # self.search.set_xml(...)  # nazwa: wartości  jakość: auto 720p 1080 UHD

        print(f'>>>{call(self.foo, 22)}<<<')
        print(self.cmd.RunPlugin(self.foo, 22))
        print(self.cmd.Container.Update(call(self.foo, 22), 'replace'))

    def home(self):
        with self.directory(type='music') as kd:
            kd.menu(self.settings, style=['B', 'COLOR orange'])
            kd.menu('Aaa', call(self.foo, 42))
            kd.menu('Bbb', call(self.bar, 42))
            kd.item(text.close, call(self.bar, 42))
            kd.menu(self.search)

    def foo(self, a):
        print(f'foo(a={a!r})')

    def bar(self, a: PathArg[int]):
        print(f'bar(a={a!r})')

    @search.folder
    def find_best_movies(self, name, opt):
        with self.directory() as kd:
            kd.item(f'Result {name}: 22', call(self.foo, 22))
            kd.item(f'Result {name}: 42', call(self.foo, 42))

    # # @cache
    # @search.data
    # def find_best_series(self, name, options):
    #     return [ {}, {} ]


# VideoInfo = namedtuple('VideoInfo', 'title genre duration year')

del sys.argv[0]  # for kodi plugin call simulate
MyPlugin().run()
