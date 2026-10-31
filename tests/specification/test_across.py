"""Cases across market paths: one case for each path, matched by key (#306)."""

from datetime import date

import pytest

import rangekeeper as rk
from rangekeeper.errors import Code, ContractError, UnitError
from rangekeeper.execution import Status, execute, solve
from rangekeeper.io import MemoryStore
from rangekeeper.market import Paths
from rangekeeper.specification import Role

YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2030, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)


def flow(*magnitudes: float, units: str = "ratio", periods=YEARS) -> rk.flow.Flow:
    return rk.flow.Flow.from_periods(
        periods=periods, magnitudes=magnitudes, units=units
    )


def model() -> rk.Model:
    draft = rk.Model(name="Index").edit()
    project = draft.add_entity(code="project", classification="project")
    project.flow(key="rent_index", units="ratio", periods=YEARS)
    project.flow(key="cost_index", units="ratio", periods=YEARS)
    project.value(key="base_rent", units="AUD")
    project.equations("rent = rent_index * base_rent", "cost = cost_index * base_rent")
    return draft.commit()


def paths(name: str = "rent_index") -> Paths:
    return Paths.from_flows(
        flows={
            "up": {name: flow(1, 1.1, 1.2)},
            "down": {name: flow(1, 0.9, 0.8)},
        }
    )


@pytest.fixture(scope="module")
def base() -> rk.Specification:
    return model().specify(name="Base").fix(base_rent="100 AUD", cost_index=1)


def test_across_makes_one_case_for_each_path(base):
    market = paths()
    batch = base.across(paths=market)
    assert len(batch.record.cases) == 2
    assert batch.metadata.name == "Base"
    up = batch.case(key="up")
    assert up.metadata.previous == base.id
    path = up.record.path
    assert (path.paths, path.key) == (market.id, "up")
    (binding,) = path.series
    assert binding.series == "rent_index"
    assert binding.value.target == base.model.value(key="rent_index").id
    # The case refers to the path; it does not copy the amounts.
    assert {a.target.target for a in up.record.assignments} == {
        a.target.target for a in base.record.assignments
    }
    fixed = [row for row in up.roles.rows if row.values["key"] == "rent_index"]
    assert [row.values["role"] for row in fixed] == [Role.FIXED] * 3
    assert [row.values["quantity"].number for row in fixed] == pytest.approx(
        [1, 1.1, 1.2]
    )


def test_the_solve_fixes_each_case_from_its_path(base):
    market = paths()
    outcome = solve(specification=base.across(paths=market))
    assert outcome.status is Status.FEASIBLE
    assert len(outcome.cases) == 2
    assert outcome.run.paths == market.id
    for key in market.keys:
        case = outcome.case(key=key)
        assert case.run.paths == market.id
        assert case["rent_index"] == market[key]["rent_index"]
    rent = outcome.case(key="down")["rent"]
    assert [m.number for m in rent.movements] == pytest.approx([100, 90, 80])


def test_series_maps_a_value_whose_key_differs(base):
    market = paths(name="index")
    outcome = solve(
        specification=base.across(paths=market, series={"rent_index": "index"})
    )
    assert outcome.case(key="up")["rent_index"] == market["up"]["index"]


def test_matching_errors_list_the_series_and_the_model_keys(base):
    with pytest.raises(ContractError) as unmatched:
        base.across(paths=paths(name="market_index"))
    assert unmatched.value.code is Code.REFERENCE_MISSING
    assert unmatched.value.values["series"] == ["market_index"]
    assert {"rent_index", "cost_index"} <= set(unmatched.value.values["model"])
    with pytest.raises(ContractError) as lacking:
        base.across(paths=paths(), series={"rent_index": "index"})
    assert lacking.value.code is Code.REFERENCE_MISSING
    both = Paths.from_flows(
        flows={"a": {"rent_index": flow(1, 1, 1), "index": flow(1, 1, 1)}}
    )
    with pytest.raises(ContractError) as twice:
        base.across(paths=both, series={"rent_index": "index"})
    assert twice.value.code is Code.UNIQUE
    cost = Paths.from_flows(flows={"a": {"cost_index": flow(1, 1, 1)}})
    with pytest.raises(ContractError, match="cost_index"):
        base.across(paths=cost)  # the base fixes cost_index too
    with pytest.raises(ContractError, match="#284"):
        base.across(paths=paths(), series={"rent_index": {"hotel": "rent_index"}})


def test_a_path_must_have_the_periods_and_units_of_its_value(base):
    longer = YEARS.extend(count=1)
    with pytest.raises(ContractError) as periods:
        base.across(
            paths=Paths.from_flows(
                flows={"a": {"rent_index": flow(1, 1, 1, 1, periods=longer)}}
            )
        )
    assert periods.value.code is Code.ALIGNMENT_DIFFER
    with pytest.raises(UnitError):
        base.across(
            paths=Paths.from_flows(
                flows={"a": {"rent_index": flow(1, 1, 1, units="AUD")}}
            )
        )


def test_a_path_case_is_a_leaf(base):
    batch = base.across(paths=paths())
    with pytest.raises(ContractError) as twice:
        batch.across(paths=paths())
    assert twice.value.code is Code.BATCH_UNSUPPORTED
    with pytest.raises(ContractError, match="across"):
        batch.case(key="up").fix(base_rent="200 AUD")


def test_execute_publishes_the_paths_and_a_store_resolves_them(base):
    market = paths()
    store = MemoryStore()
    for document in (base.model,):
        store.put(document)
    batch = base.across(paths=market)
    outcome = execute(specification=batch, store=store)
    assert store.load_paths(market.id) == market
    assert store.load_run(outcome.run.id).paths == market.id
    stored = store.load_specification(batch.id)
    assert stored.check(resolver=store) is stored
    again = solve(specification=stored, resolver=store)
    assert again.case(key="up")["rent_index"] == market["up"]["rent_index"]


def test_a_bundle_carries_the_paths_that_a_run_pins(tmp_path, base):
    pytest.importorskip("pyarrow")
    from rangekeeper.io.bundle import Reader, write

    market = paths()
    store = MemoryStore()
    store.put(base.model)
    outcome = execute(specification=base.across(paths=market), store=store)
    write(
        root=tmp_path / "bundle",
        model=base.model,
        documents=(outcome.run,),
        resolver=store,
    )
    reader = Reader(root=tmp_path / "bundle")
    assert reader.load_paths(market.id) == market
    assert reader.load_run(outcome.run.id).paths == market.id
