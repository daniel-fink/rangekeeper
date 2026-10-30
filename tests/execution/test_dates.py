"""Date roles and date equations in a solve (#280).

Lesson 03 cell 5 declares the plan's dates and the equations between them, and
cell 9 fixes the start dates. ``model`` runs cell 5 from the proposed cells as
written, but declares the dates that cell 5 leaves for the draft to infer
(#282) first.
"""

import ast
import re
from datetime import date
from pathlib import Path

import pytest

import rangekeeper as rk
from rangekeeper.errors import ContractError, UnsupportedError
from rangekeeper.execution import Status, solve
from rangekeeper.run import SolutionStatus
from rangekeeper.specification import Role

LESSON = (
    Path(__file__).resolve().parents[2]
    / "examples/walkthrough/proposed/03_cases_debt_equity.md"
)
# The dates that cell 5 leaves for the draft to infer (#282).
INFERRED = ("shared_start", "a_start", "a_open", "b_open")
NEVER = rk.duration.NEVER


def cell(number: str) -> str:
    for block in re.findall(r"```python\n(.*?)```", LESSON.read_text(), re.S):
        if block.startswith(f"# cell {number}\n"):
            return block
    raise LookupError(number)


@pytest.fixture(scope="module")
def model() -> rk.Model:
    """Return the Model of lesson 03 cell 5, as written."""
    namespace: dict[str, object] = {"rk": rk}
    for statement in ast.parse(cell("5")).body:
        code = ast.unparse(statement)
        if "add_formulation" in code:
            for key in INFERRED:
                namespace["project"].date(key=key)  # type: ignore[attr-defined]
        exec(code, namespace)
    return namespace["draft"].commit()  # type: ignore[attr-defined]


@pytest.fixture(scope="module")
def base(model):
    """Return cell 9's fixes of the plan's dates."""
    return (
        model.specify(name="Base case")
        .fix(base_date=date(2027, 1, 1), sale_date=date(2037, 1, 1))
        .fix(start_date=date(2027, 1, 1), b_start=date(2029, 1, 1))
    )


def test_fixed_dates_have_roles(base):
    roles = {
        row.values["key"]: (row.values["role"], row.values["quantity"])
        for row in base.roles.rows
    }
    assert roles["start_date"] == (Role.FIXED, date(2027, 1, 1))
    assert roles["a_open"] == (Role.FREE, None)
    fixed = [
        a
        for a in base.record.assignments
        if a.target.target == base.model.value(key="b_start").id
    ]
    assert fixed[0].date == date(2029, 1, 1) and fixed[0].quantity is None


def test_the_date_equations_determine_the_plan(base):
    outcome = solve(specification=base).raise_for_status()
    assert outcome["shared_start"] == date(2027, 1, 1)
    assert outcome["a_start"] == date(2028, 1, 1)
    assert outcome["a_open"] == date(2030, 1, 1)
    assert outcome["b_open"] == date(2031, 1, 1)
    assert outcome["sale_date"] == date(2037, 1, 1)


def test_a_start_that_breaks_the_sequence_is_infeasible(base):
    early = solve(specification=base.fix(b_start=date(2027, 6, 1)))
    assert early.status is Status.INFEASIBLE
    assert early.run.report.status.solution == SolutionStatus.INFEASIBLE


def test_never_is_a_date_that_does_not_happen(base):
    outcome = solve(specification=base.fix(b_start=NEVER)).raise_for_status()
    assert outcome["b_open"] is NEVER
    assert outcome["a_open"] == date(2030, 1, 1)


def test_execute_publishes_the_dates_and_validates_the_run(model, base):
    store = rk.io.MemoryStore()
    store.put(model)
    executed = rk.execution.execute(specification=base, store=store)
    output = store.load_model(executed.run.record.outputs[0])
    assert output.value(key="a_open").date == date(2030, 1, 1)
    assert output.value(key="start_date").date == date(2027, 1, 1)
    rk.run.validate(run=executed.run, resolver=store).raise_if_invalid()


def test_a_date_fix_round_trips_as_data(base):
    data = base.record.to_data()
    dates = [a for a in data["assignments"] if "date" in a]
    assert {a["date"] for a in dates} == {"2027-01-01", "2029-01-01", "2037-01-01"}
    assert all("quantity" not in a for a in dates)
    again = rk.specification.SpecificationRecord.from_data(data)
    assert again.to_data() == data


def test_never_round_trips_as_data(base):
    data = base.fix(b_start=NEVER).record.to_data()
    (never,) = [a for a in data["assignments"] if "never" in a]
    assert never == {"target": never["target"], "never": "never"}


def test_a_date_value_takes_a_date_and_a_number_takes_a_quantity(base):
    with pytest.raises(ContractError):
        base.fix(start_date="1 AUD")
    draft = rk.Model(name="Mixed").edit()
    project = draft.add_entity(code="project", classification="project")
    project.value(key="land_cost", units="AUD")
    project.date(key="start_date")
    mixed = draft.commit().specify(name="Mixed")
    with pytest.raises(ContractError):
        mixed.fix(land_cost=date(2027, 1, 1))


def test_a_free_date_that_no_equation_determines_is_unsupported():
    draft = rk.Model(name="Loose").edit()
    project = draft.add_entity(code="project", classification="project")
    project.date(key="start_date")
    project.date(key="b_start")
    project.equations("b_start >= start_date + 1 year")
    loose = draft.commit().specify(name="Loose").fix(start_date=date(2027, 1, 1))
    outcome = solve(specification=loose)
    assert outcome.status is Status.UNSUPPORTED
    with pytest.raises(UnsupportedError) as raised:
        outcome.raise_for_status()
    assert "b_start" in str(raised.value)


def test_a_new_revision_keeps_the_date_fixes(model, base):
    draft = model.edit()
    draft.entity(code="project").value(key="land_cost", units="AUD")
    moved = base.on(model=draft.commit())
    assert solve(specification=moved).raise_for_status()["a_open"] == date(2030, 1, 1)
