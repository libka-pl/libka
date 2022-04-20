"""
Register common global objects.
"""

from typing import (
    Optional, Any,
    Dict,
)
from collections.abc import Callable
# from functools import wraps


class Registry:
    """
    Register database for any kind instance/object/module/method.
    """

    def __init__(self):
        #: All instances.
        self._instances: Dict[str, Any] = {}
        #: All factories.
        self._factory: Dict[str, Callable] = {}

    def __getattr__(self, name: str) -> Any:
        """
        Get instance, create if missing.
        """
        if name in self._instances:
            return self._instances[name]
        try:
            factory = self._factory[name]
        except KeyError:
            raise AttributeError(f'Missing factory for instance {name}') from None
        instance = factory()
        self._instances[name] = instance
        return instance


class RegistryOffice:
    """
    Register database for any kind instance/object/module/method.
    """

    def __init__(self, *, registry):
        #: Registry.
        self.registry: Registry = registry

    def register_factory(self, name: str, factory: Callable) -> None:
        """
        Register anything factory.
        """
        if isinstance(name, str):
            names = [name]
        else:
            names = name
        for name in names:
            self.registry._factory[name] = factory

    def get(self, name: str) -> Any:
        """
        Get instance, create if missing.
        """
        return getattr(self.registry, name)


#: Global registry.
registry = Registry()

#: Global registery factory.
registry_factory = RegistryOffice(registry=registry)


def register_factory(*args, name: Optional[str] = None) -> Callable:
    """Decorator for register factory."""

    def decorator(method: Callable) -> Callable:
        key: str
        if name is None:
            key = method.__name__
            if key.startswith('create_'):
                key = key[len('create_'):]
        else:
            key = name
        registry_factory.register_factory(key, method)
        return method

    if len(args) > 1:
        raise TypeError('Too many positional arguments, use @cached or @cached(key=value, ...)')
    method = args and args[0]
    # with parameters: @cache()
    if method is None:
        return decorator
    # w/o parameters: @cache
    return decorator(method)


register_singleton = register_factory
