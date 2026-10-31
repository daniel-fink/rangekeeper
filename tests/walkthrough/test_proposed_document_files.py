"""The proposed cells that load saved documents run as written (#295).

The cells come from ``examples/walkthrough/proposed/``: lesson 04 cells 2, 4
and 9, lesson 05 cells 2 and 3, lesson 06 cells 2 and 22, and lesson 07 cells 2
and 3.
Each reads a document of the data package with
``rk.io.load(path=helpers.data_path(name=...))``. Here ``helpers.data_path``
gives a file in a temporary folder, which ``rk.io.save`` writes from the
documents of the earlier lessons' cells.

The other statements of these cells need other issues: ``model.summary()``
(#287), rollups (#285), the walkthrough helpers' data, and keyed values (#284).
"""

import ast
import importlib.util
import os
import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

import rangekeeper as rk
from tests.execution.lesson02 import back
from tests.market.test_paths import histories

PROPOSED = Path(__file__).resolve().parents[2] / "examples/walkthrough/proposed"
YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)
EXECUTION = all(importlib.util.find_spec(name) for name in ("pyomo", "highspy"))


def cells(lesson: str) -> dict[str, str]:
    """Return the numbered cells of a lesson."""
    numbered: dict[str, str] = {}
    for block in re.findall(
        r"```python\n(.*?)```", (PROPOSED / lesson).read_text(), re.S
    ):
        if match := re.match(r"# cell (\w+)", block):
            numbered[match[1]] = block
    return numbered


def statements(cell: str, *indexes: int) -> str:
    """Return some statements of a cell, by their index."""
    body = ast.parse(cell).body
    return ast.unparse(ast.Module(body=[body[i] for i in indexes], type_ignores=[]))


@pytest.fixture(scope="module")
def data(tmp_path_factory) -> Path:
    """Return a folder with the documents that the cells load, saved by rk.io.save."""
    folder = tmp_path_factory.mktemp("data")
    numbered = cells("03_cases_debt_equity.md")
    namespace: dict[str, object] = {"rk": rk, "date": date, "years": YEARS}
    for key in ("5", "5b", "5c", "6", "7", "7b", "8", "12", "12b"):
        exec(numbered[key], namespace)
    plan = namespace["model"]
    assert isinstance(plan, rk.Model)
    for name in (
        "03_base_plan.model.json",
        "04_base_plan_on_paths.model.json",
        "mixed_use_property.model.json",
        "07_property_plan.model.json",
    ):
        rk.io.save(document=plan, path=folder / name)
    base = plan.specify(name="Base case").fix(
        start_date=date(2027, 1, 1), b_start=date(2030, 1, 1)
    )
    rk.io.save(document=base, path=folder / "04_base_case.specification.json")
    growth = base.fix(rent_growth="3 % pa", exit_cap_rate="5 %")
    rk.io.save(document=growth, path=folder / "03_base_case.specification.json")
    rk.io.save(document=back(), path=folder / "02_back_door.specification.json")
    for name in ("04_rent_index.paths.json", "04_use_factors.paths.json"):
        rk.io.save(document=histories(), path=folder / name)
    return folder


def run(code: str, data: Path) -> dict[str, object]:
    """Run code with ``helpers.data_path`` reading from ``data``."""
    helpers = SimpleNamespace(data_path=lambda *, name: data / name)
    namespace: dict[str, object] = {"rk": rk, "date": date, "helpers": helpers}
    exec(code, namespace)
    return namespace


def test_lesson_04_cell_2_loads_the_plan_of_lesson_03_and_shows_its_equations(data):
    namespace = run(cells("04_market_futures.md")["2"], data)
    model = namespace["model"]
    assert isinstance(model, rk.Model)
    assert len(model.equations) == 35


def test_lesson_04_cell_4_moves_lesson_03_s_base_case_to_the_new_plan(data):
    """Cells 3 and 3b remove the rent growth (#283); cell 4 frees it, then on."""
    numbered = cells("04_market_futures.md")
    namespace = run(numbered["2"], data)
    exec(numbered["3"], namespace)
    exec(numbered["3b"], namespace)
    exec(numbered["4"], namespace)
    base = namespace["base"]
    assert base.model_id == namespace["model"].id
    keys = {row.values["key"] for row in base.roles.rows}
    assert "rent_growth" not in keys and "exit_cap_rate" in keys


def test_lesson_04_cell_9_saves_and_loads_the_generated_paths(tmp_path, monkeypatch):
    """Cells 5 to 9 as written; the helpers only draw, so here they draw nothing."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RK_PATH_COUNT", "3")
    numbered = cells("04_market_futures.md")
    namespace: dict[str, object] = {
        "rk": rk,
        "date": date,
        "os": os,
        "years": YEARS,
        "helpers": SimpleNamespace(plot_paths=lambda **_: None),
    }
    for key in ("5", "6", "7", "8", "9"):
        exec(numbered[key], namespace)
    # The cell runs again: the same paths are in the file already.
    exec(numbered["9"], namespace)
    paths = namespace["paths"]
    assert (
        rk.io.load(path=tmp_path / "paths" / f"04_rent_index_{paths.id}.json") == paths
    )


def test_lesson_05_cells_2_and_3_load_the_plan_the_paths_and_the_base_case(data):
    numbered = cells("05_when_to_commit.md")
    loaded = run(numbered["2"], data)
    model = loaded["model"]
    assert loaded["paths"] == histories()
    dates = eval(statements(numbered["2"], 2), loaded)
    assert [item.key for item in dates] == [
        "shared_start",
        "shared_open",
        "a_start",
        "a_open",
        "b_open",
        "b_start",
    ]
    namespace = run(numbered["3"], data)
    fixed = namespace["fixed"]
    assert isinstance(fixed, rk.Specification)
    assert fixed.model is not None and fixed.model.id == model.id
    roles = {row.values["key"]: row.values["role"] for row in fixed.roles.rows}
    assert roles["start_date"] is rk.specification.Role.FIXED


def test_lesson_06_cell_2_loads_the_property(data):
    namespace = run(statements(cells("06_project_structure.md")["2"], 0), data)
    assert isinstance(namespace["model"], rk.Model)


@pytest.mark.skipif(not EXECUTION, reason="requires the optional execution extra")
def test_lesson_06_cell_22_solves_lesson_02_s_back_door_again(data):
    """The loaded Specification brings its Model, so the solve resolves it."""
    namespace = run(statements(cells("06_project_structure.md")["22"], 0, 1, 2), data)
    outcome = namespace["lesson_02_outcome"]
    assert outcome.status is rk.execution.Status.FEASIBLE
    expected = rk.execution.solve(specification=back())
    assert rk.quantity.isclose(
        actual=outcome["land_cost"], expected=expected["land_cost"]
    )


def test_lesson_07_cells_2_and_3_load_the_plan_and_the_base_case(data):
    numbered = cells("07_policies_and_graph.md")
    loaded = run(statements(numbered["2"], 0, 1), data)
    residential = loaded["residential"]
    assert isinstance(loaded["use_paths"], rk.market.Paths)
    base = run(statements(numbered["3"], 0), data)["base"]
    assert isinstance(residential, rk.Model)
    assert isinstance(base, rk.Specification) and base.model is not None
