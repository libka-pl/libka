#
# XXX  Test and debug only!
#

import sys
from .debug import xbmc_debug
from . import Plugin, call, PathArg, RawArg, search
# from . import Site
from .lang import text
from .logs import log
from . import path as pathmod


xbmc_debug(fake=True, console=True, items=True)
pathmod.vfs = None


class MyPlugin(Plugin):

    def __init__(self):
        super().__init__()
        # self.s1 = Search(addon=self, asdasdasdaasdasdasdasd)
        # self.s2 = Search(addon=self)
        # self.search.set_option(...)  # nazwa: wartości  jakość: auto 720p 1080 UHD
        # self.search.set_xml(...)  # nazwa: wartości  jakość: auto 720p 1080 UHD

        # self.test_raw()
        print(f'>>>{call(self.foo, 22)}<<<')
        print(self.cmd.RunPlugin(self.foo, 22))
        print(self.cmd.Container.Update(call(self.foo, 22), 'replace'))

        if False:
            self.user_data.set('foo', 0)
            self.user_data.set('baz', 9)
            try:
                with self.user_data.transaction() as data:
                    data.set('foo', 1)
                    raise Exception()  # test
                    data.set('bar', 2)
            finally:
                log(self.user_data._data)

        # s = Site(base='https://docs.python.org/3/library')
        # t = s.txtget('runpy.html')
        # print(t.find('run_module'))
        # t = s.txtget('/3/tutorial/controlflow.html')
        # assert t == s.txtget('../tutorial/controlflow.html')
        # print(t.find('Perhaps the most well-known statement type is'))

        # self.search._add('abc')
        # self.search.clear()

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
            kd.menu(f'Result {name}: 42', call(self.foo, 42))

    def test_raw(self):
        # id_list = [item['id'] for results in data for item in results]
        id_list = list(range(20))
        with self.directory() as kdir:
            kdir.menu('title', call(self.get_search_tabs, id_list=id_list))
            kdir.menu('title', call(self.get_search_tabs_s, id_list=id_list))

    def get_search_tabs(self, id_list: RawArg):
        print(type(id_list))

    def get_search_tabs_s(self, id_list: PathArg):
        print(type(id_list))

    # # @cache
    # @search.data
    # def find_best_series(self, name, options):
    #     return [ {}, {} ]


# VideoInfo = namedtuple('VideoInfo', 'title genre duration year')

del sys.argv[0]  # for kodi plugin call simulate
log(sys.argv, title='ARGS')
MyPlugin().run()
