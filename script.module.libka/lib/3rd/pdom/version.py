from collections import namedtuple

VersionInfo = namedtuple('VersionInfo', ['major', 'minor', 'micro', 'patch'])
VersionInfo.__new__.__defaults__ = (0, 0, 0, 0)

version = '0.1.3'
version_info = VersionInfo(map(int, version.split('.')))
