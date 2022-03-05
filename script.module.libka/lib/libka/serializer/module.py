from typing import Union, Any
from ..path import Path
from ..logs import log


class Module:
    """Custom module serializer for user data. Module must have `load()` and `dump()` functions."""

    SUFFIX = '.data'

    def __init__(self, *, module):
        self.module = module

    def load(self, path: Union[Path, str]) -> Any:
        try:
            with open(path, 'rb') as f:
                return self.module.load(f)
        except FileNotFoundError:
            log.info(f'Missing data file {path}')
            return None
        except IOError:
            raise
        except Exception as exc:
            log.error(f'Decode data file {path} FAILED: {exc!r}')
            return None

    def save(self, data: Any, path: Union[Path, str]) -> None:
        try:
            with open(path, 'wb') as f:
                self.module.dump(data, f)
        except IOError as exc:
            log.error(f'{self.__class__.__name__}({path}): save failed: {exc!r}')
