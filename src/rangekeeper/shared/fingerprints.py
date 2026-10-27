"""Pure digest and source-closure mechanics; each subsystem owns its manifest."""

import ast
import hashlib
import json
import os
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path


class _WithoutDocstrings(ast.NodeTransformer):
    def visit_Module(self, node):
        return self._body(node)

    def visit_ClassDef(self, node):
        return self._body(node)

    def visit_FunctionDef(self, node):
        return self._body(node)

    def visit_AsyncFunctionDef(self, node):
        return self._body(node)

    def _body(self, node):
        self.generic_visit(node)
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            node.body = node.body[1:]
        return node


# The caches take the source text as the key, so a changed file is parsed again.
@lru_cache(maxsize=1024)
def semantic_digest(source: str) -> str:
    """Hash executable syntax and constants, excluding comments and docstrings."""
    tree = _WithoutDocstrings().visit(ast.parse(source))
    return hashlib.sha256(
        ast.dump(tree, include_attributes=False).encode("utf-8")
    ).hexdigest()


def manifest_digest(manifest: dict) -> str:
    """Encode an explicit manifest without timestamps or install-path inference."""
    data = json.dumps(
        manifest,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1024)
def _parse(source: str) -> ast.Module:
    """Parse a source once; callers must not change the shared tree."""
    return ast.parse(source)


class _Package:
    """Resolve static imports to source files under one package directory."""

    def __init__(self, package: Path, root: str) -> None:
        self.package, self.root = package, root
        self.trees: dict[str, ast.Module] = {}

    def file(self, module: str) -> str | None:
        """Return a module's relative source path; names match case-sensitively."""
        parts = module.split(".")
        if parts[0] != self.root:
            return None
        folder = self.package.joinpath(*parts[1:-1])
        if len(parts) == 1:
            stem, folder = "", self.package
        else:
            stem = parts[-1]
        try:
            names = set(os.listdir(folder))
        except (FileNotFoundError, NotADirectoryError):
            return None
        prefix = "/".join(parts[1:])
        if stem and stem + ".py" in names:
            return prefix + ".py"
        if (not stem or stem in names) and (
            "__init__.py" in os.listdir(self.package / prefix)
        ):
            return (prefix + "/" if prefix else "") + "__init__.py"
        return None

    def tree(self, path: str) -> ast.Module:
        if path not in self.trees:
            self.trees[path] = _parse((self.package / path).read_text())
        return self.trees[path]

    def module(self, path: str) -> str:
        parts = [self.root, *path.removesuffix(".py").split("/")]
        return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)

    def absolute(self, path: str, name: str | None, level: int) -> str:
        """Resolve a relative import against the importing module."""
        if not level:
            return name or ""
        base = self.module(path).split(".")
        if not path.endswith("__init__.py"):
            base = base[:-1]
        base = base[: len(base) - level + 1]
        return ".".join([*base, name] if name else base)

    def require(self, module: str) -> str:
        path = self.file(module)
        if path is None:
            raise ModuleNotFoundError(f"{module} has no source in {self.package}")
        return path

    def binding(self, module: str, name: str, seen: frozenset = frozenset()) -> str:
        """Return the file that defines a name taken from a module."""
        submodule = self.file(f"{module}.{name}")
        if submodule is not None:
            return submodule
        path = self.require(module)
        if not path.endswith("__init__.py") or (module, name) in seen:
            return path
        for node in self._top_level(self.tree(path).body):
            if isinstance(node, ast.ImportFrom):
                source = self.absolute(path, node.module, node.level)
                for alias in node.names:
                    if (alias.asname or alias.name) == name and source.startswith(
                        self.root
                    ):
                        return self.binding(source, alias.name, seen | {(module, name)})
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname == name:
                        return self.require(alias.name)
        return path

    @staticmethod
    def _top_level(body):
        for node in body:
            # TYPE_CHECKING re-exports name the module that a lazy export loads.
            if isinstance(node, ast.If):
                yield from _Package._top_level(node.body)
                yield from _Package._top_level(node.orelse)
            else:
                yield node

    def imports(self, path: str) -> set[str]:
        """Return the files that one module's import statements reach."""
        found: set[str] = set()
        for node in ast.walk(self.tree(path)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] == self.root:
                        found.add(self.require(alias.name))
            elif isinstance(node, ast.ImportFrom):
                source = self.absolute(path, node.module, node.level)
                if source.split(".")[0] != self.root:
                    continue
                for alias in node.names:
                    found.add(
                        self.require(source)
                        if alias.name == "*"
                        else self.binding(source, alias.name)
                    )
            elif (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", getattr(node.func, "attr", None))
                == "import_module"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                # Lazy exports load literal module names through import_module.
                name = node.args[0].value
                level = len(name) - len(name.lstrip("."))
                module = self.absolute(path, name.lstrip(".") or None, level)
                if module.split(".")[0] == self.root:
                    found.add(self.require(module))
        return found


def import_closure(
    entries: Iterable[str],
    *,
    package: Path,
    root: str = "rangekeeper",
) -> tuple[str, ...]:
    """Find the package source files that entry modules import, without importing.

    Entries and results are paths relative to the package directory. The closure
    follows each import statement in each reached module, including imports in
    functions and TYPE_CHECKING blocks. A name taken from a package resolves to
    the module that defines it: a package __init__ joins the closure only when it
    defines the name itself or loads it lazily. Parent package __init__ modules
    that Python runs on import are not part of the computation. A missing entry
    or imported module fails explicitly.
    """
    resolver = _Package(package, root)
    pending = list(entries)
    found: set[str] = set()
    while pending:
        path = pending.pop()
        if path not in found:
            found.add(path)
            pending.extend(resolver.imports(path))
    return tuple(sorted(found))
