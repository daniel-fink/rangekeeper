"""Batch Outcomes: case keys, the by-case table and Streams of solved Flows."""

import pytest

import rangekeeper as rk
from rangekeeper.execution import Outcome, Status
from rangekeeper.flow import Stream
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, MissingReferenceError
from tests.execution.test_temporal_execution import investigate, oracle

pytest.importorskip("pyomo")
pytest.importorskip("highspy")


def batch_outcome():
    model, ids = oracle()
    base = investigate(model, ids)
    batch = base.cases(cases={"low": {"rate": 0.05}, "high": {"rate": 0.2}})
    return base, rk.execution.solve(specification=batch)


def test_a_case_outcome_has_the_key_of_its_case():
    base, outcome = batch_outcome()
    assert [case.key for case in outcome.cases] == ["low", "high"]
    low = outcome.case(key="low")
    assert isinstance(low, Outcome)
    assert low is outcome.cases[0]
    with pytest.raises(MissingReferenceError) as error:
        outcome.case(key="middle")
    assert error.value.candidates == ("low", "high")
    with pytest.raises(ContractError) as error:
        low.case(key="low")
    assert error.value.code is Code.BATCH_REQUIRED
    # A Specification without a name gives an Outcome without a key.
    assert rk.execution.solve(specification=base).key is None


def test_the_table_has_one_row_for_each_case():
    _, outcome = batch_outcome()
    table = outcome.table("pv", "rate")
    assert table.columns == ("case", "status", "pv", "rate")
    assert table.column("case") == ("low", "high")
    assert table.column("status") == (Status.FEASIBLE, Status.FEASIBLE)
    assert table.column("rate") == (
        rk.Quantity(magnitude=0.05, units="dimensionless"),
        rk.Quantity(magnitude=0.2, units="dimensionless"),
    )
    low, high = table.column("pv")
    assert low > high
    leaf = outcome.case(key="low").table("pv")
    assert leaf.column("case") == ("low",)
    assert leaf.column("pv") == (low,)
    with pytest.raises(TypeError, match="at least one"):
        outcome.table()


def test_a_stream_holds_the_solved_flows_by_key():
    _, outcome = batch_outcome()
    low = outcome.case(key="low")
    stream = low.stream("cash", "discounted")
    assert isinstance(stream, Stream)
    assert stream.names == ("cash", "discounted")
    assert stream.flows[0] == low["cash"]
    with pytest.raises(ContractError) as error:
        outcome.stream("cash")
    assert error.value.code is Code.BATCH_UNSUPPORTED
    with pytest.raises(ContractError, match="not a Flow") as error:
        low.stream("pv")
    assert error.value.values == {"key": "pv"}
    with pytest.raises(TypeError, match="at least one"):
        low.stream()


def test_a_case_without_an_output_has_no_values_in_the_table():
    model, ids = oracle()
    batch = investigate(model, ids).cases(
        cases={"fixed": {}, "conflict": {"pv": "1 AUD"}}
    )
    outcome = rk.execution.solve(specification=batch)
    table = outcome.table("pv")
    assert table.column("case") == ("fixed", "conflict")
    status = table.column("status")
    assert status[0] is Status.FEASIBLE
    assert status[1] is not Status.FEASIBLE
    assert table.column("pv")[1] is None
    assert outcome.status is status[1]
