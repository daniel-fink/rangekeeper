"""``rk.execution.solve`` runs the rules of a Specification, with stored evidence (#300).

The project and its expected values come from ``test_sequential_verification``, which
holds worked tables and a plain calculation that share no code with the engine. Here
the rules are written with the public query, and the solve is the public one.
"""

from copy import deepcopy
from datetime import date

import pytest

import rangekeeper as rk
from rangekeeper.execution import _parallel
from rangekeeper.execution.config import ExecutionConfig
from rangekeeper.io import MemoryStore
from rangekeeper.schema.records import RuleEvidence
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    AvailabilityError,
    ContractError,
    MissingReferenceError,
    ValidationError,
)
from tests.execution.rule.test_sequential_verification import (
    HAND,
    HISTORIES,
    histories,
    independent,
    project_model,
)
from tests.execution.test_lesson05 import LESSON_05, cells

pytest.importorskip("pyomo")
pytest.importorskip("highspy")

NEVER = rk.duration.NEVER
Window = rk.specification.Window
DECIDED = rk.execution.DecisionResult.DECIDED
FIXED = {
    "base_date": date(2027, 1, 1),
    "a_cost": "100 AUD",
    "b_cost": "60 AUD",
    "a_rent": "30 AUD",
    "b_rent": "20 AUD",
    "site_value": "5 AUD",
    "equity": "30 AUD",
    "loan_limit": "60 AUD",
    "rate": "10 % pa",
}


def base(model: rk.Model | None = None) -> rk.Specification:
    model = project_model() if model is None else model
    return model.specify(name="Rules").fix(**FIXED)


def strategy() -> rk.Specification:
    """Return the rules of ADR-021's worked examples, written with the public query."""
    start = Window(earliest=date(2027, 1, 1), latest=date(2030, 1, 1))
    b_start = Window(earliest="shared_start + 1 year", latest=date(2032, 1, 1))
    sale = Window(earliest=date(2033, 1, 1), latest=date(2033, 1, 1))
    return base().fix(
        start_date=start.where(condition="rent_index >= 1.05").first(otherwise=NEVER),
        b_start=b_start.where(
            condition="rent_index >= 1.10 "
            "and equity_available + loan_available >= b_cost"
        ).first(otherwise=NEVER),
        b_sale_date=sale.where(condition="b_start == NEVER").first(otherwise=NEVER),
    )


@pytest.fixture(scope="module")
def paths() -> rk.market.Paths:
    return histories()


@pytest.fixture(scope="module")
def solved(paths) -> rk.execution.Outcome:
    return rk.execution.solve(specification=strategy().across(paths=paths))


def by_key(rows):
    return [(row.key, row.decision_date, row.result) for row in rows]


@pytest.mark.parametrize("key", HISTORIES)
def test_the_solve_agrees_with_the_independent_calculation(solved, key):
    case = solved.case(key=key)
    assert case.status is rk.execution.Status.FEASIBLE
    start, b_start, sale, npv = independent(HISTORIES[key])
    assert case["start_date"] == start
    assert case["b_start"] == b_start
    assert case["b_sale_date"] == sale
    assert case["equity_npv"].number == pytest.approx(npv, abs=1e-6)


@pytest.mark.parametrize("key", HISTORIES)
def test_the_run_records_the_trace_and_the_solve_count(solved, key):
    evidence = solved.case(key=key).run.rule_evidence
    hand = HAND[key]
    assert isinstance(evidence, RuleEvidence)
    assert evidence.verified is True
    assert evidence.provisional_solves == hand.provisional_solves
    assert {item.key: item.decision_date for item in evidence.decided} == (
        hand.decided_on
    )


def test_stored_evidence_reads_back(solved):
    run = solved.case(key="late").run
    again = rk.Run.from_data(run.to_data())
    assert again.rule_evidence == run.rule_evidence


def test_a_case_without_rules_has_no_evidence(paths):
    outcome = rk.execution.solve(
        specification=base()
        .fix(
            start_date=date(2027, 1, 1),
            b_start=date(2029, 1, 1),
            b_sale_date=NEVER,
        )
        .across(paths=paths)
    )
    case = outcome.case(key="late")
    assert case.run.rule_evidence is None
    assert len(outcome.decisions) == 0
    assert len(case.trace) == 0


def test_decisions_have_one_row_for_each_case_and_window_date(solved):
    late = [row for row in solved.decisions if row.case == "late"]
    assert by_key(late) == by_key(solved.case(key="late").trace)
    first = late[0]
    assert (first.key, first.decision_date) == ("start_date", date(2027, 1, 1))
    assert first.observed["rent_index"].number == pytest.approx(1.00)
    assert first.condition is False
    assert first.value is None


def test_where_selects_by_key_and_result(solved):
    decided = solved.decisions.where(key="b_start", result=DECIDED)
    assert [(row.case, row.value) for row in decided] == [
        ("recovery", date(2032, 1, 1))
    ]
    assert {row.key for row in solved.decisions.where(result=DECIDED)} == {
        "start_date",
        "b_start",
        "b_sale_date",
    }
    with pytest.raises(MissingReferenceError):
        solved.decisions.where(key="not_a_rule")
    with pytest.raises(TypeError):
        solved.decisions.where(result="decided")
    with pytest.raises(TypeError):
        solved.decisions.where("b_start")


def test_observations_are_known_by_their_window_date(solved):
    rows = solved.decisions.observations
    assert rows
    assert all(row.available_on <= row.decision_date for row in rows)
    assert {row.source for row in rows} >= {
        rk.execution.ObservationSource.PATH,
        rk.execution.ObservationSource.SOLVED,
    }


def test_a_batch_has_no_single_trace(solved):
    with pytest.raises(ContractError) as raised:
        _ = solved.trace
    assert raised.value.code is Code.BATCH_UNSUPPORTED


def test_the_table_shows_the_records(solved):
    table = solved.case(key="late").trace.table
    assert table.column("key")[0] == "start_date"
    assert "rent_index = " in table.column("observed")[0]
    assert "<table" in solved.decisions._repr_html_()


def test_cell_18_runs_as_written(solved, paths):
    """Lesson 05's checks, on this project: lesson 05's Model waits (see test_lesson05)."""
    fixed = base().fix(
        start_date=date(2028, 1, 1), b_start=date(2030, 1, 1), b_sale_date=NEVER
    )
    namespace = {
        "rk": rk,
        "paths": paths,
        "strategy_outcome": solved,
        "fixed_outcome": rk.execution.solve(specification=fixed.across(paths=paths)),
    }
    exec(cells(LESSON_05)["18"], namespace)


def _many_histories() -> rk.market.Paths:
    """Return each history three times: the first two cases stay in this process."""
    years = rk.duration.Span(start=date(2026, 1, 1), end=date(2037, 1, 1)).periods(
        frequency=rk.duration.Frequency.YEAR
    )
    return rk.market.Paths.from_flows(
        flows={
            f"{key} {copy}": {
                "rent_index": rk.flow.Flow.from_periods(
                    periods=years, magnitudes=list(index), units="ratio"
                )
            }
            for key, index in HISTORIES.items()
            for copy in range(3)
        }
    )


def test_the_evidence_does_not_depend_on_the_worker_count(monkeypatch):
    """A worker holds only the Models and Paths; the decisions and traces must match."""
    monkeypatch.setattr(_parallel, "START_SECONDS", 0.0)
    started = []
    original = _parallel.Worker.start

    def start(command, *, role="solver worker"):
        worker = original(command, role=role)
        if role == "batch worker":
            started.append(worker)
        return worker

    monkeypatch.setattr(_parallel.Worker, "start", staticmethod(start))
    batch = strategy().across(paths=_many_histories())
    alone = rk.execution.solve(specification=batch, config=ExecutionConfig(workers=1))
    assert not started
    together = rk.execution.solve(
        specification=batch, config=ExecutionConfig(workers=3)
    )
    assert started
    assert _leaf_evidence(alone) == _leaf_evidence(together)
    assert by_key(alone.decisions) == by_key(together.decisions)
    assert alone.table("start_date", "b_start").rows == (
        together.table("start_date", "b_start").rows
    )


def _leaf_evidence(outcome):
    return [
        leaf.run.rule_evidence.to_data() for leaf in outcome.walk() if not leaf.cases
    ]


def _unavailable() -> rk.Specification:
    """Return a rule whose first window date reads before the first known Movement."""
    years = rk.duration.Span(start=date(2026, 1, 1), end=date(2028, 1, 1)).periods(
        frequency=rk.duration.Frequency.YEAR
    )
    rule = (
        Window(periods=years)
        .where(condition="rent_index >= 1.05")
        .first(otherwise=NEVER)
    )
    return base().fix(start_date=rule, b_start=NEVER, b_sale_date=NEVER)


def test_an_unavailable_observation_fails_its_case_with_the_key(paths):
    outcome = rk.execution.solve(specification=_unavailable().across(paths=paths))
    case = outcome.case(key="late")
    assert case.status is rk.execution.Status.FAILED
    assert case.run.rule_evidence is None
    with pytest.raises(AvailabilityError) as raised:
        case.raise_for_status()
    assert raised.value.code is Code.OBSERVATION_UNAVAILABLE
    assert raised.value.key == "start_date"
    assert raised.value.decision_date == date(2026, 1, 1)


def test_a_rule_with_no_window_date_fails_its_case(paths):
    rule = Window().where(condition="b_cost >= 1 AUD").first(otherwise=NEVER)
    outcome = rk.execution.solve(
        specification=base()
        .fix(start_date=rule, b_start=NEVER, b_sale_date=NEVER)
        .across(paths=paths)
    )
    case = outcome.case(key="late")
    assert case.status is rk.execution.Status.FAILED
    assert any(item.code == Code.RULE_CAPABILITY.value for item in case.diagnostics)


def test_a_failed_case_keeps_its_trace_up_to_the_failure(paths):
    window = Window(earliest="shared_start + 1 year", latest=date(2032, 1, 1))
    rule = window.where(condition="equity_available >= b_cost").first(otherwise=NEVER)
    start = Window(earliest=date(2027, 1, 1), latest=date(2030, 1, 1))
    draft = project_model().edit()
    draft.entity(code="project").equations("start_date <= date(2029, 1, 1)")
    made = base(draft.commit()).fix(
        start_date=start.where(condition="rent_index >= 1.05").first(otherwise=NEVER),
        b_sale_date=NEVER,
        b_start=rule,
    )
    outcome = rk.execution.solve(specification=made.across(paths=paths))
    case = outcome.case(key="late")
    assert case.status is rk.execution.Status.FAILED
    evidence = case.run.rule_evidence
    assert evidence.verified is False
    assert [item.key for item in evidence.decided] == ["start_date"]
    assert [row.key for row in case.trace.where(result=DECIDED)] == ["start_date"]
    stopped = next(
        item for item in case.diagnostics if item.code == "provisional_infeasible"
    )
    assert stopped.values["window_date"] == "2031-01-01"
    assert stopped.values["decided"]["start_date"] == "2030-01-01"
    assert tuple(stopped.values["constraints"]) == ("start_date <= date(2029, 1, 1)",)


@pytest.fixture()
def stored(paths):
    store = MemoryStore()
    outcome = rk.execution.execute(
        specification=strategy().across(paths=paths), store=store
    )
    return store, outcome


def changed_trace(run: rk.Run, *, condition: bool) -> rk.Run:
    data = deepcopy(run.to_data())
    data["report"]["rule_evidence"]["checks"][0]["condition"] = condition
    return rk.Run.from_data(data)


def test_a_bundle_keeps_the_evidence(stored, tmp_path):
    pytest.importorskip("pyarrow")
    from rangekeeper.io.bundle import Reader, write

    store, outcome = stored
    case = outcome.case(key="late")
    write(
        root=tmp_path / "bundle",
        model=case.model,
        documents=[case.run],
        resolver=store,
    )
    read = Reader(root=tmp_path / "bundle").load_run(case.run.id)
    assert read.rule_evidence == case.run.rule_evidence
    assert rk.run.validate(run=read, resolver=store).valid


def test_validate_checks_a_stored_trace(stored):
    store, outcome = stored
    run = store.load_run(outcome.case(key="late").run.id)
    assert rk.run.validate(run=run, resolver=store).valid
    report = rk.run.validate(run=changed_trace(run, condition=True), resolver=store)
    assert not report.valid
    assert report.issues[0].code is Code.RULE_TRACE


def test_validate_rejects_an_output_without_a_verified_trace(stored):
    store, outcome = stored
    data = deepcopy(store.load_run(outcome.case(key="late").run.id).to_data())
    data["report"]["rule_evidence"]["verified"] = False
    report = rk.run.validate(run=rk.Run.from_data(data), resolver=store)
    assert not report.valid
    assert "verified decision trace" in report.issues[0].message


def test_a_replay_gives_the_same_trace(stored):
    store, outcome = stored
    replayed = rk.execution.replay(run=outcome.run, store=store)
    assert replayed.diagnostics == ()
    assert replayed.raise_for_status() is replayed


class ChangedPaths:
    """A store that returns other amounts in place of its Paths, with the same identity."""

    def __init__(self, store: MemoryStore, paths: rk.market.Paths) -> None:
        self.store = store
        self.paths = paths

    def load_model(self, id):
        return self.store.load_model(id)

    def load_specification(self, id):
        # From data, as a store on disk gives it: it keeps no Paths of its own.
        return rk.Specification.from_data(self.store.load_specification(id).to_data())

    def load_run(self, id):
        return self.store.load_run(id)

    def load_paths(self, id):
        return self.paths if id == self.paths.id else self.store.load_paths(id)


def with_amount(
    paths: rk.market.Paths, *, year: int, magnitude: float
) -> rk.market.Paths:
    """Return ``paths`` with one amount of ``rent_index`` changed on the ``late`` path."""
    data = deepcopy(paths.to_data())
    for member in data["members"]:
        if member["key"] == "late":
            member["amounts"][0]["magnitudes"][year - 2026] = magnitude
    return rk.market.Paths.from_data(data)


def test_a_replay_on_changed_path_data_names_the_first_window_date(stored, paths):
    store, outcome = stored
    changed = ChangedPaths(store, with_amount(paths, year=2028, magnitude=1.2))
    replayed = rk.execution.replay(run=outcome.run, store=changed)
    first = replayed.diagnostics[0]
    assert first.code == Code.REPLAY_MISMATCH.value
    assert first.values["case"] == "late"
    assert first.values["key"] == "start_date"
    # The amount of 2028 is known on 2029-01-01.
    assert first.values["on"] == "2029-01-01"
    with pytest.raises(ContractError) as raised:
        replayed.raise_for_status()
    assert raised.value.code is Code.REPLAY_MISMATCH


def test_a_changed_stored_trace_is_a_replay_mismatch(stored):
    store, outcome = stored
    case = outcome.case(key="late")
    run = changed_trace(store.load_run(case.run.id), condition=True)
    replayed = rk.execution.replay(run=run, store=store)
    first = replayed.diagnostics[0]
    assert first.code == Code.REPLAY_MISMATCH.value
    assert first.values["on"] == "2027-01-01"
    assert first.values["key"] == "start_date"


def test_validate_report_type_of_the_trace_check_is_an_error(stored):
    store, outcome = stored
    run = changed_trace(store.load_run(outcome.case(key="late").run.id), condition=True)
    with pytest.raises(ValidationError):
        rk.run.validate(run=run, resolver=store).raise_if_invalid()
