"""Plan and apply a rename pass over a repository or over consumer code."""

from __future__ import annotations

import ast
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import libcst as cst

from .names import Index, Resolver, absolute
from .python import Context, Locations, PythonRewriter, has_package
from .renamemap import MapError, RenameMap
from .report import Change, Report
from .text import SHORT, TextRewriter

PYTHON = frozenset({".py", ".pyi"})
TEXT = {
    ".md": "markdown",
    ".ipynb": "notebook",
    ".toml": "config",
    ".yml": "config",
    ".yaml": "config",
    ".cfg": "config",
    ".ini": "config",
    ".txt": "config",
    ".rst": "config",
}
_LINK = re.compile(
    r"(?P<head>\]\(\s*<?|^\s{0,3}\[[^\]\n]+\]:\s*<?)"
    r"(?P<path>[^\s)>#]+)(?P<fragment>#[^\s)>]*)?",
    re.MULTILINE,
)
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        "_build",
        ".mypy_cache",
        ".ruff_cache",
    }
)


@dataclass
class _File:
    old: str
    new: str
    text: str | None = None
    result: str | None = None


@dataclass
class Plan:
    """Every file change and move that one run makes, before it writes."""

    files: list[_File] = field(default_factory=list)
    data: list[tuple[str, str]] = field(default_factory=list)
    created: dict[str, str] = field(default_factory=dict)
    report: Report = field(default_factory=Report)


def build_index(package_root: Path, package: str) -> Index:
    """Read the package modules and the names that they re-export."""
    index = Index()
    files: dict[str, Path] = {}
    for path in sorted(package_root.rglob("*.py")):
        if SKIP_DIRS & set(path.relative_to(package_root).parts):
            continue
        parts = path.relative_to(package_root).with_suffix("").parts
        is_package = parts[-1] == "__init__"
        if is_package:
            parts = parts[:-1]
        name = ".".join((package, *parts))
        index.modules.add(name)
        if is_package:
            index.packages.add(name)
        files[name] = path
    for name, path in files.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        is_package = name in index.packages
        children = {
            m.rpartition(".")[2] for m in index.modules if m.rpartition(".")[0] == name
        }
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                source = absolute(
                    "." * node.level + (node.module or ""), name, package=is_package
                )
                if source is None or not (
                    source == package or source.startswith(package + ".")
                ):
                    continue
                for alias in node.names:
                    if alias.name == "*" or f"{source}.{alias.name}" in index.modules:
                        continue
                    index.aliases[(name, alias.asname or alias.name)] = (
                        source,
                        alias.name,
                    )
            elif (
                is_package
                and isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Dict)
            ):
                table = node.value
                pairs = [
                    (k.value, v.value)
                    for k, v in zip(table.keys, table.values, strict=True)
                    if isinstance(k, ast.Constant)
                    and isinstance(k.value, str)
                    and isinstance(v, ast.Constant)
                    and isinstance(v.value, str)
                ]
                if (
                    pairs
                    and len(pairs) == len(table.keys)
                    and {v for _, v in pairs} <= children
                ):
                    for key, child in pairs:
                        index.aliases.setdefault((name, key), (f"{name}.{child}", key))
    return index


def index_to_json(index: Index) -> str:
    """Freeze an index for consumer runs without the old package source."""
    return json.dumps(
        {
            "modules": sorted(index.modules),
            "packages": sorted(index.packages),
            "aliases": sorted([*k, *v] for k, v in index.aliases.items()),
        },
        indent=1,
    )


def index_from_json(text: str) -> Index:
    """Read an index written by index_to_json."""
    data = json.loads(text)
    return Index(
        modules=set(data["modules"]),
        packages=set(data["packages"]),
        aliases={(m, n): (om, on) for m, n, om, on in data["aliases"]},
    )


class Codemod:
    """One rename pass over the files under a root folder.

    In package mode the run also moves the package modules and the `paths`
    entries. In consumer mode it only rewrites references.
    """

    def __init__(
        self,
        root: Path,
        rename_map: RenameMap,
        *,
        consumer: bool = False,
        index: Index | None = None,
        targets: Sequence[str] = (),
    ) -> None:
        self.root = Path(root).resolve()
        self.map = rename_map
        self.consumer = consumer
        self.package_root = rename_map.package_root.strip("/")
        self.targets = tuple(t.strip("/") for t in targets)
        source = self.root / self.package_root
        if index is None:
            index = (
                build_index(source, rename_map.package)
                if self.package_root and source.is_dir()
                else Index()
            )
        self.index = index
        self.resolver = Resolver(rename_map, index)
        self.layout: dict[str, str] = {}
        self.layout_created: dict[str, str] = {}
        self.new_packages: set[str] = set()
        if not consumer and self.package_root and source.is_dir():
            self._plan_layout()
        self.locations = Locations(
            package_root=self.package_root,
            files={k: v for k, v in self.layout.items() if k != v},
            relocate=self.relocate,
            repository=self.map.path,
            folder=self._folder_target,
        )
        self.python = PythonRewriter(self.resolver, self.locations)
        self.text = TextRewriter(self.python, self.locations)

    # Layout

    def _module_of(self, relative: str) -> str:
        parts = PurePosixPath(relative).with_suffix("").parts
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join((self.map.package, *parts))

    def _path_of(self, module: str, *, package: bool) -> str:
        parts = module.split(".")[1:]
        if package:
            return "/".join([*parts, "__init__.py"])
        return "/".join(parts) + ".py"

    def _plan_layout(self) -> None:
        old: dict[str, str] = {}
        for name in sorted(self.index.modules):
            is_package = name in self.index.packages
            old[self._path_of(name, package=is_package)] = name
        new_names = {rel: self.map.module(name) for rel, name in old.items()}
        packages = {
            new for rel, new in new_names.items() if rel.endswith("__init__.py")
        }
        for new in new_names.values():
            parts = new.split(".")
            packages.update(".".join(parts[:i]) for i in range(1, len(parts)))
        seen: dict[str, str] = {}
        for rel, new in new_names.items():
            target = self._path_of(new, package=new in packages)
            if target in seen:
                raise MapError(f"{rel} and {seen[target]} both move to {target}")
            seen[target] = rel
            self.layout[rel] = target
        self.new_packages = packages
        for package in sorted(packages):
            path = self._path_of(package, package=True)
            if path not in seen:
                leaf = package.rpartition(".")[2]
                self.layout_created[path] = f'"""The {leaf} namespace."""\n'

    def relocate(self, relative: str) -> str:
        """Return the new package-relative path for an old file or folder path."""
        if relative in self.layout:
            return self.layout[relative]
        if relative.endswith(".py"):
            new = self.map.module(self._module_of(relative))
            return self._path_of(new, package=new in self.new_packages)
        if "." in PurePosixPath(relative).name:
            parent = str(PurePosixPath(relative).parent)
            return (
                str(PurePosixPath(self.relocate(parent)) / PurePosixPath(relative).name)
                if parent != "."
                else relative
            )
        new = self.map.module(
            ".".join((self.map.package, *PurePosixPath(relative).parts))
        )
        return "/".join(new.split(".")[1:])

    def _repository_target(self, relative: str) -> str:
        root = self.package_root
        if not self.consumer and root and relative.startswith(root + "/"):
            inner = relative[len(root) + 1 :]
            return f"{root}/{self.relocate(inner)}"
        return self.map.path(relative) if not self.consumer else relative

    def _folder_target(self, relative: str) -> str:
        root = self.package_root
        if not self.consumer and root and relative.startswith(root + "/"):
            inner = relative[len(root) + 1 :]
            return f"{root}/{self.relocate(inner)}"
        return self.map.path(relative) if not self.consumer else relative

    # Files

    def _discover(self) -> list[str]:
        if (self.root / ".git").exists():
            listed = subprocess.run(
                ["git", "ls-files", "-co", "--exclude-standard", "-z"],
                cwd=self.root,
                capture_output=True,
                check=True,
            ).stdout.decode()
            paths = [p for p in listed.split("\0") if p and (self.root / p).is_file()]
        else:
            paths = []
            for folder, dirs, names in os.walk(self.root):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for name in names:
                    paths.append(str((Path(folder) / name).relative_to(self.root)))
        if self.targets:
            paths = [
                p
                for p in paths
                if any(p == t or p.startswith(t + "/") for t in self.targets)
            ]
        return sorted(p.replace(os.sep, "/") for p in paths)

    def plan(self) -> Plan:
        """Compute every change without writing."""
        plan = Plan()
        report = plan.report
        report.skipped = self.map.skipped
        for relative in self._discover():
            suffix = PurePosixPath(relative).suffix
            target = self._repository_target(relative)
            excluded = self.map.excluded(relative)
            rewrite = (suffix in PYTHON or suffix in TEXT) and not excluded
            # Excluded Markdown keeps its words, but its links must still resolve.
            links_only = suffix == ".md" and excluded and not self.consumer
            if not rewrite and not links_only:
                if target != relative:
                    plan.data.append((relative, target))
                continue
            path = self.root / relative
            try:
                text = path.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                if target != relative:
                    plan.data.append((relative, target))
                continue
            if links_only:
                result, changes = text, []
            else:
                result, changes = self._rewrite(relative, text, suffix)
            if suffix == ".md" and not self.consumer:
                result, linked = self._links(relative, target, result)
                changes += linked
            result, fixed = self._fixups(relative, target, result)
            report.changes += changes + fixed
            if result != text or target != relative:
                plan.files.append(_File(relative, target, text, result))
        if not self.consumer:
            for path, content in self.layout_created.items():
                full = f"{self.package_root}/{path}"
                if not (self.root / full).exists():
                    plan.created[full] = content
        report.moves = sorted(
            [(f.old, f.new) for f in plan.files if f.old != f.new]
            + [m for m in plan.data]
        )
        report.created = sorted(plan.created)
        return plan

    def _links(
        self,
        relative: str,
        target: str,
        text: str,
    ) -> tuple[str, list[Change]]:
        """Point relative Markdown links at the new locations of moved files."""
        changes: list[Change] = []
        here = posixpath.dirname(relative)
        there = posixpath.dirname(target)

        def link(match: re.Match) -> str:
            path, fragment = match["path"], match["fragment"] or ""
            if ":" in path or path.startswith("/"):
                return match[0]
            old = posixpath.normpath(posixpath.join(here, path))
            if old.startswith(".."):
                return match[0]
            new = (
                self._repository_target(old)
                if (self.root / old).is_file()
                else self._folder_target(old)
            )
            if new == old and here == there:
                return match[0]
            moved = posixpath.relpath(new, there or ".")
            if path.endswith("/") and not moved.endswith("/"):
                moved += "/"
            if moved == path:
                return match[0]
            line = text[: match.start()].count("\n") + 1
            changes.append(Change(relative, line, "link", f"{path} -> {moved}"))
            return f"{match['head']}{moved}{fragment}"

        return _LINK.sub(link, text), changes

    def _fixups(
        self,
        relative: str,
        target: str,
        text: str,
    ) -> tuple[str, list[Change]]:
        changes = []
        for fixup in self.map.fixups:
            if fixup.path not in (relative, target):
                continue
            old, new = fixup.old, fixup.new
            if "\r\n" in text:
                # A Windows checkout can have CRLF line ends; the map uses LF.
                old, new = (
                    x.replace("\r\n", "\n").replace("\n", "\r\n") for x in (old, new)
                )
            count = text.count(old)
            if count > 1:
                detail = f"fixup {fixup.old!r} matches {count} times"
                changes.append(Change(relative, 0, "review", detail))
            elif count == 1:
                line = text[: text.index(old)].count("\n") + 1
                text = text.replace(old, new)
                detail = f"{fixup.old!r} -> {fixup.new!r}"
                changes.append(Change(relative, line, "fixup", detail))
        return text, changes

    def _rewrite(
        self,
        relative: str,
        text: str,
        suffix: str,
    ) -> tuple[str, list[Change]]:
        try:
            if suffix in PYTHON:
                module = None
                package = False
                root = self.package_root
                if root and relative.startswith(root + "/"):
                    inner = relative[len(root) + 1 :]
                    module = self._module_of(inner)
                    package = inner.endswith("__init__.py")
                    if module not in self.index.modules:
                        module = None
                context = Context(
                    path=relative,
                    module=module,
                    package=package,
                    uses_package=has_package(text, self.map.package),
                    target=self._repository_target(relative),
                )
                return self.python.rewrite(text, context)
            kind = TEXT[suffix]
            if not has_package(text, self.map.package, (SHORT,)) and "src/" not in text:
                return text, []
            if kind == "markdown":
                return self.text.markdown(text, relative)
            if kind == "notebook":
                return self.text.notebook(text, relative)
            return self.text.config(text, relative)
        except (cst.ParserSyntaxError, json.JSONDecodeError) as error:
            return text, [
                Change(relative, 0, "review", f"not parsed: {type(error).__name__}")
            ]

    # Writing

    def apply(self, plan: Plan, *, format_code: bool = False) -> None:
        """Write the plan to disk."""
        moved_from = []
        for item in plan.files:
            if item.old != item.new:
                (self.root / item.old).unlink()
                moved_from.append(item.old)
        for old, new in plan.data:
            target = self.root / new
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(self.root / old, target)
            moved_from.append(old)
        written = []
        for item in plan.files:
            target = self.root / item.new
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((item.result or "").encode("utf-8"))
            written.append(item.new)
        for path, content in plan.created.items():
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content.encode("utf-8"))
            written.append(path)
        self._prune(moved_from)
        if format_code:
            self._format(
                [
                    p
                    for p in written
                    if Path(p).suffix in PYTHON and not self.map.excluded(p)
                ]
            )

    def _prune(self, moved: Iterable[str]) -> None:
        folders = {(self.root / p).parent for p in moved}
        for folder in sorted(folders, key=lambda f: len(f.parts), reverse=True):
            while folder != self.root and folder.is_dir():
                cache = folder / "__pycache__"
                rest = [c for c in folder.iterdir() if c != cache]
                if rest:
                    break
                if cache.exists():
                    shutil.rmtree(cache)
                folder.rmdir()
                folder = folder.parent

    def _format(self, paths: list[str]) -> None:
        if not paths:
            return
        for command in (
            ["check", "--select", "I", "--fix", "--quiet"],
            ["format", "--quiet"],
        ):
            subprocess.run(
                [sys.executable, "-m", "ruff", *command, *paths],
                cwd=self.root,
                check=False,
            )

    def run(self, *, apply: bool = False, format_code: bool = False) -> Report:
        """Plan the pass, write it when `apply` is true, and return the report."""
        plan = self.plan()
        if apply:
            self.apply(plan, format_code=format_code)
        return plan.report
