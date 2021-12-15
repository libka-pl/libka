import sys
import os.path

__version__ = '0.0.1'


# Add paths to 3rd-party libs
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '3rd'))
if sys.version_info < (3, 0):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '3rdpy2'))

# Make aliases, most modules are located like in py3
from future import standard_library
standard_library.install_aliases()

# Missing aliases
if sys.version_info < (3, 0):
    import collections
    sys.modules['collections.abc'] = collections
