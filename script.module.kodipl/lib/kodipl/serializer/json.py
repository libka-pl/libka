from typing import Union, Any
import json
from ..path import Path
from ..logs import log


class Json:
    """JSON serializer for user data."""

    SUFFIX = '.json'

    def __init__(self, *, pretty: bool = True, indent: int = 2):
        self.pretty = pretty
        self.indent = indent

    def load(self, path: Union[Path, str]) -> Any:
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            log.info(f'Missing data file {path}')
            return None
        except json.JSONDecodeError as exc:
            log.error(f'Decode data file {path} FAILED: {exc!r}')
            return {}

    def save(self, data: Any, path: Union[Path, str]) -> None:
        try:
            with open(path, 'w') as f:
                indent = self.indent if self.pretty else 0
                self._data = json.dump(data, f, indent=indent)
        except IOError as exc:
            log.error(f'AddonUserData({self.path}): save failed: {exc!r}')
