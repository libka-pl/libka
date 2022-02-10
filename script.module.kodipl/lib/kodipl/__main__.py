#
# XXX  Test and debug only!
#


from . import Plugin, call


class MyPlugin(Plugin):

    def __init__(self):
        super().__init__()

    def home(self):
        with self.directory(type='music') as kd:
            kd.menu('Aaa', call(self.foo, 42))

    def foo(self, a):
        print(f'foo(a={a!r})')


MyPlugin().run()
