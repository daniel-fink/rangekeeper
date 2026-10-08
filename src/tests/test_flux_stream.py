"""Independent numeric, structural and acausal acceptance for ADR-005."""

from datetime import date
from uuid import uuid4
import math
import subprocess
import sys
import pytest
from rangekeeper.model.flux import Flow, Stream, MissingValueHandling as Missing
from rangekeeper.model.duration import Span, Frequency, make_periods
from rangekeeper.calculations.series import (
    ResamplingMethod as R,
    AggregationMethod as A,
    AlignmentJoin as Join,
    MeanWeighting as Weight,
)
from rangekeeper.model.formulation import flow
from rangekeeper.model import Quantity, Update, Reference
from rangekeeper.model.system import Reduction, Hierarchy, View, Contributor
from rangekeeper.io import MemoryStore
from rangekeeper.run.execution import Executor
from rangekeeper.schema.enums import SolutionStatus
from rangekeeper_examples.flux import (
    collection,
    hierarchy_model,
    forward_specification,
    solve_example,
)


def test_collection_and_column_reuse(monkeypatch):
    from rangekeeper.calculations._batch import Batch

    stream = collection()
    assert stream._flows is None
    batch = stream._prepared()
    monkeypatch.setattr(
        Batch,
        "prepare",
        classmethod(lambda *a, **kw: pytest.fail("reprepared records")),
    )
    assert stream.sum().movements[0].number == 960
    assert stream.select(["Rent"]).sum().movements[0].number == 1200
    assert stream._prepared() is batch
    frame = stream.to_frame()
    frame[0, "Rent"] = 999
    assert stream.sum().movements[0].number == 960
    assert "Rent [AUD]" in str(stream.display())
    assert stream.flows[0].movements[0].number == 1200


def test_minimal_import_and_immutable_stream():
    code = "from rangekeeper.model.flux import Flow, Stream; import sys; Stream({}); Flow(units='AUD', movements=()).display(); assert not {'polars','matplotlib','pyomo.environ','IPython'} & set(sys.modules)"
    subprocess.run([sys.executable, "-c", code], check=True)
    stream = Stream({})
    with pytest.raises(AttributeError):
        stream.labels = ("edited",)


@pytest.mark.parametrize("period_content", [False, True])
def test_flow_display_preserves_records_and_uses_shared_rendering(period_content):
    start = date(2027, 1, 1)
    amounts = [0, None, -1.234]
    source = (
        Flow.from_periods(
            make_periods(start, frequency=Frequency.MONTH, count=3),
            amounts,
            units="AUD",
        )
        if period_content
        else Flow.from_events(
            [date(2027, 1, day) for day in (1, 2, 3)], amounts, units="AUD"
        )
    )
    recorded = source.to_data()
    table = source.display(name="<Cash>", transpose=True, precision=3)
    html = table._repr_html_()
    assert "&lt;Cash&gt; [AUD]" in html and "<Cash>" not in html
    assert "0.000" in html and "?" in html and "-1.234" in html
    assert "Jan 2027" in html if period_content else "2027-01-01" in html
    assert (
        html
        == Stream({"<Cash>": source}).display(transpose=True, precision=3)._repr_html_()
    )
    assert "Flow [AUD]" in source._repr_html_()
    assert "-1.23" in str(source.display())
    assert source.to_data() == recorded


def test_empty_flow_display_and_invalid_presentation_options():
    source = Flow(units="AUD", movements=())
    assert "Flow [AUD]" in source._repr_html_()
    for options in ({"name": ""}, {"precision": -1}, {"transpose": "yes"}):
        with pytest.raises((TypeError, ValueError)):
            source.display(**options)


@pytest.mark.parametrize("transpose", [False, True])
def test_native_display_shows_full_selection_and_restores_config(transpose):
    import polars as pl

    periods = make_periods(date(2001, 1, 1), frequency=Frequency.YEAR, count=80)
    label = "Income from the property's commercial and residential tenancies"
    source = Flow.from_periods(periods, [1234.567] * 80, units="AUD")
    table = Stream({label: source, "Other": source}).display(
        transpose=transpose, precision=1
    )
    with pl.Config(
        tbl_rows=2,
        tbl_cols=1,
        tbl_width_chars=12,
        fmt_str_lengths=6,
        tbl_hide_column_names=True,
        float_precision=0,
        thousands_separator=".",
        decimal_separator=",",
    ):
        before = pl.Config.state()
        html, text = table._repr_html_(), str(table)
        assert pl.Config.state() == before
    for rendered in (html, text):
        assert "Other [AUD]" in rendered and "1,234.6" in rendered
        assert "shape:" not in rendered
        assert all(str(year) in rendered for year in range(2001, 2081))
    assert label in text
    assert "commercial and residential tenancies [AUD]" in html
    assert "&quot;1,234.6&quot;" not in html


@pytest.mark.parametrize("method", ["_repr_html_", "__str__"])
def test_native_display_restores_config_after_renderer_failure(monkeypatch, method):
    import polars as pl

    table = Flow.from_events([date(2027, 1, 1)], [1], units="AUD").display()

    def fail_render(self):
        raise RuntimeError("native rendering failed")

    monkeypatch.setattr(pl.DataFrame, method, fail_render)
    with pl.Config(tbl_rows=3, tbl_hide_dataframe_shape=False):
        before = pl.Config.state()
        with pytest.raises(RuntimeError, match="native rendering failed"):
            getattr(table, method)()
        assert pl.Config.state() == before


@pytest.mark.parametrize("transpose", [False, True])
def test_native_display_missing_states_and_numeric_export(transpose):
    import polars as pl

    periods = make_periods(date(2027, 1, 1), frequency=Frequency.MONTH, count=3)
    receipts = Flow.from_periods(periods[:2], [0, None], units="AUD")
    stream = Stream(
        {
            "Receipts": receipts,
            "Expenses": Flow.from_periods(periods, [-1234.567] * 3, units="AUD"),
        },
        join=Join.UNION,
    )
    recorded = receipts.to_data()
    table = stream.display(transpose=transpose, precision=3)
    for rendered in (table._repr_html_(), str(table)):
        assert all(value in rendered for value in ("0.000", "?", "—", "-1,234.567"))
    assert "&quot;0.000&quot;" not in table._repr_html_()
    numeric = stream.to_frame()
    assert numeric["Receipts"].dtype == pl.Float64
    assert numeric["Receipts"].to_list() == [0, None, None]
    assert numeric["Expenses"].to_list() == [-1234.567] * 3
    assert receipts.to_data() == recorded


@pytest.mark.parametrize("transpose", [False, True])
def test_native_display_empty_collections(transpose):
    table = Stream({"Empty": Flow(units="AUD", movements=())}).display(
        transpose=transpose
    )
    for rendered in (table._repr_html_(), str(table)):
        assert ("Line item" if transpose else "Period / date") in rendered
        assert "Empty [AUD]" in rendered
    # A selection with no Flows retains its existing alignment error.
    empty = Stream({}).display(transpose=transpose)
    for render in (empty._repr_html_, empty.__str__):
        with pytest.raises(ValueError, match="at least one Flow"):
            render()


def test_span_anchor_partial_and_decoded_behavior():
    span = Span.from_duration(
        name="Leap", start=date(2024, 1, 31), frequency=Frequency.MONTH, count=3
    )
    assert span.end == date(2024, 4, 30)
    assert [p.end for p in span.periods(Frequency.MONTH)] == [
        date(2024, 2, 29),
        date(2024, 3, 31),
        date(2024, 4, 30),
    ]
    assert Span.from_data(span.to_data()).periods(Frequency.MONTH) == span.periods(
        Frequency.MONTH
    )
    with pytest.raises(ValueError, match="partial"):
        span.periods(Frequency.YEAR)
    assert len(span.periods(Frequency.YEAR, include_partial=True)) == 1
    with pytest.raises(ValueError):
        Span.from_duration(
            name="Empty", start=date(2024, 1, 1), frequency=Frequency.YEAR, count=0
        )


@pytest.mark.parametrize(
    "method,expected",
    [(R.SUM, 6), (R.MIN, 1), (R.MAX, 3), (R.FIRST, 1), (R.LAST, 3), (R.MEAN, 2)],
)
def test_resampling_independent_oracle_and_claims(method, expected):
    periods = make_periods(date(2027, 1, 1), frequency=Frequency.MONTH, count=3)
    claim = uuid4()
    source = Flow.from_periods(periods, [1, 2, 3], units="AUD")
    source = source.replace(
        movements=tuple(m.replace(claims=(claim,)) for m in source.movements)
    )
    stream = Stream({"Receipts": source})
    result = stream.resample(
        make_periods(date(2027, 1, 1), frequency=Frequency.QUARTER, count=1),
        method=method,
        weighting=Weight.OBSERVATIONS if method is R.MEAN else None,
    )
    assert result.flows[0].movements[0].number == expected
    assert result.flows[0].movements[0].claims == (claim,)
    assert result.coverage["Receipts"] == (1.0,)
    assert source.movements[0].id != result.flows[0].movements[0].id
    assert not result.flows[0].movements[0].has_field("date")


def test_methods_mapping_missing_zero_and_html_escape():
    periods = make_periods(date(2027, 1, 1), frequency=Frequency.MONTH, count=3)
    receipts = Flow.from_periods(periods[:2], [0, None], units="AUD")
    balance = Flow.from_periods(periods[:2], [10, 20], units="AUD")
    stream = Stream(
        {"<Receipts>": receipts, "Balance": balance}, missing=Missing.PROPAGATE
    )
    result = stream.resample(
        periods, method={"<Receipts>": R.SUM, "Balance": R.LAST}, missing=Missing.ZERO
    )
    assert [m.magnitude for m in result.flows[0].movements] == [0, None, 0]
    assert result.coverage["<Receipts>"] == (1, 0, 0)
    html = result.display(transpose=True)._repr_html_()
    assert (
        "&lt;Receipts&gt;" in html
        and "<Receipts>" not in html
        and "?" in html
        and "0.00" in html
    )
    with pytest.raises(ValueError, match="every label"):
        stream.resample(periods, method={"Balance": R.LAST})
    with pytest.raises(ValueError, match="weighting"):
        stream.resample(periods, method=R.MEAN)
    sparse = Stream(
        {
            "Receipt": receipts,
            "Balance": Flow.from_periods(periods, [1, 2, 3], units="AUD"),
        },
        join=Join.UNION,
    )
    assert "—" in str(sparse.display()) and "?" in str(sparse.display())


def test_cancellation_units_empty_and_boundaries():
    day = date(2027, 1, 1)
    stream = Stream(
        {
            str(i): Flow.from_events([day], [v], units="AUD")
            for i, v in enumerate([1e16, 1, -1e16])
        }
    )
    assert stream.sum().movements[0].number == math.fsum([1e16, 1, -1e16]) == 1
    with pytest.raises(ValueError, match="outside|crosses"):
        Stream(
            {
                "annual": Flow.from_periods(
                    make_periods(day, frequency=Frequency.YEAR, count=1),
                    [1],
                    units="AUD",
                )
            }
        ).resample(make_periods(day, frequency=Frequency.MONTH, count=12), method=R.SUM)
    with pytest.raises(ValueError, match="trim crosses"):
        stream = collection()
        stream.trim(
            Span(start_inclusive=date(2027, 2, 1), end_exclusive=date(2028, 1, 1))
        )
    with pytest.raises(ValueError):
        Stream({}).sum()


def test_model_selections_cannot_hide_numerical_transformations():
    model, ids = hierarchy_model()
    selected = Stream.from_values(model, [ids["A_rent"], ids["A_expense"]])
    declaration = flow.sum(model, id=uuid4(), summands=selected, total=ids["A_net"])
    assert declaration.bindings[0].value == ids["A_rent"]
    detached = selected.resample(
        make_periods(date(2027, 1, 1), frequency=Frequency.YEAR, count=1), method=R.SUM
    )
    with pytest.raises(ValueError, match="intermediate"):
        flow.sum(model, id=uuid4(), summands=detached, total=ids["A_annual"])
    with pytest.raises(ValueError, match="canonical"):
        detached.values
    assert detached.source_values == selected.values
    revised = model.revise(
        Update(
            metadata=model.metadata.replace(
                id=uuid4(), previous=model.id, name="Other revision"
            )
        )
    )
    with pytest.raises(ValueError, match="revision"):
        flow.sum(revised, id=uuid4(), summands=selected, total=ids["A_net"])
    assert selected.merge(selected.select(["rent"])).value_ids == selected.value_ids
    with pytest.raises(ValueError, match="twice"):
        Stream.from_values(model, [ids["A_rent"]] * 2)


def test_forward_reverse_hierarchy_and_numeric_parity():
    solved, ids = solve_example()
    hierarchy = Hierarchy(View(solved), membership_root=ids["root"])
    results = Reduction.flows(key="annual").execute(hierarchy)
    assert results.root_value.movements[0].number == 2880
    assert results.value(ids["A"]).movements[0].number == 1080
    assert results.entries[ids["root"]].period_coverage == (1.0,)
    assert set(results.value_ids.values()) == {ids["A_annual"], ids["B_annual"]}
    assert "Portfolio" in str(results.display())


def test_underdetermined_and_inconsistent_reverse_cases():
    model, ids = hierarchy_model()
    store = MemoryStore()
    store.put(model)
    base = forward_specification(model, ids)
    reverse = base.lock(
        ids["portfolio"], Quantity(magnitude=2880, units="AUD"), id=uuid4(), model=model
    )
    under = reverse.unlock(
        ids["A_rent"],
        ids=[m.id for m in model.value(ids["A_rent"]).flow.movements[-2:]],
        id=uuid4(),
        model=model,
    )
    run = Executor(store).execute(under)
    assert run.report.status.solution is SolutionStatus.FEASIBLE
    result = store.load_model(run.record.outputs[0])
    assert sum(
        m.number for m in result.value(ids["A_rent"]).flow.movements[-2:]
    ) == pytest.approx(320)
    assert any(d.code == "underdetermined" for d in run.report.diagnostics)
    failed = Executor(store).execute(reverse)
    assert failed.report.status.solution is SolutionStatus.INFEASIBLE
    assert not failed.record.outputs


def test_role_editing_is_explicit_atomic_and_revision_pinned():
    model, ids = hierarchy_model()
    base = forward_specification(model, ids)
    with pytest.raises(ValueError, match="quantity|recorded"):
        base.lock(ids["A_rent"], id=uuid4(), model=model)
    unlocked = base.unlock(ids["A_rent"], id=uuid4(), model=model)
    targets = {m.id for m in model.value(ids["A_rent"]).flow.movements}
    assert targets <= {r.target for r in unlocked.record.unknowns}
    assert not targets & {a.target.target for a in unlocked.record.assignments}
    assert unlocked.metadata.previous == base.id
    relocked = unlocked.lock(ids["A_rent"], recorded=True, id=uuid4(), model=model)
    assert not targets & {r.target for r in relocked.record.unknowns}
    assert len(base.record.assignments) == len(relocked.record.assignments)
    from rangekeeper.specification import Specification, SpecificationRecord
    from rangekeeper.model import Metadata

    store = MemoryStore()
    store.put(model)
    store.put(base)
    included = Specification(
        SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="0.7.0"), includes=(base.id,)
        )
    )
    with pytest.raises(ValueError, match="inherited"):
        included.unlock(ids["A_rent"], id=uuid4(), model=model, resolver=store)


@pytest.mark.parametrize("method", [R.MEAN, R.FIRST, R.LAST])
def test_symbolic_resampling_keeps_unknowns_and_fixed_membership(method):
    model, ids = hierarchy_model()
    relation = flow.resample(
        model,
        id=uuid4(),
        sequence=ids["A_net"],
        resampled=ids["A_annual"],
        method=method,
        weighting=Weight.ELAPSED if method is R.MEAN else None,
    )
    assert relation.bindings[0].value == ids["A_net"]
    assert relation.expressions
    with pytest.raises(ValueError, match="unknown symbols"):
        flow.resample(
            model,
            id=uuid4(),
            sequence=ids["A_net"],
            resampled=ids["A_annual"],
            method=R.SUM,
            missing=Missing.SKIP,
        )
    with pytest.raises(ValueError, match="piecewise"):
        flow.resample(
            model,
            id=uuid4(),
            sequence=ids["A_net"],
            resampled=ids["A_annual"],
            method=R.MIN,
        )


def test_selection_releases_unselected_coordinates_before_trim():
    months = make_periods(date(2027, 1, 1), frequency=Frequency.MONTH, count=12)
    years = make_periods(date(2027, 1, 1), frequency=Frequency.YEAR, count=1)
    stream = Stream(
        {
            "months": Flow.from_periods(months, [1] * 12, units="AUD"),
            "years": Flow.from_periods(years, [12], units="AUD"),
        }
    )
    stream._prepared()
    selected = stream.select(["months"])
    assert len(selected._prepared().metadata) == 12
    assert len(selected._prepared().coordinates) == 12
    assert (
        len(
            selected.trim(
                Span(start_inclusive=date(2027, 2, 1), end_exclusive=date(2027, 4, 1))
            )
            .flows[0]
            .movements
        )
        == 2
    )


@pytest.mark.parametrize("method", [R.MEAN, R.FIRST, R.LAST])
def test_passive_weighted_and_selected_resampling_executes(method):
    from rangekeeper.specification import Specification, SpecificationRecord
    from rangekeeper.model import Metadata
    from rangekeeper.specification.targets import assign_flow, unknown_flow
    from rangekeeper.schema.records import System

    model, ids = hierarchy_model()
    net = model.value(ids["A_net"])
    periods = net.flow.movements
    magnitudes = list(range(1, 13))
    data = model.system.to_data()
    data["formulations"] = []
    for entity in data["entities"]:
        for value in entity["characteristics"]["values"]:
            if value["id"] == str(net.id):
                for m, v in zip(value["flow"]["movements"], magnitudes):
                    m["magnitude"] = v
    model = model.revise(Update(system=System.from_data(data)))
    relation = flow.resample(
        model,
        id=uuid4(),
        sequence=net.id,
        resampled=ids["A_annual"],
        method=method,
        weighting=Weight.ELAPSED if method is R.MEAN else None,
    )
    model = model.revise(Update(system=model.system.replace(formulations=(relation,))))
    spec = Specification(
        SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
            model=model.id,
            assignments=assign_flow(model, net.id),
            unknowns=unknown_flow(model, ids["A_annual"]),
        )
    )
    store = MemoryStore()
    store.put(model)
    run = Executor(store).execute(spec)
    assert run.report.status.solution is SolutionStatus.FEASIBLE, run.report.to_data()
    result = (
        store.load_model(run.record.outputs[0])
        .value(ids["A_annual"])
        .flow.movements[0]
        .number
    )
    expected = (
        1
        if method is R.FIRST
        else (
            12
            if method is R.LAST
            else math.fsum(
                v * (m.period.end_exclusive - m.period.start_inclusive).days
                for v, m in zip(magnitudes, periods)
            )
            / 365
        )
    )
    assert result == pytest.approx(expected)


def test_policy_and_scalar_role_editing():
    from .test_temporal_execution import oracle, investigate
    from rangekeeper.schema.records import Policy

    model, ids = oracle()
    base = investigate(model, ids)
    unlocked = base.unlock(Reference(target=ids["initial"]), id=uuid4(), model=model)
    locked = unlocked.lock(
        Reference(target=ids["initial"]),
        Quantity(magnitude=120, units="AUD"),
        id=uuid4(),
        model=model,
    )
    assert (
        next(
            a.quantity.magnitude
            for a in locked.record.assignments
            if a.target.target == ids["initial"]
        )
        == 120
    )
    with pytest.raises(ValueError):
        unlocked.lock(
            Reference(target=ids["initial"]), recorded=True, id=uuid4(), model=model
        )


def test_role_edit_rejects_policy_control_without_changing_the_specification():
    from .test_temporal_execution import oracle, investigate
    from rangekeeper.schema.records import Policy
    from rangekeeper.specification import Specification

    model, ids = oracle()
    base = investigate(model, ids)
    record = base.record.replace(
        assignments=tuple(
            a for a in base.record.assignments if a.target.target != ids["initial"]
        ),
        policy=Policy(
            id=uuid4(), targets=(Reference(target=ids["initial"]),), decisions=()
        ),
    )
    controlled = Specification(record)
    before = controlled.to_data()
    with pytest.raises(ValueError, match="policy-controlled"):
        controlled.unlock(Reference(target=ids["initial"]), id=uuid4(), model=model)
    assert controlled.to_data() == before
