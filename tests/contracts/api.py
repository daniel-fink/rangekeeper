"""Write or check the public API snapshot (ADR-017).

The snapshot lists each public name of each public package, with its kind, its
defining module and its signature. A change to the snapshot is a change to the
public API; review it before you update the file:

    uv run python -m tests.contracts.api --write
"""

import enum
import importlib
import inspect
import json
import re
import sys
import typing
from pathlib import Path
from types import ModuleType

SNAPSHOT = Path(__file__).with_name("api.json")

# The public packages (ADR-010) and the public modules inside them. `schema`
# and `shared` are internal.
PACKAGES = (
    "rangekeeper",
    "rangekeeper.quantity",
    "rangekeeper.money",
    "rangekeeper.duration",
    "rangekeeper.profile",
    "rangekeeper.flow",
    "rangekeeper.market",
    "rangekeeper.finance",
    "rangekeeper.finance.financial",
    "rangekeeper.model",
    "rangekeeper.model.expression",
    "rangekeeper.model.formulation",
    "rangekeeper.model.system",
    "rangekeeper.expressions",
    "rangekeeper.expressions.finance",
    "rangekeeper.expressions.flow",
    "rangekeeper.expressions.profile",
    "rangekeeper.specification",
    "rangekeeper.specification.rule",
    "rangekeeper.run",
    "rangekeeper.execution",
    "rangekeeper.execution.backends",
    "rangekeeper.execution.rule",
    "rangekeeper.io",
    "rangekeeper.io.bundle",
    "rangekeeper.io.json",
    "rangekeeper.io.polars",
    "rangekeeper.io.yaml",
    "rangekeeper.errors",
)

# Base classes whose members every record shares; they are listed once.
SHARED_BASES = ("rangekeeper.schema.runtime",)


def public_names(module: ModuleType) -> list[str]:
    names = getattr(module, "__all__", None)
    if names is not None:
        return sorted(set(names))
    return sorted(
        name
        for name, value in vars(module).items()
        if not name.startswith("_")
        and getattr(value, "__module__", None) == module.__name__
    )


def default(value) -> str:
    """Write a default without memory addresses or environment details."""
    # A StrEnum member is also a str, so test for an enum first.
    if isinstance(value, enum.Enum):
        return f"{type(value).__name__}.{value.name}"
    if value is None or isinstance(value, (bool, int, float, str)):
        return repr(value)
    if isinstance(value, (tuple, list, frozenset)):
        items = ", ".join(default(item) for item in value)
        return f"{type(value).__name__}({items})"
    return f"<{type(value).__name__}>"


def public_path(match: re.Match) -> str:
    """Name a class by the public module that exports it, not a private one."""
    parent, name = match.group(1), match.group(3)
    try:
        exported = getattr(importlib.import_module(parent), name, None)
    except ImportError:
        exported = None
    return f"{parent}.{name}" if exported is not None else match.group(0)


def annotation(value) -> str:
    text = value if isinstance(value, str) else inspect.formatannotation(value)
    # For example, Python 3.13 defines pathlib.Path in pathlib._local.
    return re.sub(
        r"\b([a-z]\w*(?:\.[a-z]\w*)*)\.(_\w+)\.([A-Za-z]\w*)", public_path, text
    )


def signature(value) -> str | None:
    try:
        found = inspect.signature(value)
    except (TypeError, ValueError):
        return None
    parts = []
    marker = None
    for parameter in found.parameters.values():
        kind = parameter.kind
        if kind is parameter.KEYWORD_ONLY and marker is None:
            parts.append("*")
            marker = True
        if kind is parameter.VAR_POSITIONAL:
            marker = True
        text = {parameter.VAR_POSITIONAL: "*", parameter.VAR_KEYWORD: "**"}.get(
            kind, ""
        ) + parameter.name
        if parameter.annotation is not parameter.empty:
            text += f": {annotation(parameter.annotation)}"
        if parameter.default is not parameter.empty:
            text += f" = {default(parameter.default)}"
        parts.append(text)
        if kind is parameter.POSITIONAL_ONLY:
            following = list(found.parameters.values())
            index = following.index(parameter)
            if index + 1 == len(following) or (
                following[index + 1].kind is not parameter.POSITIONAL_ONLY
            ):
                parts.append("/")
    result = f"({', '.join(parts)})"
    if found.return_annotation is not found.empty:
        result += f" -> {annotation(found.return_annotation)}"
    return result


def members(cls: type) -> dict[str, str]:
    result: dict[str, str] = {}
    for owner in reversed(cls.__mro__):
        module = getattr(owner, "__module__", "")
        if not module.startswith("rangekeeper.") or module in SHARED_BASES:
            continue
        for name, value in vars(owner).items():
            if name.startswith("_") and name != "__init__":
                continue
            if isinstance(value, property):
                result[name] = "property"
            elif isinstance(value, (classmethod, staticmethod)):
                result[name] = f"{type(value).__name__} {signature(value.__func__)}"
            elif inspect.isfunction(value):
                result[name] = f"method {signature(value)}"
    return dict(sorted(result.items()))


def describe(value) -> dict:
    if isinstance(value, ModuleType):
        return {"kind": "module", "module": value.__name__}
    entry = {"module": getattr(value, "__module__", None)}
    if inspect.isclass(value) and issubclass(value, enum.Enum):
        entry.update(kind="enum", members=[member.name for member in value])
    elif inspect.isclass(value):
        entry.update(kind="class", signature=signature(value), members=members(value))
    elif callable(value):
        entry.update(kind="function", signature=signature(value))
    elif typing.get_origin(value) is not None:
        entry = {
            "kind": "alias",
            "value": " | ".join(map(annotation, typing.get_args(value))),
        }
    else:
        entry = {"kind": "value", "type": type(value).__name__}
    return entry


def snapshot() -> dict:
    result = {}
    for package in PACKAGES:
        module = importlib.import_module(package)
        result[package] = {
            name: describe(getattr(module, name))
            for name in public_names(module)
            if name != "__version__"
        }
    return result


def render(data: dict) -> str:
    return json.dumps(data, indent=1, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render(snapshot())
    if argv == ["--write"]:
        SNAPSHOT.write_text(text)
        print(f"Wrote {SNAPSHOT}")
        return 0
    if argv:
        print(__doc__)
        return 2
    if SNAPSHOT.read_text() != text:
        print("The public API differs from the snapshot; review it, then use --write")
        return 1
    print("The public API matches the snapshot")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
