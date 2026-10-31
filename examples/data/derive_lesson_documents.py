"""Derive the documents that walkthrough lesson 04 loads from lesson 03.

Usage, from the repository root:

    python examples/data/derive_lesson_documents.py          # write the documents
    python examples/data/derive_lesson_documents.py --check  # fail if a file differs

The script writes two files of ``mixed_use_property``, with ``rk.io.save``:

- ``03_base_plan.model.json``: lesson 03's Model, with the commitments of its
  optional cell 21.
- ``03_base_case.specification.json``: lesson 03's ``funded`` Specification
  (cell 19), on that Model.

Their origin is lesson 03: the script runs the statements of the numbered cells
of ``examples/walkthrough/proposed/03_cases_debt_equity.md`` that declare the
Model and the Specification, and fixes the values of ``base_plan.json``. It leaves
out each solve and display.

Each revision has a new random UUID, so two runs give different IDs. The comparison
reads each UUID as the order of its first use, and the script keeps the files when
only their IDs differ. After a change, update the ``bytes`` and ``sha256`` of the
files in ``manifest.json``. The script needs Rangekeeper, and no solver.
"""

import ast
import json
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

import rangekeeper as rk

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "examples/data/mixed_use_property"
LESSON = ROOT / "examples/walkthrough/proposed/03_cases_debt_equity.md"
# The cells of lesson 03 that declare the Model and the funded Specification.
CELLS = "3 5 5b 5c 6 7 7b 8 9 12 12b 13 18 19 21".split()
FILES = ("03_base_plan.model.json", "03_base_case.specification.json")
UUID_TEXT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def plan() -> dict[str, object]:
    """Return the values of ``base_plan.json``, as ``helpers.load_base_plan`` does."""
    content = json.loads((DATA / "base_plan.json").read_text(encoding="utf-8"))
    return {
        key: date.fromisoformat(item["date"])
        if "date" in item
        else rk.Quantity(magnitude=item["magnitude"], units=item["units"])
        for key, item in content["values"].items()
    }


def declarations(source: str) -> list[str]:
    """Return the statements of a cell without its solves and displays."""
    found = []
    for statement in ast.parse(source).body:
        code = ast.unparse(statement)
        solves = "rk.execution." in code or "helpers." in code
        shows = isinstance(statement, ast.Expr) and (
            not isinstance(statement.value, ast.Call) or ".table(" in code
        )
        if not solves and not shows:
            found.append(code)
    return found


def documents() -> tuple[rk.Model, rk.Specification]:
    """Return lesson 03's Model and its funded Specification on that Model."""
    numbered = {}
    for block in re.findall(
        r"```python\n(.*?)```", LESSON.read_text(encoding="utf-8"), re.S
    ):
        if match := re.match(r"# cell (\w+)", block):
            numbered[match[1]] = block
    namespace: dict = {"rk": rk, "date": date, "plan": plan()}
    for key in CELLS:
        for code in declarations(numbered[key]):
            exec(code, namespace)
    model = namespace["model"]
    return model, namespace["funded"].on(model=model)


def without_ids(text: str) -> str:
    """Return document text with each UUID replaced by the order of its first use."""
    order: dict[str, int] = {}
    return UUID_TEXT.sub(
        lambda found: f"id-{order.setdefault(found[0], len(order))}", text
    )


def differing(folder: Path) -> list[str]:
    """Return the names of the files that differ from those of ``folder``, but for IDs."""
    return [
        name
        for name in FILES
        if not (DATA / name).is_file()
        or without_ids((DATA / name).read_text(encoding="utf-8"))
        != without_ids((folder / name).read_text(encoding="utf-8"))
    ]


def main(arguments: list[str]) -> int:
    """Write the documents, or with ``--check`` compare them with a new derivation."""
    if arguments not in ([], ["--check"]):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        model, funded = documents()
        rk.io.save(document=model, path=folder / FILES[0])
        rk.io.save(document=funded, path=folder / FILES[1])
        changed = differing(folder)
        if arguments:
            for name in changed:
                print(f"{name} differs; run this script again", file=sys.stderr)
            return 1 if changed else 0
        if changed:
            # The two files must name the same Model revision, so write both.
            for name in FILES:
                (DATA / name).write_bytes((folder / name).read_bytes())
                print(DATA / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
