"""One lazy-export helper for package ``__init__`` modules."""

import sys
from collections.abc import Callable, Iterable, Mapping
from importlib import import_module
from typing import Any


def lazy(
    package: str,
    *,
    names: Mapping[str, str] | None = None,
    modules: Iterable[str] = (),
) -> tuple[Callable[[str], Any], Callable[[], list[str]]]:
    """Return ``__getattr__`` and ``__dir__`` that load on first access.

    ``names`` maps an exported name to the submodule, relative to ``package``,
    that defines it. ``modules`` are submodules that load by their own name. A
    loaded value is kept in the package namespace, so it loads only once.
    """
    exports = dict(names or {})
    submodules = frozenset(modules)
    namespace = sys.modules[package].__dict__

    def __getattr__(name: str) -> Any:
        if name in exports:
            value = getattr(import_module(f".{exports[name]}", package), name)
        elif name in submodules:
            value = import_module(f".{name}", package)
        else:
            raise AttributeError(f"module {package!r} has no attribute {name!r}")
        namespace[name] = value
        return value

    def __dir__() -> list[str]:
        return sorted({*namespace, *exports, *submodules})

    return __getattr__, __dir__
