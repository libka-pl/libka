
from typing import Union, Any
from ..path import Path


class SerializerType:

    def load(self, path: Union[Path, str]) -> Any:
        ...

    def save(self, data: Any, path: Union[Path, str]) -> None:
        ...
