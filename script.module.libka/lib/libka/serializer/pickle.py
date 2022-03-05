from typing import Union, Any
import pickle
from ..path import Path
from ..logs import log


class Pickle:
    """Pickle serializer for user data."""

    SUFFIX = '.pickle'

    def load(self, path: Union[Path, str]) -> Any:
        try:
            with open(path, 'rb') as f:
                return pickle.load(f)
        except FileNotFoundError:
            log.info(f'Missing data file {path}')
            return None
        except pickle.UnpicklingError as exc:
            log.error(f'Decode data file {path} FAILED: {exc!r}')
            return None

    def save(self, data: Any, path: Union[Path, str]) -> None:
        try:
            with open(path, 'wb') as f:
                pickle.dump(data, f)
        except IOError as exc:
            log.error(f'{self.__class__.__name__}({path}): save failed: {exc!r}')
