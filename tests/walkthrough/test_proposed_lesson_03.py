"""The equations of lesson 03's proposed cells parse and are checked as written.

The cells come from ``examples/walkthrough/proposed/03_cases_debt_equity.md``.
Cells 6 to 8 and 12 write their equations with equation functions and Flow
methods (#278). This test reads each equation from the cells as written,
adds it to the project of cells 5 to 5c, and checks that its records read
back to the same text.

The Flow-valued equations commit (#279): each Flow combines with Flows over
the same Periods, and each Flow made from amounts, by a profile or an event,
takes the Periods of the Flow that it defines.

``run_as_written`` runs cells 5 to 8, 12 and 12b as written, with their
named Formulations (#305). The cells leave the results that they do not rely
on undeclared, and the draft infers them, with the Periods of their Flows
(#282): ``RESULTS`` gives the kind and units that it infers, and
``model.entity(code="project").values`` shows them (D44).
"""

import ast
import re
from datetime import date
from pathlib import Path

import pytest

import rangekeeper as rk
from rangekeeper.model.expression.text import read

LESSON = (
    Path(__file__).resolve().parents[2]
    / "examples/walkthrough/proposed/03_cases_debt_equity.md"
)
# The cells whose equations use equation functions and Flow methods.
EQUATION_CELLS = ("5", "6", "7", "7b", "8", "12", "12b")
YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)
# The results that the cells leave to the draft to infer (#282), with the
# kind and units that their equations give.
RESULTS = {
    "shared_start": ("date", None),
    "a_start": ("date", None),
    "a_open": ("date", None),
    "b_open": ("date", None),
    "works": ("flow", "AUD"),
    "income": ("flow", "AUD"),
    "opex": ("flow", "AUD"),
    "renewals": ("flow", "AUD"),
    "operating": ("flow", "AUD"),
    "exit_value": ("value", "AUD"),
    "project_cash": ("flow", "AUD"),
    "net_cash_flow": ("flow", "AUD"),
    "funding_need": ("flow", "AUD"),
    "loan_principal": ("flow", "AUD"),
    "loan_draws": ("flow", "AUD"),
    "loan_interest": ("flow", "AUD"),
    "equity_cash_flow": ("flow", "AUD"),
}


def cells() -> dict[str, str]:
    """Return the numbered cells of the lesson."""
    numbered: dict[str, str] = {}
    for block in re.findall(r"```python\n(.*?)```", LESSON.read_text(), re.S):
        if match := re.match(r"# cell (\w+)", block):
            numbered[match[1]] = block
    return numbered


def equations(cell: str) -> list[str]:
    """Return the equation text of each ``equations(...)`` call of a cell, in order."""
    found = []
    for node in ast.walk(ast.parse(cell)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "equations"
        ):
            found.extend(ast.literal_eval(argument) for argument in node.args)
    return found


def declarations(cell: str) -> str:
    """Return the statements of a cell that declare values, dates and Flows."""
    kept = [
        statement
        for statement in ast.parse(cell).body
        if isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Attribute)
        and statement.value.func.attr in ("value", "date", "flow")
    ]
    return ast.unparse(ast.Module(body=kept, type_ignores=[]))


@pytest.fixture
def draft():
    return rk.Model(name="Mixed-use base plan").edit()


@pytest.fixture
def project(draft):
    """Return the project of cells 5 to 5c, 8 and 12, with the results of RESULTS."""
    numbered = cells()
    project = draft.add_entity(code="project", classification="project")
    namespace = {"rk": rk, "date": date, "project": project, "years": YEARS}
    for key in ("5", "5b", "5c", "8", "12"):
        exec(declarations(numbered[key]), namespace)
    for key, (kind, units) in RESULTS.items():
        if kind == "date":
            project.date(key=key)
        elif kind == "flow":
            project.flow(key=key, units=units, periods=YEARS)
        else:
            project.value(key=key, units=units)
    return project


@pytest.mark.parametrize("cell", EQUATION_CELLS)
def test_the_equations_of_the_cell_parse_as_written(project, cell):
    texts = equations(cells()[cell])
    assert texts
    project.equations(*texts)


class Names:
    """The names of equation text on the project: its keys."""

    units = rk.quantity.default_units

    def __init__(self, project) -> None:
        self.project = project

    def value(self, path: tuple[str, ...]):
        return self.project.ref(key=".".join(path))


def test_each_equation_reads_back_to_its_text(project):
    """The canonical text of each equation's records is the text of the cell."""
    numbered = cells()
    for cell in EQUATION_CELLS:
        for source in equations(numbered[cell]):
            assert read(text=source, names=Names(project)).text == source


def test_the_equations_of_the_cells_commit(draft, project):
    numbered = cells()
    texts = [text for cell in EQUATION_CELLS for text in equations(numbered[cell])]
    project.equations(*texts)
    model = draft.commit()
    (formulation,) = model.system.formulations
    assert len(formulation.constraints) == len(texts)
    assert {record.code for record in model.definitions.functions} == {
        "rx.flow.event",
        "rx.profile.uniform",
        "rx.profile.compounding",
        "rx.finance.npv",
        "rx.finance.interest",
        "rx.finance.irr",
        "rx.max",
        "Flow.at",
        "Flow.until",
        "Flow.cumulative",
        "Flow.diff",
    }


def run_as_written(*keys: str) -> dict[str, object]:
    """Run cells as written, statement by statement, from a fresh namespace."""
    numbered = cells()
    namespace: dict[str, object] = {"rk": rk, "date": date, "years": YEARS}
    for key in keys:
        for statement in ast.parse(numbered[key]).body:
            exec(ast.unparse(statement), namespace)
    return namespace


def named(formulations) -> list[str]:
    """Return the names of the named Formulations, depth first."""
    found = []
    for formulation in formulations or ():
        if formulation.name is not None:
            found.append(formulation.name)
        found.extend(named(formulation.formulations))
    return found


def test_cells_5_to_8_and_12_run_as_written():
    """The cells run with their named Formulations (#305) and commit twice."""
    namespace = run_as_written("5", "5b", "5c", "6", "7", "7b", "8", "12", "12b")
    model = namespace["model"]
    assert isinstance(model, rk.Model)
    assert named(model.system.formulations) == [
        "Dates",
        "Development",
        "Operations",
        "Sale and value",
        "Funding",
    ]
    assert model.metadata.previous is not None


def run_cells(*keys: str) -> dict[str, object]:
    """Run whole cells as written, from a fresh namespace with ``years``."""
    numbered = cells()
    namespace: dict[str, object] = {"rk": rk, "date": date, "years": YEARS}
    for key in keys:
        exec(numbered[key], namespace)
    return namespace


def test_cells_5_to_5c_run_as_written_and_infer_the_dates():
    """Cell 5 declares four dates; its equations define four more (#282, D44)."""
    model = run_cells("5", "5b", "5c")["draft"].commit()
    values = {
        value.key: value
        for value in model.entity(code="project").record.characteristics.values
    }
    for key in ("shared_start", "a_start", "a_open", "b_open"):
        assert values[key].kind is rk.model.ValueKind.DATE
        assert values[key].measure is None
    (root,) = model.system.formulations
    (dates,) = root.formulations
    assert (dates.name, len(dates.constraints)) == ("Dates", 5)
    assert values["a_income"].kind is rk.model.ValueKind.MEASUREMENT
    assert len(values["land"].flow.movements) == len(YEARS)


def test_cells_5_to_8_and_12_infer_the_results_that_they_do_not_declare():
    """The cells run as written with no declared results (#282, D44).

    The draft works out the kind and units of each result in ``RESULTS`` from
    its equations, and ``Entity.values`` shows each value as declared or
    inferred.
    """
    namespace = run_as_written("5", "5b", "5c", "6", "7", "7b", "8", "12", "12b")
    model = namespace["model"]
    assert isinstance(model, rk.Model)
    words = {
        rk.model.ValueKind.DATE: "date",
        rk.model.ValueKind.FLOW: "flow",
        rk.model.ValueKind.MEASUREMENT: "value",
    }
    inferred = {}
    for key in RESULTS:
        value = model.value(key=key)
        measure = None if value.measure is None else model.record_by_id(value.measure)
        units = None if measure is None else measure.record.units
        inferred[key] = (words[value.kind], units)
        if value.kind is rk.model.ValueKind.FLOW:
            # A Flow takes the Periods of its operands, one Movement in each.
            assert len(value.flow.movements) == len(YEARS)
    assert inferred == RESULTS
    shown = {
        row.values["key"]: row.values["inferred"]
        for row in model.entity(code="project").values.rows
    }
    assert {key for key, flag in shown.items() if flag} == set(RESULTS)
