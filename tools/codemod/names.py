"""Resolve qualified names through the module moves, renames and re-exports."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .renamemap import (
    AttributeRename,
    ParameterRename,
    Removed,
    RenameMap,
    SymbolRename,
)


def absolute(name: str, module: str | None, *, package: bool) -> str | None:
    """Resolve a relative dotted name from `module`; return None if it cannot."""
    level = len(name) - len(name.lstrip("."))
    if not level:
        return name
    if module is None:
        return None
    parts = module.split(".")
    if not package:
        parts = parts[:-1]
    if level > 1:
        if level - 1 > len(parts):
            return None
        parts = parts[: len(parts) - (level - 1)]
    rest = name[level:]
    return ".".join([*parts, rest] if rest else parts)


def relative(target: str, module: str, *, package: bool, level: int) -> str | None:
    """Express `target` with `level` leading dots from `module`, if it is inside."""
    parts = module.split(".")
    if not package:
        parts = parts[:-1]
    if level > 1:
        parts = parts[: len(parts) - (level - 1)]
    base = ".".join(parts)
    if target == base:
        return "." * level
    if base and target.startswith(base + "."):
        return "." * level + target[len(base) + 1 :]
    return None


@dataclass
class Index:
    """Modules of the old package and the names that packages re-export.

    `aliases` maps (module, name) to the (module, name) that it re-exports.
    """

    modules: set[str] = field(default_factory=set)
    packages: set[str] = field(default_factory=set)
    aliases: dict[tuple[str, str], tuple[str, str]] = field(default_factory=dict)


class Resolver:
    """Map qualified names of the old package to their 1.0 names."""

    def __init__(self, rename_map: RenameMap, index: Index) -> None:
        self.map = rename_map
        self.index = index
        self.package = rename_map.package
        self.symbols: dict[tuple[str, str], SymbolRename] = {
            (rename_map.module(s.module), s.name): s for s in rename_map.symbols
        }
        self.aliases = {
            (self.map.module(m), n): (self.map.module(om), on)
            for (m, n), (om, on) in index.aliases.items()
        }
        self.attributes: dict[tuple[str, str], AttributeRename] = {}
        self.any_owner: dict[str, AttributeRename] = {}
        for a in rename_map.attributes:
            if a.owner == "*":
                self.any_owner[a.name] = a
            else:
                owner = self.symbol(rename_map.module(a.owner))
                self.attributes[(owner, a.name)] = a
        self.by_name: dict[str, list[AttributeRename]] = {}
        for a in rename_map.attributes:
            self.by_name.setdefault(a.name, []).append(a)
        self.parameters: dict[str, ParameterRename] = {}
        self.any_parameter: dict[str, ParameterRename] = {}
        for p in rename_map.parameters:
            if p.callable == "*":
                self.any_parameter[p.name] = p
            else:
                self.parameters[
                    self.symbol(rename_map.module(p.callable)) + "." + p.name
                ] = p
        self.removed: dict[str, Removed] = {
            self.map.module(r.name): r for r in rename_map.removed
        }
        self.modules = {self.map.module(m) for m in index.modules} | {
            m.new for m in rename_map.modules
        }

    def inside(self, name: str) -> bool:
        """Return true for a name in the package namespace."""
        return name == self.package or name.startswith(self.package + ".")

    def is_module(self, name: str) -> bool:
        """Return true when the dotted name is a module, before or after the moves."""
        return (
            name in self.index.modules
            or self.map.module(name) in self.modules
            or any(name == m.old for m in self.map.modules)
        )

    def _origin(self, module: str, name: str) -> tuple[SymbolRename | None, bool]:
        """Follow re-exports to a renamed symbol; the flag says the name is kept."""
        key = (module, name)
        same = True
        for _ in range(16):
            if key in self.symbols:
                return self.symbols[key], same
            if key not in self.aliases:
                return None, same
            origin = self.aliases[key]
            same = same and origin[1] == key[1]
            key = origin
        return None, same

    def symbol(self, qualified: str) -> str:
        """Apply the module moves and symbol renames to a qualified name."""
        name = self.map.module(qualified)
        parts = name.split(".")
        for i in range(len(parts) - 1, 0, -1):
            module = ".".join(parts[:i])
            entry, same = self._origin(module, parts[i])
            if entry is None:
                continue
            if entry.new_module:
                head = self.map.module(entry.new_module).split(".")
                return ".".join([*head, entry.target_name, *parts[i + 1 :]])
            if not same:
                return name
            return ".".join([*parts[:i], entry.target_name, *parts[i + 1 :]])
        return name

    def qualified(self, qualified: str) -> str:
        """Apply moves, symbol renames and qualified attribute renames."""
        name = self.symbol(qualified)
        parts = name.split(".")
        for i in range(len(parts) - 1, 1, -1):
            entry = self.attributes.get((self.canonical(".".join(parts[:i])), parts[i]))
            if entry is not None:
                return ".".join([*parts[:i], entry.new_name, *parts[i + 1 :]])
        return name

    def canonical(self, qualified: str) -> str:
        """Follow re-exports of a qualified name to the module that defines it."""
        module, _, name = qualified.rpartition(".")
        key = (module, name)
        for _ in range(16):
            if key not in self.aliases:
                break
            key = self.aliases[key]
        return ".".join(key)

    def removal(self, qualified: str) -> Removed | None:
        """Return the removal entry for a qualified name or its owner module."""
        name = self.map.module(qualified)
        while name:
            if name in self.removed:
                return self.removed[name]
            name = name.rpartition(".")[0]
        return None

    def renamed_under(self, package: str) -> dict[str, str]:
        """Return old to new names of symbols renamed in a package or its direct children."""
        found: dict[str, set[str]] = {}
        new_package = self.map.module(package)
        for (module, name), entry in self.symbols.items():
            if entry.new_name and new_package in (module, module.rpartition(".")[0]):
                found.setdefault(name, set()).add(entry.new_name)
        return {old: next(iter(new)) for old, new in found.items() if len(new) == 1}

    def children(self, package: str, names: Iterable[str]) -> dict[str, str]:
        """Map old child names of a package to new names when they stay inside it."""
        result = {}
        for child in names:
            old = f"{package}.{child}"
            new = self.map.module(old)
            parent, _, leaf = new.rpartition(".")
            if new != old and parent == self.map.module(package):
                result[child] = leaf
        return result
