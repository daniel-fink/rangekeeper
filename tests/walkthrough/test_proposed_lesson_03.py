"""The equations of lesson 03's proposed cells parse and are checked as written.

The cells come from ``examples/walkthrough/proposed/03_cases_debt_equity.md``.
Cells 6 to 8 and 12 write their equations with equation functions and Flow
methods (#278). This test reads each equation from the cells as written,
adds it to the project of cells 5 to 5c, and checks that its records read
back to the same text.

The cells themselves do more than these equations: they group the equations
in named Formulations (``add_formulation``, #305), and they leave the
results that they do not rely on undeclared, for the draft to infer (#282).
Until those land, the test declares those results itself (``RESULTS``) and
adds the equations to the entity.
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
def project():
    """Return the project of cells 5 to 5c, 8 and 12, with the results of RESULTS."""
    numbered = cells()
    draft = rk.Model(name="Mixed-use base plan").edit()
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
