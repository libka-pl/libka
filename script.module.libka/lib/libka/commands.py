
from .routing import Call


class Commands:
    """
    Simple xmbc command wraper with method resolver (mkurl).
    """

    def __init__(self, *, addon, mkurl=None):
        self._addon = addon
        if mkurl is None:
            mkurl = self._addon.mkurl
        self._mkurl = mkurl

    def __getattr__(self, key):
        if key[:1] == '_':
            raise AttributeError(key)
        return CommandCall(key, mkurl=self._mkurl)


class CommandCall:
    """Simple call wrapper."""

    def __init__(self, name, *, mkurl):
        self.name = name
        self._mkurl = mkurl

    def __call__(self, method, *args, **kwargs):
        if args and isinstance(method, Call):
            items = [self._mkurl(method)]
            items.extend(args)
            items.extend(f'{k}={v}' for k, v in kwargs.items())
        else:
            items = [self._mkurl(method, *args, **kwargs)]
        return '{}({})'.format(self.name, ', '.join(str(a) for a in items))

    def __getattr__(self, key):
        if key[:1] == '_':
            raise AttributeError(key)
        return CommandCall(f'{self.name}.{key}', mkurl=self._mkurl)
