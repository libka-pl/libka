#
# XXX  Test and debug only!
#


from . import Plugin, call


class MyPlugin(Plugin):

    def __init__(self):
        super().__init__()

    def home(self):
        with self.directory() as kd:
            kd.menu('Aaa', call(self.foo, 42))

    def foo(self, a):
        pass


MyPlugin().run()
