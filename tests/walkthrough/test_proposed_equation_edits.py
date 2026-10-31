"""The proposed cells that read and edit equations by key run as written (#283).

The cells come from ``examples/walkthrough/proposed/``: lesson 04 cells 2, 3 and
3b, lesson 05 cells 2 and 10, lesson 06 cell 24 and lesson 07 cell 17c. Each
lesson starts from the Model of the lesson before it, which this test builds
from lesson 03's cells 5 to 12b, as written.

Some statements of these cells need other issues, so this test runs the rest:

- ``rk.io.load(path=helpers.data_path(...))`` needs #295 and the helpers' data
  package; the test uses the Model that the earlier cells make.
- Lesson 06's Model, with its floors and rollups, needs #284, #285 and #287;
  the test makes a small Model whose equation names two floors by code.
- Lesson 07 cell 17 includes a fragment (#302) and makes a Filter with
  labels (#288), and cell 17b declares rollups (#285); the test declares
  ``x_income`` and ``x_cost`` as values.
"""

import ast
import re
from datetime import date
from pathlib import Path

import pytest

import rangekeeper as rk

PROPOSED = Path(__file__).resolve().parents[2] / "examples/walkthrough/proposed"
YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)


def cells(lesson: str) -> dict[str, str]:
    """Return the numbered cells of a lesson."""
    numbered: dict[str, str] = {}
    text = (PROPOSED / lesson).read_text()
    for block in re.findall(r"```python\n(.*?)```", text, re.S):
        if match := re.match(r"# cell (\w+)", block):
            numbered[match[1]] = block
    return numbered


def statements(cell: str, *indexes: int) -> str:
    """Return some statements of a cell, by their index."""
    body = ast.parse(cell).body
    return ast.unparse(ast.Module(body=[body[i] for i in indexes], type_ignores=[]))


def run(cell: str, namespace: dict[str, object]) -> dict[str, object]:
    exec(cell, namespace)
    return namespace


@pytest.fixture(scope="module")
def lesson_03() -> rk.Model:
    """Return the Model of lesson 03's cells 5 to 12b, as written."""
    numbered = cells("03_cases_debt_equity.md")
    namespace: dict[str, object] = {"rk": rk, "date": date, "years": YEARS}
    for key in ("5", "5b", "5c", "6", "7", "7b", "8", "12", "12b"):
        exec(numbered[key], namespace)
    model = namespace["model"]
    assert isinstance(model, rk.Model)
    return model


@pytest.fixture(scope="module")
def lesson_04(lesson_03: rk.Model) -> rk.Model:
    """Return the Model of lesson 04's cells 3 and 3b, as written."""
    numbered = cells("04_market_futures.md")
    namespace = {"rk": rk, "date": date, "model": lesson_03}
    run(numbered["3"], namespace)
    run(numbered["3b"], namespace)
    model = namespace["model"]
    assert isinstance(model, rk.Model)
    return model


def test_lesson_04_cell_2_shows_the_equations_of_lesson_03(lesson_03):
    """The second statement of cell 2 shows lesson 03's equations."""
    cell = statements(cells("04_market_futures.md")["2"], 1)
    shown = eval(cell, {"model": lesson_03})
    assert isinstance(shown, rk.model.Equations)
    assert len(shown) == 35
    assert shown.where(key="income")[0].text == "income = a_rent + b_rent"
    assert "<table>" in shown._repr_html_()


def test_lesson_04_cells_3_and_3b_replace_two_rents_and_remove_growth_and_irr(
    lesson_03, lesson_04
):
    replaced = lesson_04.equations.where(key=["income", "a_rent", "b_rent"])
    assert [item.text for item in replaced] == [
        "a_rent = rx.profile.constant(initial=a_income, start=a_open)",
        "b_rent = rx.profile.constant(initial=b_income, start=b_open)",
        "income = rent_index * (a_rent + b_rent)",
    ]
    # Each equation keeps its key and its Formulation.
    assert {item.formulation for item in replaced} == {"Operations"}
    assert [item.key for item in lesson_04.equations] == [
        item.key for item in lesson_03.equations if item.key != "equity_irr"
    ]
    for removed in ("rent_growth", "equity_irr"):
        with pytest.raises(rk.errors.MissingReferenceError):
            lesson_04.value(key=removed)
    assert lesson_04.value(key="rent_index").kind is rk.model.ValueKind.FLOW


def test_lesson_04_cell_4_frees_the_removed_growth_before_on(lesson_03, lesson_04):
    """``on`` refuses a fixed value that the new revision does not declare."""
    base = lesson_03.specify(name="Base case").fix(rent_growth="3 % pa")
    with pytest.raises(rk.errors.ContractError) as error:
        base.on(model=lesson_04)
    assert error.value.values["keys"] == ("rent_growth",)
    assert base.free("rent_growth").on(model=lesson_04).model_id == lesson_04.id


def test_lesson_05_cell_2_shows_the_date_equations(lesson_04):
    cell = statements(cells("05_when_to_commit.md")["2"], 2)
    shown = eval(cell, {"model": lesson_04})
    assert [item.text for item in shown] == [
        "shared_start = start_date",
        "shared_open = shared_start + 1 year",
        "a_start = shared_start + 1 year",
        "a_open = a_start + 2 years",
        "b_open = b_start + 2 years",
        "b_start >= shared_start + 1 year",
    ]


def test_lesson_05_cell_10_adds_the_site_sale_to_the_project_cash(lesson_04):
    namespace = run(
        cells("05_when_to_commit.md")["10"],
        {"rk": rk, "date": date, "model": lesson_04},
    )
    model = namespace["model"]
    (cash,) = model.equations.where(key="project_cash")
    assert cash.text == "project_cash = land + works + operating + sale + b_site_sale"
    assert cash.formulation == "Sale and value"
    keys = [item.key for item in model.equations.where(entity="project")]
    assert keys[0] == "b_site_sale"


def floors() -> rk.Model:
    """Return a project whose reference income names two floors by code."""
    draft = rk.Model(name="Project structure").edit()
    project = draft.add_entity(code="project", classification="project")
    for code in ("a_hotel_floor_1", "a_hotel_floor_2"):
        floor = draft.add_entity(code=code, classification="floor")
        floor.value(key="income", units="AUD pa")
        draft.add_relationship(source="project", target=code, classification="contains")
    project.value(key="reference_income", units="AUD pa")
    project.equations(
        "reference_income = a_hotel_floor_1.income + a_hotel_floor_2.income"
    )
    return draft.commit()


def test_lesson_06_cell_24_names_the_equation_that_breaks(capsys):
    namespace = run(
        cells("06_project_structure.md")["24"], {"rk": rk, "model": floors()}
    )
    assert capsys.readouterr().out == "a_hotel_floor_1.income ('reference_income',)\n"
    assert namespace["draft"].model.entity(code="a_hotel_floor_1")


def test_lesson_07_cell_17c_adds_the_expansion_to_the_works_and_the_income(
    lesson_04,
):
    numbered = cells("07_policies_and_graph.md")
    namespace: dict[str, object] = {"rk": rk, "date": date, "residential": lesson_04}
    exec(statements(numbered["17"], 0, 1), namespace)
    project = namespace["project"]
    assert isinstance(project, rk.model.EntityHandle)
    # Cell 17b declares these two values as rollups (#285).
    project.value(key="x_income", units="AUD pa")
    project.value(key="x_cost", units="AUD")
    run(numbered["17c"], namespace)
    expanded = namespace["expanded"]
    assert [
        item.text for item in expanded.equations.where(key=["works", "income"])
    ] == [
        "works = shared_works + a_works + b_works"
        " - rx.profile.uniform(total=x_cost, start=expansion_date, length=1 year)",
        "income = rent_index * (a_rent + b_rent)"
        " + rx.profile.constant(initial=x_income, start=x_open)",
    ]
    assert expanded.metadata.name == "Building A expanded"
