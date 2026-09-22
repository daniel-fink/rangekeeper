"""Separate exact installed-code audit from semantic computation identity."""

import ast
import hashlib
from pathlib import Path

from rangekeeper.graph import _structured


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


def semantic_digest(source: str) -> str:
    """Ignore comments/docstrings, while including executable syntax and constants."""
    tree = _WithoutDocstrings().visit(ast.parse(source))
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()


def manifests(package: Path, *, modules: tuple[str, ...] = ()):
    """Audit every Python file; bind semantic identity to declared computation code.

    This conservative dependency set includes graph construction, provenance,
    measures and ingestion, plus the selected handlers' declared native modules.
    Presentation and CLI export do not compute assertions and therefore cannot
    change their identities.
    """
    paths = sorted(package.rglob("*.py"))
    audit = {
        str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths
    }
    semantic = {}
    for p in paths:
        name = str(p.relative_to(package))
        included = name in {"validate.py", "measure.py"} or name.startswith((
            "measure/",
            "graph/",
        ))
        excluded = name.startswith("graph/adapter/") and not (
            any(name.startswith(prefix) for prefix in modules)
            or name in {"graph/adapter/errors.py", "graph/adapter/json.py"}
        )
        excluded |= name in {
            "graph/workflow/review.py",
            "graph/workflow/_review.py",
            "graph/workflow/workbench.py",
            "graph/workflow/references.py",
            "graph/workflow/__main__.py",
        }
        if included and not excluded:
            semantic[name] = semantic_digest(p.read_text())
    return audit, semantic, _structured.fingerprint({"version": 3, "modules": semantic})
