"""Pure digest mechanics; each subsystem owns its computation manifest."""

import ast
import hashlib
import json


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
