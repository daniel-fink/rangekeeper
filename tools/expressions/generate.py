"""Write the Python form of equations and its docs table from the function registry.

The equation-function registry (``rangekeeper.model.expression.catalogue``)
declares each equation function once (ADR-015, D32). This script writes, from
it:

- ``src/rangekeeper/expressions/``: ``rx``, with one typed function for each
  equation function, in the module of its namespace (``rx.finance.npv`` is in
  ``finance.py``);
- the Flow methods of ``Symbolic`` in ``model/expression/terms.py``, between
  the generated-methods markers;
- the function table of ``docs/reference/expressions.md``, between the
  generated-functions markers.

Run it from the repository root after a change to the registry. ``--check``
writes nothing and fails when a file differs from what the registry gives:

    uv run --locked python tools/expressions/generate.py
    uv run --locked python tools/expressions/generate.py --check
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from rangekeeper.model.expression.catalogue import functions  # noqa: E402
from rangekeeper.model.expression.functions import (  # noqa: E402
    EquationFunction,
    Form,
    FunctionParameter,
)
from rangekeeper.schema.enums import ParameterKind  # noqa: E402

PACKAGE = ROOT / "src/rangekeeper/expressions"
TERMS = ROOT / "src/rangekeeper/model/expression/terms.py"
DOCS = ROOT / "docs/reference/expressions.md"
METHODS = ("    # BEGIN GENERATED METHODS\n", "    # END GENERATED METHODS\n")
TABLE = ("<!-- BEGIN GENERATED FUNCTIONS -->\n", "<!-- END GENERATED FUNCTIONS -->\n")
HEADER = '''"""{doc}

tools/expressions/generate.py writes this module from the equation-function
registry; do not edit it by hand.
"""
'''
NAMESPACES = {
    "profile": "Profiles in equations: a Flow made by a growth or a distribution profile.",
    "flow": "Flows made from amounts in equations.",
    "finance": "Valuation and interest in equations, on one date basis.",
}


def _signature(function: EquationFunction, *, method: bool) -> str:
    """Return the parameters of the Python function or method of ``function``."""
    parameters = list(function.parameters[1:] if method else function.parameters)
    positional = [p for p in parameters if p.call is ParameterKind.POSITIONAL_OR_NAMED]
    named = [p for p in parameters if p not in positional]
    # Methods are in terms.py, above the definition of Operand.
    operand = '"Operand"' if method else "Operand"
    parts = ["self"] if method else []
    parts += [_parameter(p, operand=operand) for p in positional]
    if named:
        parts.append("*")
        parts += [_parameter(p, operand=operand) for p in named]
    return ", ".join(parts)


def _parameter(parameter: FunctionParameter, *, operand: str) -> str:
    if parameter.required:
        return f"{parameter.name}: {operand}"
    optional = '"Operand | None"' if operand.startswith('"') else "Operand | None"
    return f"{parameter.name}: {optional} = None"


def _arguments(function: EquationFunction, *, method: bool) -> str:
    """Return the arguments with which the Python form calls ``terms.call``."""
    parameters = function.parameters[1:] if method else function.parameters
    required = [p for p in parameters if p.required]
    optional = [p for p in parameters if not p.required]
    parts = [f'"{function.code}"']
    if method:
        parts.append("self")
    parts += [
        p.name if p.call is ParameterKind.POSITIONAL_OR_NAMED else f"{p.name}={p.name}"
        for p in required
    ]
    if optional:
        given = ", ".join(f"{p.name}={p.name}" for p in optional)
        parts.append(f"**given({given})")
    return ", ".join(parts)


def _docstring(function: EquationFunction, *, indent: str) -> str:
    """Return the docstring of the Python function or method of ``function``."""
    summary = function.summary
    if summary.startswith("The "):
        summary = "Return the " + summary[4:]
    elif summary.startswith("A "):
        summary = "Return a " + summary[2:]
    elif summary.startswith("Each "):
        summary = "Return each " + summary[5:]
    lines = [summary, ""]
    shown = (
        function.parameters[1:] if function.form is Form.METHOD else function.parameters
    )
    for parameter in shown:
        lines.append(f"``{parameter.name}``: {parameter.description}")
    if shown:
        lines.append("")
    lines.append(
        f"Mirrors ``{function.mirrors}``."
        if function.mirrors.startswith("rangekeeper")
        else f"Mirrors {function.mirrors}."
    )
    body = "\n".join(lines).strip()
    wrapped = []
    for line in body.split("\n"):
        wrapped += textwrap.wrap(line, width=80 - len(indent)) or [""]
    if len(wrapped) == 1:
        return f'{indent}"""{wrapped[0]}"""'
    rest = "\n".join(f"{indent}{line}" if line else "" for line in wrapped[1:])
    return f'{indent}"""{wrapped[0]}\n{rest}\n{indent}"""'


def _function_source(function: EquationFunction, *, name: str) -> str:
    signature = _signature(function, method=False)
    return (
        f"def {name}({signature}) -> Term:\n"
        f"{_docstring(function, indent='    ')}\n"
        f"    return call({_arguments(function, method=False)})\n"
    )


def _method_source(function: EquationFunction) -> str:
    signature = _signature(function, method=True)
    return (
        f'    def {function.name}({signature}) -> "Term":\n'
        f"{_docstring(function, indent='        ')}\n"
        f"        return call({_arguments(function, method=True)})\n"
    )


def _module(
    doc: str, entries: list[tuple[str, EquationFunction]], *, root: bool
) -> str:
    uses_given = any(not p.required for _, f in entries for p in f.parameters)
    imports = ["call"]
    if uses_given:
        imports.append("given")
    lines = [HEADER.format(doc=doc), ""]
    names = sorted(name for name, _ in entries)
    if root:
        lines.append(
            "from rangekeeper.model.expression.functions import (\n"
            "    Availability,\n    EquationFunction,\n    EvaluationStage,\n"
            "    Form,\n    FunctionParameter,\n)\n"
        )
        lines.append("from rangekeeper.model.expression.catalogue import functions\n")
    lines.append(
        "from rangekeeper.model.expression.terms import Operand, Term, "
        + ", ".join(imports)
        + "\n"
    )
    if root:
        submodules = sorted({f.name.split(".")[0] for f in functions if "." in f.name})
        for module in submodules:
            lines.append(f"from . import {module}\n")
    lines.append("\n")
    for name, function in sorted(entries, key=lambda item: item[0]):
        lines.append("\n" + _function_source(function, name=name) + "\n")
    exported = list(names)
    if root:
        exported += [
            "Availability",
            "EquationFunction",
            "EvaluationStage",
            "Form",
            "FunctionParameter",
            "Operand",
            "Term",
            "functions",
            *sorted({f.name.split(".")[0] for f in functions if "." in f.name}),
        ]
    listed = "".join(f'    "{item}",\n' for item in exported)
    lines.append(f"\n__all__ = [\n{listed}]\n")
    return "".join(lines)


def package() -> dict[Path, str]:
    """Return the source of each module of ``rangekeeper.expressions``."""
    grouped: dict[str, list[tuple[str, EquationFunction]]] = defaultdict(list)
    for function in functions:
        if function.form is not Form.FUNCTION:
            continue
        namespace, _, name = function.name.rpartition(".")
        grouped[namespace].append((name, function))
    root_doc = (
        "The Python form of equations, imported as ``rx`` (D32).\n\n"
        "``import rangekeeper.expressions as rx``. A declaration on an entity handle\n"
        "returns a value handle, and ``project.ref(key=)`` finds one; operators on\n"
        "handles and Terms build equations, such as ``noi == coverage * debt_service``,\n"
        "and ``project.equations(...)`` adds them. The functions have the names of\n"
        "equation text: ``rx.max(a, b)`` here, and ``rx.profile``, ``rx.flow`` and\n"
        "``rx.finance``. ``rk.`` computes on values now; ``rx.`` builds an equation.\n"
        "Text and ``rx`` make the same records.\n\n"
        "``max`` keeps the name of Python's built-in, as in equation text (D21)."
    )
    sources = {
        PACKAGE / "__init__.py": _module(root_doc, grouped.pop("", []), root=True)
    }
    for namespace, entries in grouped.items():
        doc = NAMESPACES.get(namespace, f"Equation functions in ``rx.{namespace}``.")
        sources[PACKAGE / f"{namespace}.py"] = _module(doc, entries, root=False)
    return sources


def methods() -> str:
    """Return the generated Flow methods of ``Symbolic``."""
    found = [f for f in functions if f.form is Form.METHOD]
    return "".join(_method_source(f) + "\n" for f in found)


def table() -> str:
    """Return the function table of the expressions reference."""
    rows = [
        "| Function | Meaning | Stage | Availability | Mirrors |\n",
        "| --- | --- | --- | --- | --- |\n",
    ]
    for function in functions:
        rows.append(
            f"| `{_spelled(function)}` | {function.summary} | `{function.stage.value}` "
            f"| `{function.availability.value}` | {_mirrors(function)} |\n"
        )
    return "".join(rows)


def _spelled(function: EquationFunction) -> str:
    shown = (
        function.parameters[1:] if function.form is Form.METHOD else function.parameters
    )
    parts = [
        p.name if p.call is ParameterKind.POSITIONAL_OR_NAMED else f"{p.name}="
        for p in shown
    ]
    listed = ", ".join(parts)
    if function.form is Form.METHOD:
        return f"x.{function.name}({listed})"
    return f"{function.code}({listed})"


def _mirrors(function: EquationFunction) -> str:
    if function.mirrors.startswith("rangekeeper"):
        return f"`{function.mirrors}`"
    return function.mirrors


def _between(text: str, markers: tuple[str, str], body: str) -> str:
    start, end = markers
    head, found, rest = text.partition(start)
    if not found:
        raise SystemExit(f"marker {start.strip()!r} not found")
    _, found, tail = rest.partition(end)
    if not found:
        raise SystemExit(f"marker {end.strip()!r} not found")
    return head + start + body + end + tail


def outputs() -> dict[Path, str]:
    """Return each generated file with its content."""
    files = dict(package())
    files[TERMS] = _between(TERMS.read_text(encoding="utf-8"), METHODS, methods())
    files[DOCS] = _between(DOCS.read_text(encoding="utf-8"), TABLE, table())
    return files


def _formatted(files: dict[Path, str]) -> dict[Path, str]:
    """Format the Python files with the project's ruff, as the hooks do."""
    import subprocess

    result = {}
    for path, content in files.items():
        if path.suffix != ".py":
            result[path] = content
            continue
        fixed = (
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "check",
                    "--fix",
                    "--quiet",
                    "--select",
                    "I",
                    "--stdin-filename",
                    str(path),
                    "-",
                ],
                input=content,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                cwd=ROOT,
            ).stdout
            or content
        )
        formatted = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "format",
                "--quiet",
                "--stdin-filename",
                str(path),
                "-",
            ],
            input=fixed,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            cwd=ROOT,
        ).stdout
        result[path] = formatted
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="write nothing; fail on a difference"
    )
    options = parser.parse_args()
    files = _formatted(outputs())
    stale = [
        path
        for path, content in files.items()
        if not path.exists() or path.read_text(encoding="utf-8") != content
    ]
    known = {path for path in files if path.parent == PACKAGE}
    extra = (
        [path for path in PACKAGE.glob("*.py") if path not in known]
        if PACKAGE.exists()
        else []
    )
    if options.check:
        for path in [*stale, *extra]:
            print(f"out of date: {path.relative_to(ROOT)}", file=sys.stderr)
        return 1 if stale or extra else 0
    PACKAGE.mkdir(exist_ok=True)
    for path in stale:
        path.write_text(files[path], encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(ROOT)}")
    for path in extra:
        path.unlink()
        print(f"removed {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
