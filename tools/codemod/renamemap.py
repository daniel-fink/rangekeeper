"""Load the rename map and resolve old names to 1.0 names."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

import yaml

STATUSES = frozenset({"agreed", "draft", "pending", "open"})
APPLIED_STATUSES = frozenset({"agreed", "draft"})
REQUIREMENTS = frozenset({"schema", "refactor"})


class MapError(ValueError):
    """The rename map is not valid."""


@dataclass(frozen=True)
class Entry:
    """Fields common to every map entry."""

    status: str
    source: str = ""
    requires: tuple[str, ...] = ()
    note: str = ""
    pending: str = ""

    def applies(self, *, include_pending: bool, allow: frozenset[str]) -> bool:
        """Return true when the codemod applies this entry."""
        if self.status == "open":
            return False
        if self.status == "pending" and not include_pending:
            return False
        return set(self.requires) <= allow

    @property
    def needs_name(self) -> bool:
        """Return true when the entry has no 1.0 target to apply."""
        return False


@dataclass(frozen=True)
class ModuleMove(Entry):
    """Move a module and its submodules."""

    old: str = ""
    new: str = ""


@dataclass(frozen=True)
class PathMove(Entry):
    """Move a file or folder relative to the repository root."""

    old: str = ""
    new: str = ""


@dataclass(frozen=True)
class SymbolRename(Entry):
    """Rename a module-level name, or move it to another module."""

    module: str = ""
    name: str = ""
    new_name: str = ""
    new_module: str = ""

    @property
    def needs_name(self) -> bool:
        """Return true when the entry has no 1.0 target to apply."""
        return not (self.new_name or self.new_module)

    @property
    def target_name(self) -> str:
        """Return the 1.0 name."""
        return self.new_name or self.name


@dataclass(frozen=True)
class AttributeRename(Entry):
    """Rename an attribute, method or field of one class."""

    owner: str = ""
    name: str = ""
    new_name: str = ""
    apply: str = "review"


@dataclass(frozen=True)
class ParameterRename(Entry):
    """Rename a keyword parameter."""

    callable: str = ""
    name: str = ""
    new_name: str = ""


@dataclass(frozen=True)
class Removed(Entry):
    """A name with no direct replacement."""

    name: str = ""
    replacement: str = ""


@dataclass(frozen=True)
class Note(Entry):
    """A decision that changes an API shape, not a name."""

    topic: str = ""


_KINDS = {
    "modules": (ModuleMove, ("old", "new")),
    "paths": (PathMove, ("old", "new")),
    "symbols": (SymbolRename, ("module", "name")),
    "attributes": (AttributeRename, ("owner", "name", "new_name")),
    "parameters": (ParameterRename, ("callable", "name", "new_name")),
    "removed": (Removed, ("name", "replacement")),
    "notes": (Note, ("topic",)),
}


def _entry(kind: str, data: Mapping) -> Entry:
    cls, required = _KINDS[kind]
    if not isinstance(data, Mapping):
        raise MapError(f"{kind}: each entry must be a mapping")
    names = set(cls.__dataclass_fields__)
    unknown = set(data) - names
    if unknown:
        raise MapError(f"{kind}: unknown fields {sorted(unknown)} in {dict(data)}")
    missing = [name for name in (*required, "status") if not data.get(name)]
    if missing:
        raise MapError(f"{kind}: missing {missing} in {dict(data)}")
    if data["status"] not in STATUSES:
        raise MapError(
            f"{kind}: status {data['status']!r} is not one of {sorted(STATUSES)}"
        )
    if data["status"] == "pending" and not data.get("pending"):
        raise MapError(f"{kind}: a pending entry names its decision in `pending`")
    requires = tuple(data.get("requires", ()))
    if not set(requires) <= REQUIREMENTS:
        raise MapError(f"{kind}: requires {requires} is not in {sorted(REQUIREMENTS)}")
    if kind == "attributes" and data.get("apply", "review") not in {"all", "review"}:
        raise MapError(f"{kind}: apply must be 'all' or 'review'")
    values = {**data, "requires": requires}
    return cls(**values)


@dataclass
class RenameMap:
    """The rename map, filtered to the entries that one run applies."""

    package: str
    package_root: str
    exclude: tuple[str, ...]
    modules: tuple[ModuleMove, ...] = ()
    paths: tuple[PathMove, ...] = ()
    symbols: tuple[SymbolRename, ...] = ()
    attributes: tuple[AttributeRename, ...] = ()
    parameters: tuple[ParameterRename, ...] = ()
    removed: tuple[Removed, ...] = ()
    notes: tuple[Note, ...] = ()
    skipped: tuple[Entry, ...] = field(default=())

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        include_pending: bool = False,
        allow: Iterable[str] = (),
    ) -> RenameMap:
        """Read a map file and keep the entries that this run applies."""
        return cls.from_data(
            yaml.safe_load(Path(path).read_text(encoding="utf-8")),
            include_pending=include_pending,
            allow=allow,
        )

    @classmethod
    def from_data(
        cls,
        data: Mapping,
        *,
        include_pending: bool = False,
        allow: Iterable[str] = (),
    ) -> RenameMap:
        """Build a map from parsed YAML and keep the entries that this run applies."""
        if not isinstance(data, Mapping) or data.get("version") != 1:
            raise MapError("the rename map must be a mapping with `version: 1`")
        allowed = frozenset(allow)
        if not allowed <= REQUIREMENTS:
            raise MapError(f"unknown requirements {sorted(allowed - REQUIREMENTS)}")
        kept: dict[str, list[Entry]] = {kind: [] for kind in _KINDS}
        skipped: list[Entry] = []
        for kind in _KINDS:
            for item in data.get(kind) or ():
                entry = _entry(kind, item)
                if kind in {"removed", "notes"}:
                    kept[kind].append(entry)
                elif (
                    entry.applies(include_pending=include_pending, allow=allowed)
                    and not entry.needs_name
                ):
                    kept[kind].append(entry)
                else:
                    skipped.append(entry)
        result = cls(
            package=data.get("package", "rangekeeper"),
            package_root=data.get("package_root", ""),
            exclude=tuple(data.get("exclude") or ()),
            skipped=tuple(skipped),
            **{kind: tuple(entries) for kind, entries in kept.items()},  # type: ignore[arg-type]
        )
        result._check()
        return result

    def _check(self) -> None:
        seen: dict[str, str] = {}
        for move in self.modules:
            if move.old in seen:
                raise MapError(f"module {move.old} is moved twice")
            seen[move.old] = move.new
        for move in self.modules:
            if self.module(move.new) != move.new:
                raise MapError(
                    f"module move {move.old} -> {move.new} is not idempotent: "
                    f"{move.new} matches another move"
                )
        keys = [(s.module, s.name) for s in self.symbols]
        if len(keys) != len(set(keys)):
            raise MapError("a symbol is renamed twice")

    def excluded(self, relative: str) -> bool:
        """Return true when the codemod must not change this repository path."""
        return any(fnmatch(relative, pattern) for pattern in self.exclude)

    def module(self, name: str) -> str:
        """Return the 1.0 module for a dotted module name; longest prefix wins."""
        best = None
        for move in self.modules:
            if (name == move.old or name.startswith(move.old + ".")) and (
                best is None or len(move.old) > len(best.old)
            ):
                best = move
        if best is None:
            return name
        return best.new + name[len(best.old) :]

    def path(self, relative: str) -> str:
        """Return the 1.0 location for a repository path; longest prefix wins."""
        best = None
        for move in self.paths:
            if (relative == move.old or relative.startswith(move.old + "/")) and (
                best is None or len(move.old) > len(best.old)
            ):
                best = move
        if best is None:
            return relative
        return best.new + relative[len(best.old) :]
