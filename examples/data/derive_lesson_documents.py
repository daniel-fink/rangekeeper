"""Derive the documents that walkthrough lessons 04 and 05 load.

Usage, from the repository root:

    python examples/data/derive_lesson_documents.py          # write the documents
    python examples/data/derive_lesson_documents.py --check  # fail if a file differs

The script writes these files of ``mixed_use_property``, with ``rk.io.save``:

- ``03_base_plan.model.json``: lesson 03's Model, with the commitments of its
  optional cell 21.
- ``03_base_case.specification.json``: lesson 03's ``funded`` Specification
  (cell 19), on that Model.
- ``04_base_plan_on_paths.model.json``: lesson 04's Model, with the rent index
  (cells 2 to 3b).
- ``04_base_case.specification.json``: lesson 04's ``base`` Specification (cell 4),
  on that Model.
- ``04_rent_index.paths.json``: lesson 04's generated market paths (cells 5 to 8),
  with 500 paths and seed 1.
- ``05_histories.paths.json``: the three readable histories of lesson 05, from
  ``HISTORIES`` in this script.

The origin of the Models and the Specifications is the lessons: the script runs the
statements of the numbered cells of ``examples/walkthrough/proposed/`` that declare
them, and fixes the values of ``base_plan.json``. It leaves out each solve and display.

Each revision of a Model or a Specification has a new random UUID, so two runs give
different IDs. The comparison reads each UUID as the order of its first use, and the
script keeps the files when only their IDs differ.

The UUID of Paths is a digest of their content, and their capture record holds the
Python and numpy versions and a generator fingerprint that names the Python version, so
the same seed on another version gives Paths with another ID. The stored file keeps its
ID and its Runs pin it. The comparison leaves out the versions and the fingerprint, and
rounds the amounts to nine decimal places, because the last digits of
a floating point calculation can differ from one machine to another.

After a change, update the ``bytes`` and ``sha256`` of the files in
``manifest.json``. The script needs Rangekeeper, and no solver.
"""

import ast
import json
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import rangekeeper as rk

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "examples/data/mixed_use_property"
PROPOSED = ROOT / "examples/walkthrough/proposed"
LESSON = PROPOSED / "03_cases_debt_equity.md"
LESSON_04 = PROPOSED / "04_market_futures.md"
# The cells of lesson 03 that declare the Model and the funded Specification.
CELLS = "3 5 5b 5c 6 7 7b 8 9 12 12b 13 18 19 21".split()
# The cells of lesson 04 that declare its Model, its base case and its market paths.
CELLS_04 = "2 3 3b 4 5 6 7 8".split()
LESSON_03_FILES = ("03_base_plan.model.json", "03_base_case.specification.json")
LESSON_04_FILES = (
    "04_base_plan_on_paths.model.json",
    "04_base_case.specification.json",
)
PATH_FILES = ("04_rent_index.paths.json", "05_histories.paths.json")
FILES = (*LESSON_03_FILES, *LESSON_04_FILES, *PATH_FILES)
# The path count of lesson 04 without RK_PATH_COUNT.
PATH_COUNT = "500"
# Lesson 05's histories: the rent index in each year from 2027. An early recovery
# reaches both triggers; a long downturn reaches neither; a short recovery reaches
# them late, and then declines.
HISTORIES = {
    "early recovery": (
        1.06,
        1.12,
        1.15,
        1.16,
        1.16,
        1.16,
        1.16,
        1.16,
        1.16,
        1.16,
        1.16,
    ),
    "long downturn": (0.97, 0.95, 0.94, 0.93, 0.93, 0.93, 0.93, 0.93, 0.93, 0.93, 0.93),
    "short recovery": (0.97, 0.95, 1.06, 1.12, 1.04, 1.0, 0.98, 0.97, 0.96, 0.95, 0.95),
}
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
        loads = "helpers.data_path" in code
        solves = "rk.execution." in code or ("helpers." in code and not loads)
        shows = isinstance(statement, ast.Expr) and (
            not isinstance(statement.value, ast.Call) or ".table(" in code
        )
        if not solves and not shows:
            found.append(code)
    return found


def numbered_cells(lesson: Path) -> dict[str, str]:
    """Return the numbered cells of a lesson."""
    numbered = {}
    for block in re.findall(
        r"```python\n(.*?)```", lesson.read_text(encoding="utf-8"), re.S
    ):
        if match := re.match(r"# cell (\w+)", block):
            numbered[match[1]] = block
    return numbered


def documents() -> tuple[rk.Model, rk.Specification]:
    """Return lesson 03's Model and its funded Specification on that Model."""
    numbered = numbered_cells(LESSON)
    namespace: dict = {"rk": rk, "date": date, "plan": plan()}
    for key in CELLS:
        for code in declarations(numbered[key]):
            exec(code, namespace)
    model = namespace["model"]
    return model, namespace["funded"].on(model=model)


def lesson_04_documents(
    folder: Path,
) -> tuple[rk.Model, rk.Specification, rk.market.Paths]:
    """Return lesson 04's Model, base case and paths, from lesson 03's files in ``folder``."""
    numbered = numbered_cells(LESSON_04)
    namespace: dict = {
        "rk": rk,
        "date": date,
        "helpers": SimpleNamespace(data_path=lambda *, name: folder / name),
        "os": SimpleNamespace(environ={"RK_PATH_COUNT": PATH_COUNT}),
    }
    for key in CELLS_04:
        for code in declarations(numbered[key]):
            exec(code, namespace)
    return namespace["model"], namespace["base"], namespace["paths"]


def histories() -> rk.market.Paths:
    """Return lesson 05's histories, on the Periods of lesson 04's rent index."""
    years = rk.duration.Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods(
        frequency=rk.duration.Frequency.YEAR
    )
    return rk.market.Paths.from_flows(
        flows={
            key: {
                "rent_index": rk.flow.Flow.from_periods(
                    periods=years, magnitudes=list(index), units="ratio"
                )
            }
            for key, index in HISTORIES.items()
        },
        name="Lesson 05 histories",
    )


def without_ids(text: str) -> str:
    """Return document text with each UUID replaced by the order of its first use."""
    order: dict[str, int] = {}
    return UUID_TEXT.sub(
        lambda found: f"id-{order.setdefault(found[0], len(order))}", text
    )


def comparable(name: str, text: str) -> str:
    """Return the text of a file in the form that the check compares."""
    if name not in PATH_FILES:
        return without_ids(text)
    content = json.loads(text)
    document = content["document"]
    del document["metadata"]["id"]
    document["capture"]["versions"] = []
    document["capture"].pop("fingerprint", None)
    for member in document["members"]:
        for amount in member["amounts"]:
            amount["magnitudes"] = [round(item, 9) for item in amount["magnitudes"]]
    return json.dumps(content)


def differing(folder: Path, *, names: tuple[str, ...] = FILES) -> list[str]:
    """Return the names of the files that differ from those of ``folder``, but for IDs."""
    return [
        name
        for name in names
        if not (DATA / name).is_file()
        or comparable(name, (DATA / name).read_text(encoding="utf-8"))
        != comparable(name, (folder / name).read_text(encoding="utf-8"))
    ]


def main(arguments: list[str]) -> int:
    """Write the documents, or with ``--check`` compare them with a new derivation."""
    if arguments not in ([], ["--check"]):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        model, funded = documents()
        rk.io.save(document=model, path=folder / LESSON_03_FILES[0])
        rk.io.save(document=funded, path=folder / LESSON_03_FILES[1])
        # Lesson 04 loads lesson 03's stored files, unless they are about to change, so
        # its documents name the revisions that the data package holds.
        lesson_03 = differing(folder, names=LESSON_03_FILES)
        plan_04, base, paths = lesson_04_documents(folder if lesson_03 else DATA)
        rk.io.save(document=plan_04, path=folder / LESSON_04_FILES[0])
        rk.io.save(document=base, path=folder / LESSON_04_FILES[1])
        rk.io.save(document=paths, path=folder / PATH_FILES[0])
        rk.io.save(document=histories(), path=folder / PATH_FILES[1])
        changed = differing(folder)
        if arguments:
            for name in changed:
                print(f"{name} differs; run this script again", file=sys.stderr)
            return 1 if changed else 0
        # The files of one lesson must name the same Model revision, so write them
        # together. A change to lesson 03's files gives lesson 04's files new revisions.
        written = [
            *(LESSON_03_FILES if lesson_03 else ()),
            *(
                LESSON_04_FILES
                if lesson_03 or set(LESSON_04_FILES).intersection(changed)
                else ()
            ),
            *(name for name in PATH_FILES if name in changed),
        ]
        for name in written:
            (DATA / name).write_bytes((folder / name).read_bytes())
            print(DATA / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
