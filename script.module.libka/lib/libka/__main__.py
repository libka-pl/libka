#
# XXX  Test and debug only!
#

import sys
from .debug import xbmc_debug
from . import SimplePlugin, Plugin, Site, call, PathArg, RawArg, search
# from . import Site
from .lang import text
from .logs import log
from . import path as pathmod
from .cache import cached


xbmc_debug(fake=True, console=True, items=True)
pathmod.vfs = None


def test_concurrent():
    import time
    from .threads import concurrent

    def foo(x):
        time.sleep(1)
        return x**2

    with concurrent(name='abc') as con:
        results = [con.foo(x) for x in range(10)]
        abc = con.a.abc.foo(10)
        xyz = con.a.xyz.foo(11)
        x12 = con.foo(12)
    print(con.results(), con[x12])
    print(con.list_results())
    print(con.dict_results())
    print(results, abc, xyz)

    sys.exit(0)


class MyPlugin(SimplePlugin):

    def __init__(self):
        super().__init__()
        # self.s1 = Search(addon=self, asdasdasdaasdasdasdasd)
        # self.s2 = Search(addon=self)
        # self.search.set_option(...)  # nazwa: wartości  jakość: auto 720p 1080 UHD
        # self.search.set_xml(...)  # nazwa: wartości  jakość: auto 720p 1080 UHD

        # self.foo(22)
        # data = self.get_gh()
        # print('GH REPO:', data['name'])
        # return

        self.site = Site()
        another_site = Site('https://doc.libka.pl/libka/')
        print('---')
        with self.site.concurrent() as con:
            con.a.aa.txtget('https://docs.python.org/3/library')
            con['bb'].txtget('https://mit-license.org')
            con.a.cc(another_site).txtget('utils.html')
        print(len(con.a.aa), len(con.a['bb']), len(con['cc']))
        print([len(v) for v in con.values()])
        print([f'{k}={len(v)}' for k, v in con.items()])
        # print(dict(con.a))

        print('---')
        with self.concurrent() as con:
            con[...].txtget('https://docs.python.org/3/library')
            # con().txtget('https://mit-license.org')
            # next(con).txtget('https://mit-license.org')
            con.txtget('https://mit-license.org')
            con[another_site].txtget('utils.html')
        print(len(con[0]), len(con[1]), len(con[2]))
        print([len(c) for c in con])

        print('---')
        with self.concurrent() as con:
            con[...].txtget('https://docs.python.org/3/library')
            con.txtget('https://mit-license.org')
            con['bb'].txtget('https://mit-license.org')
            con.a.cc(another_site).txtget('utils.html')
        print([len(c) for c in con], '0:', len(con[0]))
        print([len(v) for v in con.values()])
        print([f'{k}={len(v)}' for k, v in con.items()])

        return

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

    def yyy(self, a: PathArg, b: PathArg = 44, c=None):
        pass

    @cached
    def get_gh(self):
        log('Getting... GH')
        data = self.jget('https://api.github.com/repos/twbs/bootstrap')
        return data

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
