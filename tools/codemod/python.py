"""Rewrite Python source: imports, references, definitions, keywords and strings."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import PurePosixPath

import libcst as cst
import libcst.matchers as m
from libcst.metadata import (
    MetadataWrapper,
    ParentNodeProvider,
    PositionProvider,
    QualifiedNameProvider,
    ScopeProvider,
)

from .names import Resolver, absolute, relative
from .report import Change


def dotted_pattern(*names: str) -> re.Pattern[str]:
    """Match dotted names that start with one of `names`."""
    heads = "|".join(re.escape(n) for n in names)
    return re.compile(rf"(?<![\w.])(?P<name>(?:{heads})(?:\.[A-Za-z_]\w*)+)")


_FILE = m.Call(
    func=m.Name("Path") | m.Attribute(attr=m.Name("Path")),
    args=[m.Arg(m.Name("__file__"))],
)
_PARENTS = m.Attribute(
    value=_FILE
    | m.Call(
        func=m.Attribute(value=_FILE, attr=m.Name("resolve") | m.Name("absolute"))
    ),
    attr=m.Name("parents"),
)
_WORD = re.compile(r"(?<![\w.])[A-Za-z_]\w*")
REPO_PATH = re.compile(r"(?<![\w/.-])(?P<path>src/[\w/.-]*[\w/])")


@dataclass
class Context:
    """What the rewriter knows about one file."""

    path: str
    module: str | None = None
    package: bool = False
    uses_package: bool = False
    # The repository path after the moves, when the file moves.
    target: str | None = None


@dataclass
class Locations:
    """Repository and package paths before and after the moves."""

    package_root: str = ""
    # Old package-relative path to new package-relative path, for moved files.
    files: Mapping[str, str] = field(default_factory=dict)
    # Map an old package-relative path (file or folder) to its new path.
    relocate: Callable[[str], str] = lambda path: path
    # Map an old repository path to its new path (the `paths` moves).
    repository: Callable[[str], str] = lambda path: path
    # Map an old repository folder to its new folder, for all moves.
    folder: Callable[[str], str] = lambda path: path


def rewrite_text(
    text: str, resolver: Resolver, locations: Locations, *, short: str = ""
) -> str:
    """Rewrite dotted names and repository paths in plain text.

    `short` is an extra alias of the package, such as `rk`, for prose.
    """
    package = resolver.package
    pattern = dotted_pattern(package, short) if short else dotted_pattern(package)

    def dotted(match: re.Match) -> str:
        name = match["name"]
        if short and name.startswith(short + "."):
            new = resolver.qualified(package + name[len(short) :])
            return short + new[len(package) :] if resolver.inside(new) else name
        return resolver.qualified(name)

    def path(match: re.Match) -> str:
        return _repository_path(match["path"], locations)

    return REPO_PATH.sub(path, pattern.sub(dotted, text))


def _repository_path(path: str, locations: Locations) -> str:
    root = locations.package_root.rstrip("/")
    if root and (path == root or path.startswith(root + "/")):
        inner = path[len(root) + 1 :]
        if not inner:
            return path
        trailing = "/" if inner.endswith("/") else ""
        return f"{root}/{locations.relocate(inner.rstrip('/'))}{trailing}"
    return locations.repository(path)


@dataclass
class _ImportPlan:
    statements: list[cst.ImportFrom] | None
    renames: list[tuple[str, str]]
    removed: list[tuple[str, str]]


class PythonRewriter:
    """Rewrite one Python module with a resolver."""

    def __init__(self, resolver: Resolver, locations: Locations) -> None:
        self.resolver = resolver
        self.locations = locations

    def rewrite(self, source: str, context: Context) -> tuple[str, list[Change]]:
        """Return the new source and the changes; raise ParserSyntaxError on bad input."""
        module = cst.parse_module(source)
        wrapper = MetadataWrapper(module, unsafe_skip_copy=True)
        transformer = _Transformer(self.resolver, self.locations, context, wrapper)
        result = wrapper.visit(transformer)
        return result.code, transformer.changes


class _Transformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (
        QualifiedNameProvider,
        PositionProvider,
        ScopeProvider,
        ParentNodeProvider,
    )

    def __init__(
        self,
        resolver: Resolver,
        locations: Locations,
        context: Context,
        wrapper: MetadataWrapper,
    ) -> None:
        super().__init__()
        self.resolver = resolver
        self.map = resolver.map
        self.locations = locations
        self.context = context
        self.changes: list[Change] = []
        self.module_new = self.map.module(context.module) if context.module else None
        self.positions = wrapper.resolve(PositionProvider)
        self.scopes = wrapper.resolve(ScopeProvider)
        self.parents = wrapper.resolve(ParentNodeProvider)
        self.root = wrapper.module
        self.names: dict[cst.CSTNode, str] = {}
        self.strings: dict[cst.CSTNode, dict[str, str]] = {}
        self.imports: dict[cst.CSTNode, _ImportPlan] = {}
        self.definitions: dict[cst.CSTNode, str] = {}
        # Renamed bindings, for string annotations that scopes do not track.
        self.bindings: dict[str, str] = {}
        self.import_depth = 0
        root = wrapper.module
        self.uses_package = (
            context.uses_package
            or context.module is not None
            or any(
                self._imports_package(node)
                for node in m.findall(root, m.Import() | m.ImportFrom())
            )
        )
        self.package_names: dict[str, str] = {}
        self.outside_children: set[str] = set()
        self.new_children: list[str] = []
        self.old_children: set[str] = set()
        if context.package and context.module:
            self._package_tables()
        self._plan_imports(root)
        self._plan_definitions(root)
        self._plan_parameters(root)

    # Helpers

    def line(self, node: cst.CSTNode) -> int:
        position = self.positions.get(node)
        return position.start.line if position else 0

    def record(self, node: cst.CSTNode, kind: str, detail: str) -> None:
        change = Change(self.context.path, self.line(node), kind, detail)
        if kind == "removed" and change in self.changes:
            return
        self.changes.append(change)

    def _absolute(self, name: str) -> str | None:
        return absolute(name, self.context.module, package=self.context.package)

    def _imports_package(self, node: cst.Import | cst.ImportFrom) -> bool:
        if isinstance(node, cst.Import):
            return any(
                self.resolver.inside(_dotted(alias.name)) for alias in node.names
            )
        if node.relative:
            return self.context.module is not None
        return node.module is not None and self.resolver.inside(_dotted(node.module))

    def _rename(self, scope, local: str, new: str, owner: cst.CSTNode | None) -> bool:
        """Rename a binding and its references in one scope; false on a clash."""
        if any(
            a.scope is scope and a.node is not owner for a in scope.assignments[new]
        ):
            return False
        for assignment in scope.assignments[local]:
            if owner is not None and assignment.node is not owner:
                continue
            for reference in assignment.references:
                if isinstance(reference.node, cst.Name):
                    self.names[reference.node] = new
        return True

    def _rename_all(self, old: str, new: str) -> None:
        """Rename a string in this module's __all__."""
        for target in m.findall(
            self.root,
            m.Assign(targets=[m.AssignTarget(target=m.Name("__all__"))])
            | m.AugAssign(target=m.Name("__all__"))
            | m.AnnAssign(target=m.Name("__all__")),
        ):
            for string in m.findall(target, m.SimpleString()):
                if string.raw_value == old:
                    self.strings.setdefault(string, {})[old] = new

    # Planning

    def _package_tables(self) -> None:
        package = self.context.module
        assert package is not None
        new_package = self.map.module(package)
        children = {
            name.rpartition(".")[2]
            for name in self.resolver.index.modules
            if name.rpartition(".")[0] == package
        }
        self.old_children = children
        self.package_names = {
            **self.resolver.renamed_under(package),
            **self.resolver.children(package, children),
        }
        for child in children:
            new = self.map.module(f"{package}.{child}")
            if new.rpartition(".")[0] != new_package:
                self.outside_children.add(child)
        moved = {
            self.map.module(name)
            for name in self.resolver.index.modules
            if self.map.module(name) != name
        }
        self.new_children = sorted(
            leaf
            for name in moved
            if name.rpartition(".")[0] == new_package
            and not (leaf := name.rpartition(".")[2]).startswith("_")
            and leaf not in children
            and leaf not in self.package_names.values()
        )

    def _plan_imports(self, root: cst.Module) -> None:
        for node in m.findall(root, m.ImportFrom()):
            plan = self._plan_from(node)
            if plan is not None:
                self.imports[node] = plan

    def _plan_from(self, node: cst.ImportFrom) -> _ImportPlan | None:
        level = len(node.relative)
        text = "." * level + (_dotted(node.module) if node.module else "")
        source = self._absolute(text)
        if source is None or not self.resolver.inside(source):
            return None
        scope = self.scopes.get(node)
        if isinstance(node.names, cst.ImportStar):
            target = self.map.module(source)
            if target == source and (
                not level
                or relative(
                    source,
                    self.module_new or "",
                    package=self.context.package,
                    level=level,
                )
                == text
            ):
                return None
            statement = self._statement(node, target, level, list_names=None)
            return _ImportPlan([statement] if statement is not None else None, [], [])
        groups: dict[str, list[cst.ImportAlias]] = {}
        unchanged = True
        renames: list[tuple[str, str]] = []
        removed: list[tuple[str, str]] = []
        for alias in node.names:
            name = _dotted(alias.name)
            local = alias.asname.name.value if alias.asname else None  # type: ignore[union-attr]
            full = f"{source}.{name}"
            entry = self.resolver.removal(full)
            if entry is not None:
                removed.append((entry.name, entry.replacement))
            if self.resolver.is_module(full):
                new = self.map.module(full)
                parent, _, leaf = new.rpartition(".")
                asname = local if local else (name if leaf != name else None)
            else:
                new = self.resolver.symbol(full)
                parent, _, leaf = new.rpartition(".")
                asname = local
                if local == name:
                    asname = leaf
                bound, new_bound = local or name, asname or leaf
                if bound != new_bound and scope is not None:
                    if self._rename(scope, bound, new_bound, node):
                        renames.append((bound, new_bound))
                        self.bindings[bound] = new_bound
                    else:
                        asname = bound
                        self.changes.append(
                            Change(
                                self.context.path,
                                self.line(node),
                                "review",
                                f"{new_bound} is already bound; kept the local name {bound}",
                            )
                        )
            unchanged = (
                unchanged and parent == source and leaf == name and asname == local
            )
            changed = alias.with_changes(
                name=cst.Name(leaf),
                asname=cst.AsName(name=cst.Name(asname)) if asname else None,
            )
            groups.setdefault(parent, []).append(changed)
        if unchanged and level and self.module_new:
            unchanged = (
                relative(
                    source, self.module_new, package=self.context.package, level=level
                )
                == text
            )
        if unchanged:
            return _ImportPlan(None, renames, removed)
        statements = [
            self._statement(node, parent, level, list_names=aliases)
            for parent, aliases in groups.items()
        ]
        return _ImportPlan(statements, renames, removed)

    def _statement(
        self,
        node: cst.ImportFrom,
        target: str,
        level: int,
        *,
        list_names: list[cst.ImportAlias] | None,
    ) -> cst.ImportFrom:
        text = None
        if level and self.module_new:
            text = relative(
                target, self.module_new, package=self.context.package, level=level
            )
        if text is None:
            text = target
        dots = len(text) - len(text.lstrip("."))
        rest = text[dots:]
        names: cst.ImportStar | list[cst.ImportAlias]
        keep = bool(node.lpar) and list_names is not None and len(list_names) > 1
        if list_names is None:
            names = cst.ImportStar()
        else:
            last = len(list_names) - 1
            space = cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))
            names = []
            for i, alias in enumerate(list_names):
                if keep:
                    comma = alias.comma
                    if i < last and not isinstance(comma, cst.Comma):
                        comma = space
                else:
                    comma = cst.MaybeSentinel.DEFAULT if i == last else space
                names.append(alias.with_changes(comma=comma))
        return node.with_changes(
            relative=[cst.Dot()] * dots,
            module=cst.parse_expression(rest) if rest else None,
            names=names,
            lpar=node.lpar if keep else None,
            rpar=node.rpar if keep else None,
        )

    def _plan_definitions(self, root: cst.Module) -> None:
        if self.module_new is None:
            return
        scope = self.scopes.get(root)
        for (module, name), entry in self.resolver.symbols.items():
            if module != self.module_new or not entry.new_name or entry.new_module:
                continue
            definitions = [
                a
                for a in scope.assignments[name]
                if not isinstance(a.node, (cst.Import, cst.ImportFrom))
            ]
            if not definitions:
                continue
            new = entry.new_name
            if any(
                a.node not in {d.node for d in definitions}
                for a in scope.assignments[new]
            ):
                self.changes.append(
                    Change(
                        self.context.path,
                        0,
                        "review",
                        f"{new} is already bound; did not rename {name}",
                    )
                )
                continue
            for assignment in definitions:
                target = assignment.node
                if isinstance(target, (cst.ClassDef, cst.FunctionDef)):
                    self.definitions[target.name] = new
                elif isinstance(target, cst.Name):
                    self.definitions[target] = new
                for reference in assignment.references:
                    if isinstance(reference.node, cst.Name):
                        self.names[reference.node] = new
            self._rename_all(name, new)
            self.bindings[name] = new
        for plan in self.imports.values():
            for old, new in plan.renames:
                self._rename_all(old, new)
        # Attribute and field definitions on owner classes.
        for cls in root.body:
            if not isinstance(cls, cst.ClassDef):
                continue
            owner = f"{self.module_new}.{cls.name.value}"
            for statement in cls.body.body:
                target = None
                if isinstance(statement, cst.FunctionDef):
                    target = statement.name
                elif isinstance(statement, cst.SimpleStatementLine):
                    for small in statement.body:
                        if isinstance(small, cst.AnnAssign) and isinstance(
                            small.target, cst.Name
                        ):
                            target = small.target
                if target is None:
                    continue
                entry = self.resolver.attributes.get(
                    (self.resolver.canonical(owner), target.value)
                )
                if entry is None:
                    continue
                if entry.apply == "all":
                    self.definitions[target] = entry.new_name
                else:
                    self.changes.append(
                        Change(
                            self.context.path,
                            self.line(target),
                            "review",
                            f"definition {owner}.{target.value} -> {entry.new_name}",
                        )
                    )

    def _plan_parameters(self, root: cst.Module) -> None:
        if not self.resolver.any_parameter:
            return
        for function in m.findall(root, m.FunctionDef() | m.Lambda()):
            params = function.params
            for param in (
                *params.posonly_params,
                *params.params,
                *params.kwonly_params,
            ):
                entry = self.resolver.any_parameter.get(param.name.value)
                if entry is None:
                    continue
                scope = self.scopes.get(param.name) or self.scopes.get(param)
                if scope is None or not self._rename(
                    scope, entry.name, entry.new_name, param
                ):
                    self.record(
                        param,
                        "review",
                        f"parameter {entry.name} -> {entry.new_name} clashes",
                    )
                    continue
                self.definitions[param.name] = entry.new_name

    # Transformation

    def visit_Import(self, node: cst.Import) -> None:
        self.import_depth += 1

    def leave_Import(self, original: cst.Import, updated: cst.Import) -> cst.Import:
        self.import_depth -= 1
        names = []
        changed = False
        for alias in updated.names:
            name = _dotted(alias.name)
            if self.resolver.inside(name) and self.resolver.is_module(name):
                new = self.map.module(name)
                if new != name:
                    changed = True
                    alias = alias.with_changes(name=cst.parse_expression(new))
            names.append(alias)
        if changed:
            self.record(
                original,
                "import",
                f"import {_code(original)} -> {_code(updated.with_changes(names=names))}",
            )
            return updated.with_changes(names=names)
        return updated

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        self.import_depth += 1

    def leave_ImportFrom(
        self, original: cst.ImportFrom, updated: cst.ImportFrom
    ) -> cst.ImportFrom:
        self.import_depth -= 1
        return updated

    def leave_SimpleStatementLine(
        self,
        original: cst.SimpleStatementLine,
        updated: cst.SimpleStatementLine,
    ) -> cst.BaseStatement | cst.FlattenSentinel[cst.BaseStatement]:
        plans = [
            (i, self.imports[s])
            for i, s in enumerate(original.body)
            if s in self.imports
        ]
        for _, plan in plans:
            for full, replacement in plan.removed:
                self.record(original, "removed", f"{full}: {replacement}")
        plans = [(i, p) for i, p in plans if p.statements is not None]
        if not plans:
            return updated
        if len(original.body) == 1:
            statements = plans[0][1].statements or []
            self.record(
                original,
                "import",
                f"{_code(original.body[0])} -> "
                + "; ".join(_code(s) for s in statements),
            )
            lines = [cst.SimpleStatementLine(body=[s]) for s in statements]
            lines[0] = lines[0].with_changes(leading_lines=updated.leading_lines)
            lines[-1] = lines[-1].with_changes(
                trailing_whitespace=updated.trailing_whitespace
            )
            return cst.FlattenSentinel(lines) if len(lines) > 1 else lines[0]
        body: list[cst.BaseSmallStatement] = list(updated.body)
        for i, plan in reversed(plans):
            statements = plan.statements or []
            self.record(
                original,
                "import",
                f"{_code(original.body[i])} -> "
                + "; ".join(_code(s) for s in statements),
            )
            body[i : i + 1] = [
                s.with_changes(
                    semicolon=cst.Semicolon(whitespace_after=cst.SimpleWhitespace(" "))
                )
                for s in statements
            ]
        body[-1] = body[-1].with_changes(semicolon=cst.MaybeSentinel.DEFAULT)
        return updated.with_changes(body=body)

    def leave_Name(self, original: cst.Name, updated: cst.Name) -> cst.Name:
        new = self.definitions.get(original) or self.names.get(original)
        if new and new != updated.value:
            kind = "symbol" if original in self.definitions else "reference"
            self.record(original, kind, f"{original.value} -> {new}")
            return updated.with_changes(value=new)
        return updated

    def _qualified(self, node: cst.CSTNode) -> str | None:
        names = {
            self._absolute(q.name)
            for q in self.get_metadata(QualifiedNameProvider, node, set())
        }
        names = {n for n in names if n and self.resolver.inside(n)}
        return next(iter(names)) if len(names) == 1 else None

    def leave_Attribute(
        self, original: cst.Attribute, updated: cst.Attribute
    ) -> cst.BaseExpression:
        if self.import_depth:
            return updated
        qualified = self._qualified(original)
        if qualified is not None:
            removal = self.resolver.removal(qualified)
            if removal is not None and not self._parent_attr(original):
                self.record(
                    original, "removed", f"{removal.name}: {removal.replacement}"
                )
            new = self.resolver.qualified(qualified)
            if new == qualified:
                return updated
            base_original = _base(original)
            base_updated = _base(updated)
            if base_original is None or base_updated is None:
                # A call or subscript in the chain: rename the last part only.
                old_parts, new_parts = qualified.split("."), new.split(".")
                if len(old_parts) == len(new_parts) and old_parts[-1] != new_parts[-1]:
                    self.record(
                        original, "attribute", f".{old_parts[-1]} -> .{new_parts[-1]}"
                    )
                    return updated.with_changes(attr=cst.Name(new_parts[-1]))
                return updated
            base = self._qualified(base_original)
            if base is None:
                return updated
            new_base = self.resolver.qualified(base)
            if not new.startswith(new_base + "."):
                self.record(
                    original,
                    "review",
                    f"cannot write {qualified} as {new} from {base_updated.value}",
                )
                return updated
            expression: cst.BaseExpression = base_updated
            for part in new[len(new_base) + 1 :].split("."):
                expression = cst.Attribute(value=expression, attr=cst.Name(part))
            if not self._parent_attr(original):
                self.record(original, "reference", f"{qualified} -> {new}")
            return expression
        return self._generic_attribute(original, updated)

    def _parent_attr(self, node: cst.Attribute) -> bool:
        """Return true for an inner part of a longer attribute chain."""
        parent = self.parents.get(node)
        return isinstance(parent, cst.Attribute) and parent.value is node

    def _generic_attribute(
        self, original: cst.Attribute, updated: cst.Attribute
    ) -> cst.Attribute:
        entries = self.resolver.by_name.get(original.attr.value)
        if not entries or not self.uses_package:
            return updated
        applied = [e for e in entries if e.apply == "all"]
        if len({e.new_name for e in applied}) == 1:
            entry = applied[0]
            self.record(original, "attribute", f".{entry.name} -> .{entry.new_name}")
            return updated.with_changes(attr=cst.Name(entry.new_name))
        for entry in entries:
            self.record(
                original,
                "review",
                f".{entry.name}: {entry.owner}.{entry.name} becomes {entry.new_name}",
            )
        return updated

    def leave_Arg(self, original: cst.Arg, updated: cst.Arg) -> cst.Arg:
        if original.keyword is None or not self.uses_package:
            return updated
        entry = self.resolver.any_parameter.get(original.keyword.value)
        if entry is None:
            return updated
        self.record(original, "parameter", f"{entry.name}= -> {entry.new_name}=")
        return updated.with_changes(keyword=cst.Name(entry.new_name))

    def leave_Call(self, original: cst.Call, updated: cst.Call) -> cst.Call:
        if not self.resolver.parameters:
            return updated
        callable_ = self._qualified(original.func)
        if callable_ is None:
            return updated
        target = self.resolver.symbol(callable_)
        args = []
        changed = False
        for arg in updated.args:
            if arg.keyword is not None:
                entry = self.resolver.parameters.get(f"{target}.{arg.keyword.value}")
                if entry is not None:
                    changed = True
                    self.record(
                        original,
                        "parameter",
                        f"{target}({entry.name}=) -> {entry.new_name}=",
                    )
                    arg = arg.with_changes(keyword=cst.Name(entry.new_name))
            args.append(arg)
        return updated.with_changes(args=args) if changed else updated

    def leave_Subscript(
        self, original: cst.Subscript, updated: cst.Subscript
    ) -> cst.Subscript:
        """Keep `Path(__file__).parents[N]` on the same folder when the file moves."""
        target = self.context.target
        if (
            not target
            or target == self.context.path
            or not m.matches(original.value, _PARENTS)
        ):
            return updated
        if len(original.slice) != 1 or not m.matches(
            original.slice[0], m.SubscriptElement(m.Index(m.Integer()))
        ):
            return updated
        level = int(original.slice[0].slice.value.value)  # type: ignore[attr-defined]
        old = PurePosixPath(self.context.path)
        if level >= len(old.parents):
            return updated
        folder = str(old.parents[level])
        new_folder = PurePosixPath(
            self.locations.folder("" if folder == "." else folder)
        )
        parents = [str(p) for p in PurePosixPath(target).parents]
        wanted = "." if str(new_folder) in {"", "."} else str(new_folder)
        if wanted not in parents:
            self.record(
                original,
                "review",
                f"parents[{level}] of {self.context.path} has no match in {target}",
            )
            return updated
        new_level = parents.index(wanted)
        if new_level == level:
            return updated
        self.record(original, "string", f"parents[{level}] -> parents[{new_level}]")
        element = updated.slice[0]
        return updated.with_changes(
            slice=[
                element.with_changes(
                    slice=element.slice.with_changes(value=cst.Integer(str(new_level)))
                )
            ]  # type: ignore[attr-defined]
        )

    def leave_SimpleString(
        self, original: cst.SimpleString, updated: cst.SimpleString
    ) -> cst.SimpleString:
        if "b" in updated.prefix.lower():
            return updated
        raw = updated.raw_value
        new = raw
        exact = self.strings.get(original, {}).get(raw)
        if exact is not None:
            new = exact
            kind = "all"
        elif raw in self.package_names:
            new = self.package_names[raw]
            kind = "lazy"
        elif raw in self.locations.files:
            new = self.locations.files[raw]
            kind = "string"
        elif self.bindings and self._in_annotation(original):
            new = _WORD.sub(lambda match: self.bindings.get(match[0], match[0]), raw)
            kind = "reference"
        else:
            if raw in self.outside_children:
                self.record(
                    original,
                    "review",
                    f"{raw!r} names a submodule that leaves {self.context.module}",
                )
            new = self._text(raw)
            kind = "string"
        if new == raw:
            return updated
        self.record(original, kind, f"{raw!r} -> {new!r}")
        return updated.with_changes(
            value=f"{updated.prefix}{updated.quote}{new}{updated.quote}"
        )

    def leave_FormattedStringText(
        self,
        original: cst.FormattedStringText,
        updated: cst.FormattedStringText,
    ) -> cst.FormattedStringText:
        new = self._text(updated.value)
        if new == updated.value:
            return updated
        self.record(original, "string", f"{updated.value!r} -> {new!r}")
        return updated.with_changes(value=new)

    def _in_annotation(self, node: cst.CSTNode) -> bool:
        current = self.parents.get(node)
        while current is not None and not isinstance(current, cst.BaseStatement):
            if isinstance(current, cst.Annotation):
                return True
            current = self.parents.get(current)
        return False

    def _text(self, text: str) -> str:
        if self.resolver.package not in text and "src/" not in text:
            return text
        return rewrite_text(text, self.resolver, self.locations)

    def _extend_children(
        self,
        original: cst.Set | cst.List | cst.Tuple,
        updated: cst.Set | cst.List | cst.Tuple,
    ) -> cst.BaseExpression:
        if not self.new_children or len(original.elements) < 2:
            return updated
        values = []
        for element in original.elements:
            if not isinstance(element, cst.Element) or not isinstance(
                element.value, cst.SimpleString
            ):
                return updated
            values.append(element.value.raw_value)
        if not set(values) <= self.old_children:
            return updated
        current = {
            e.value.raw_value
            for e in updated.elements
            if isinstance(e.value, cst.SimpleString)
        }
        missing = [c for c in self.new_children if c not in current]
        if not missing:
            return updated
        elements = list(updated.elements)
        last = elements[-1]
        quote = last.value.quote  # type: ignore[attr-defined]
        comma = next(
            (e.comma for e in elements[:-1] if isinstance(e.comma, cst.Comma)),
            cst.Comma(whitespace_after=cst.SimpleWhitespace(" ")),
        )
        trailing = last.comma
        elements[-1] = last.with_changes(comma=comma)
        for i, child in enumerate(missing):
            elements.append(
                cst.Element(
                    value=cst.SimpleString(f"{quote}{child}{quote}"),
                    comma=trailing if i == len(missing) - 1 else comma,
                )
            )
        self.record(original, "lazy", "added " + ", ".join(missing))
        return updated.with_changes(elements=elements)

    def leave_Set(self, original: cst.Set, updated: cst.Set) -> cst.BaseExpression:
        return self._extend_children(original, updated)

    def leave_List(self, original: cst.List, updated: cst.List) -> cst.BaseExpression:
        return self._extend_children(original, updated)

    def leave_Tuple(
        self, original: cst.Tuple, updated: cst.Tuple
    ) -> cst.BaseExpression:
        return self._extend_children(original, updated)


def _dotted(node: cst.BaseExpression) -> str:
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        return f"{_dotted(node.value)}.{node.attr.value}"
    raise TypeError(type(node).__name__)


def _base(node: cst.BaseExpression) -> cst.Name | None:
    while isinstance(node, cst.Attribute):
        node = node.value
    return node if isinstance(node, cst.Name) else None


def _code(node: cst.CSTNode) -> str:
    return cst.Module(body=[]).code_for_node(node).strip()


def has_package(source: str, package: str, aliases: Sequence[str] = ()) -> bool:
    """Return true when text mentions the package or one of its aliases."""
    return package in source or any(
        re.search(rf"\b{re.escape(a)}\.", source) for a in aliases
    )
