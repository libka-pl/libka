#
# XXX  Test and debug only!
#


from . import Plugin


class MyPlugin(Plugin):

    def __init__(self):
        super().__init__()


plugin = MyPlugin()
