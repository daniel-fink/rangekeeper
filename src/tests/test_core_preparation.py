"""Independent checks for scope preparation, source attribution and comparison."""

from pathlib import Path
from uuid import UUID, uuid4

import pytest
import yaml

from rangekeeper._record_index import RecordIndex, walk_data
from rangekeeper._records import exact_equal
from rangekeeper.errors import ContractError, IdentityConflictError, ReferenceTypeError
from rangekeeper.model import (
    Model,
    Definitions,
    Measure,
    Metadata,
    Assembly,
    Entity,
    Quantity,
)
from rangekeeper.model.definitions import measure
from rangekeeper.model.expression import Constraint, Expression, ExpressionKind
from rangekeeper.model.expression.domains import DomainCompatibility, compare_domains
from rangekeeper.model.expression.validation import (
    infer_query_domain,
    analyze_expressions,
)
from rangekeeper.model.formulation import Formulation
from rangekeeper.model.formulation.preparation import prepare_formulations
from rangekeeper.model.scope import build_scope
from rangekeeper.specification import Specification, SpecificationRecord
from rangekeeper.specification.validation import prepare


class Resolver:
    def __init__(self, model, *specifications):
        self.model = model
        self.specifications = {item.id: item for item in specifications}
        self.model_calls = []

    def load_model(self, identity):
        self.model_calls.append(identity)
        assert identity == self.model.id
        return self.model

    def load_specification(self, identity):
        return self.specifications[identity]


def fixture_model():
    path = Path(__file__).resolve().parents[2] / "schema/examples/model.yaml"
    return Model.from_data(yaml.safe_load(path.read_text()))


def specification(**fields):
    return Specification(
        SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="0.7.0"), **fields
        )
    )


def test_index_retains_paths_and_rejects_duplicate_catalogue_identity():
    identity = uuid4()
    definition = Measure(id=identity, code="length", name="Length", units="m")
    definitions = Definitions(measures=(definition,))
    index = RecordIndex.build(definitions)
    assert index.paths[identity] == "/measures/0"
    assert index.get(identity, Measure) == definition
    with pytest.raises(IdentityConflictError):
        measure(Definitions(measures=(definition, definition)), uuid4())


def test_schema_mapping_locations_escape_json_pointer_segments():
    from rangekeeper.model.provenance import Location

    location = Location.from_data(
        dict(source=str(uuid4()), address={"a/b~c": {"value": "cell"}})
    )
    located = tuple(walk_data("Location", location.to_data()))
    assert located[-1] == ({"value": "cell"}, "/address/a~1b~0c")


def test_assembly_lookup_is_typed_and_preserves_entity_lookup():
    from rangekeeper.model import System

    ordinary, assembly = Entity(id=uuid4()), Assembly(id=uuid4())
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
        system=System(entities=(ordinary,), assemblies=(assembly,)),
    )
    assert model.assembly(assembly.id) == model.entity(assembly.id)
    with pytest.raises(ReferenceTypeError):
        model.assembly(ordinary.id)


@pytest.mark.parametrize(
    "kinds, expected",
    [
        (("measurement",), "measurement"),
        (("property",), "property"),
        (("flow",), "flow"),
        (("measurement", "property"), "unknown"),
        ((), "unknown"),
    ],
)
def test_query_domain_uses_all_statically_eligible_value_kinds(kinds, expected):
    identity, measure_id = str(uuid4()), str(uuid4())
    values = [
        dict(
            id=str(uuid4()),
            key="floor_area",
            kind=kind,
            **({"measure": measure_id} if kind != "property" else {}),
        )
        for kind in kinds
    ]
    scope = build_scope(
        dict(
            definitions=dict(measures=[dict(id=measure_id, units="m^2")]),
            entities=[dict(id=identity, characteristics=dict(values=values))],
        )
    )
    query = dict(
        starting_at=identity,
        projection=dict(kind="value", key="floor_area"),
        duplicates="distinct",
    )
    result = infer_query_domain(query, scope=scope)
    assert result["item_domain"]["kind"] == expected
    required = dict(
        kind="collection", item_domain=dict(kind="measurement", measure=measure_id)
    )
    comparison = compare_domains(result, required, scope=scope)
    assert comparison is (
        DomainCompatibility.COMPATIBLE
        if expected == "measurement"
        else (
            DomainCompatibility.UNPROVEN
            if expected == "unknown"
            else DomainCompatibility.INCOMPATIBLE
        )
    )


def test_unknown_units_do_not_prove_dimensionless_arguments():
    assert (
        compare_domains(
            dict(kind="quantity"), dict(kind="number"), scope=build_scope({})
        )
        is DomainCompatibility.UNPROVEN
    )


@pytest.mark.parametrize(
    "kinds",
    [("measurement",), ("property",), ("flow",), ("measurement", "property"), ()],
)
@pytest.mark.parametrize(
    "consumer", ["function", "predicate", "objective", "reporting"]
)
def test_query_domain_acceptance_at_actual_consumer_boundaries(kinds, consumer):
    from rangekeeper.errors import ValidationError

    measure, entity, function = (str(uuid4()) for _ in range(3))
    values = [
        dict(
            id=str(uuid4()),
            key="area",
            kind=kind,
            **({"measure": measure} if kind != "property" else {}),
        )
        for kind in kinds
    ]
    query = dict(
        id=str(uuid4()),
        kind="query",
        query=dict(
            starting_at=entity,
            projection=dict(
                kind="value", key="area", cardinality="one", missing="error"
            ),
            duplicates="distinct",
        ),
    )
    expression = (
        dict(
            id=str(uuid4()),
            kind="call",
            call=dict(function=function, arguments=[query]),
        )
        if consumer == "function"
        else query
    )
    formulation = dict(id=str(uuid4()), expressions=[expression])
    if consumer == "predicate":
        formulation["constraints"] = [dict(id=str(uuid4()), predicate=expression["id"])]
    data = dict(
        metadata=dict(id=str(uuid4()), schema_version="0.7.0"),
        definitions=dict(
            measures=[dict(id=measure, code="area", name="Area", units="m^2")],
            functions=[
                dict(
                    id=function,
                    code="sum",
                    name="Sum",
                    version="1",
                    semantics="Sum declared measurements.",
                    unit_rule="Preserve area units.",
                    empty_collection="error",
                    parameters=[
                        dict(
                            name="values",
                            kind="positional_or_named",
                            required=True,
                            domain=dict(
                                kind="collection",
                                item_domain=dict(kind="measurement", measure=measure),
                            ),
                        )
                    ],
                    result=dict(kind="quantity", units="m^2"),
                )
            ],
        ),
        system=dict(
            entities=[dict(id=entity, characteristics=dict(values=values[:1]))]
            + [
                dict(id=str(uuid4()), characteristics=dict(values=[value]))
                for value in values[1:]
            ],
            formulations=[formulation],
        ),
    )
    if consumer == "predicate" or consumer == "function" and kinds != ("measurement",):
        with pytest.raises(ValidationError) as failure:
            Model.from_data(data)
        assert (
            "Boolean" in str(failure.value)
            if consumer == "predicate"
            else "argument domain" in str(failure.value)
        )
        return
    model = Model.from_data(data)
    resolver = Resolver(model)
    if consumer == "objective":
        from rangekeeper.specification import Objective, ObjectiveKind

        request = specification(
            model=model.id,
            objectives=(
                Objective(
                    sense=ObjectiveKind.MINIMIZE, expression=UUID(expression["id"])
                ),
            ),
        )
        report = request.compose(resolver=resolver).validate(resolver=resolver)
        assert not report.valid
        assert "scalar numerical" in report.issues[0].message
    else:
        report = (
            specification(model=model.id)
            .compose(resolver=resolver)
            .validate(resolver=resolver)
        )
        assert report.valid, report.issues


def test_formulation_iterable_is_consumed_once_and_analysis_is_reused():
    identity = str(uuid4())
    expression = dict(id=identity, kind="boolean", boolean=True)
    additions = (
        dict(
            id=str(uuid4()),
            expressions=[expression],
            constraints=[dict(id=str(uuid4()), predicate=identity)],
        )
        for _ in range(1)
    )
    scope, analysis, located = prepare_formulations({}, additions)
    assert analysis.nodes_by_id[UUID(identity)] is expression
    assert analysis.domains_by_id[UUID(identity)] == dict(kind="boolean")
    assert len(located) == 1
    with pytest.raises(TypeError):
        analysis.domains_by_id[UUID(identity)] = {}


def test_existing_composition_is_not_recomposed_and_keeps_the_exact_model(monkeypatch):
    model = fixture_model()
    root = specification(model=model.id)
    resolver = Resolver(model)
    composition = root.compose(resolver=resolver)
    import rangekeeper.specification.validation as validation

    def forbidden(*args, **kwargs):
        raise AssertionError("validation must not recompose a supplied Composition")

    monkeypatch.setattr(validation, "compose_specification", forbidden)
    result = prepare(composition, resolver=resolver)
    assert result.model is model
    assert resolver.model_calls == [model.id]
    # Missing roles are a later semantic error, after the exact pin has resolved.
    assert not result.report.valid and result.scope is None
    assert result.composition.model_id == model.id


def test_composed_constraint_failure_reports_original_document_and_path():
    model = Model.create(metadata=Metadata(id=uuid4(), schema_version="0.7.0"))
    expression = Expression(
        id=uuid4(),
        kind=ExpressionKind.QUANTITY,
        quantity=Quantity(magnitude=2, units="dimensionless"),
    )
    child = Formulation(
        id=uuid4(),
        expressions=(expression,),
        constraints=(Constraint(id=uuid4(), predicate=expression.id),),
    )
    included = specification(
        formulations=(Formulation(id=uuid4(), formulations=(child,)),)
    )
    root = specification(model=model.id, includes=(included.id,))
    resolver = Resolver(model, included)
    report = root.compose(resolver=resolver).validate(resolver=resolver)
    assert len(report.issues) == 1
    issue = report.issues[0]
    assert issue.document_id == included.id
    assert issue.path == "/formulations/0/formulations/0/constraints/0/predicate"


@pytest.mark.parametrize(
    "left,right",
    [(0, False), (0, 0.0), (0.0, -0.0), ([1, 2], [2, 1]), ({}, {"x": None})],
)
def test_exact_preserved_content_comparison_retains_scalar_and_order_distinctions(
    left, right
):
    assert not exact_equal(left, right)
    assert not exact_equal(right, left)


def test_nested_expression_paths_and_analysis_keys_remain_original():
    leaf = dict(id=str(uuid4()), kind="boolean", boolean=True)
    parent = dict(id=str(uuid4()), kind="unary", operator="logical_not", operand=leaf)
    analysis = analyze_expressions(
        (parent,), scope=build_scope({}), locations=("/formulations/2/expressions/4",)
    )
    assert set(analysis.nodes_by_id) == {UUID(leaf["id"]), UUID(parent["id"])}
    assert (
        analysis.paths_by_id[UUID(leaf["id"])]
        == "/formulations/2/expressions/4/operand"
    )
    leaf["kind"] = "reference"
    leaf["target"] = dict(target=str(uuid4()))
    with pytest.raises(ContractError) as error:
        analyze_expressions(
            (parent,),
            scope=build_scope({}),
            locations=("/formulations/2/expressions/4",),
        )
    assert error.value.path == "/formulations/2/expressions/4/operand"


def test_diff_reuses_existing_record_indexes_without_export(monkeypatch):
    from rangekeeper.model import Update
    from rangekeeper.model.diff import between

    model = fixture_model()
    changed = model.revise(
        Update(
            metadata=model.metadata.replace(
                id=uuid4(), previous=model.id, name="renamed"
            )
        )
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("comparison rebuilt or exported an already checked Model")

    monkeypatch.setattr(RecordIndex, "build", forbidden)
    monkeypatch.setattr(Model, "to_data", forbidden)
    assert between(model, changed).changes


def test_model_raw_preparation_checks_structure_once_and_preserves_history_errors(
    monkeypatch,
):
    from rangekeeper.model.validation import validate
    import rangekeeper._schema.validation as structure

    original = structure.validate
    calls = []

    def counted(kind, value):
        calls.append(kind)
        return original(kind, value)

    monkeypatch.setattr(structure, "validate", counted)
    assert validate(dict(metadata=dict(id=str(uuid4()), schema_version="0.7.0"))).valid
    assert calls.count("Model") == 1
    report = validate({"metadata": {}}, history=[{"schema_version": "0.7.0"}])
    assert any(issue.path.startswith("/history/0") for issue in report.issues)


def test_preparation_rechecks_model_units_under_a_different_caller_context():
    from rangekeeper.model import System, Value, ValueKind
    from rangekeeper.units import UnitSystem

    currency = Measure(id=uuid4(), code="money", name="Money", units="USD")
    value = Value(
        id=uuid4(),
        key="money",
        kind=ValueKind.MEASUREMENT,
        measure=currency.id,
        quantity=Quantity(magnitude=2, units="USD"),
    )
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
        definitions=Definitions(measures=(currency,)),
        system=System(formulations=(Formulation(id=uuid4(), values=(value,)),)),
    )
    resolver = Resolver(model)
    composition = specification(model=model.id).compose(resolver=resolver)
    result = prepare(composition, resolver=resolver, units=UnitSystem(currencies=()))
    assert not result.report.valid and result.scope is None
    assert result.model is model
    assert all(issue.document_id == model.id for issue in result.report.issues)
    assert all(issue.path.endswith("/units") for issue in result.report.issues)


def test_run_child_diagnostics_identify_the_child_and_report_field():
    from rangekeeper.run.validation import validate_records

    examples = Path(__file__).resolve().parents[2] / "schema/examples"

    def catalogue(pattern):
        records = [yaml.safe_load(path.read_text()) for path in examples.glob(pattern)]
        return {record["metadata"]["id"]: record for record in records}

    runs = catalogue("run-*.yaml")
    root = yaml.safe_load((examples / "run-batch.yaml").read_text())
    child = runs[root["spawns"][0]]
    child["report"]["runtime"].setdefault("settings", {})["iteration_limit"] = 999
    result = validate_records(
        root,
        runs=runs,
        specifications=catalogue("specification-*.yaml"),
        models=catalogue("model*.yaml"),
    )
    assert not result.valid
    assert result.issues[0].document_id == UUID(child["metadata"]["id"])
    assert result.issues[0].path == "/report"


@pytest.mark.parametrize("published", [False, True])
def test_supplied_units_reach_policy_runtime_and_stored_run_outcomes(published):
    """Exercise real converted comparisons through both public entry points."""
    from copy import deepcopy
    from rangekeeper.io import MemoryStore
    from rangekeeper.policies import Policy, evaluate
    from rangekeeper.run import Run, validate
    from rangekeeper.units import UnitSystem

    conversions = []

    class TrackingUnits(UnitSystem):
        def convert(self, quantity, *, to):
            conversions.append((self, quantity.units, to))
            return super().convert(quantity, to=to)

    units = TrackingUnits(currencies=())
    measure, observed, control, decision, rule = (str(uuid4()) for _ in range(5))
    at = "2027-01-01"
    reference = dict(target=control)
    amount = dict(magnitude=1, units="m")
    data = dict(
        metadata=dict(id=str(uuid4()), schema_version="0.7.0"),
        definitions=dict(
            measures=[dict(id=measure, code="length", name="Length", units="m")]
        ),
        system=dict(
            formulations=[
                dict(
                    id=str(uuid4()),
                    values=[
                        dict(
                            id=observed,
                            key="observed",
                            kind="measurement",
                            measure=measure,
                            quantity=dict(magnitude=2, units="m"),
                        ),
                        dict(
                            id=control,
                            key="control",
                            kind="measurement",
                            measure=measure,
                        ),
                    ],
                )
            ]
        ),
    )
    action = dict(kind="assign", target=reference, quantity=amount)
    policy = Policy.from_data(
        dict(
            id=str(uuid4()),
            targets=[reference],
            decisions=[
                dict(
                    id=decision,
                    at=at,
                    observations=[
                        dict(
                            name="observed",
                            target=dict(target=observed),
                            available_at=at,
                        )
                    ],
                    rules=[
                        dict(
                            id=rule,
                            condition=dict(
                                id=str(uuid4()),
                                kind="binary",
                                operator="greater_than",
                                operands=[
                                    dict(
                                        id=str(uuid4()),
                                        kind="reference",
                                        target=dict(target=observed),
                                    ),
                                    dict(
                                        id=str(uuid4()),
                                        kind="quantity",
                                        quantity=dict(magnitude=100, units="cm"),
                                    ),
                                ],
                            ),
                            actions=[action],
                        )
                    ],
                    fallback=[action],
                )
            ],
        )
    )
    model = Model.from_data(data)
    result = evaluate(policy, model=model, units=units)
    assert result.outcomes[0].rule == UUID(rule)
    assert len(conversions) >= 2
    assert all(
        context is units and source == "cm" and target == "m"
        for context, source, target in conversions
    )
    spec = specification(model=model.id, policy=policy)
    store = MemoryStore()
    for document in (model, spec):
        store.put(document)
    raw = dict(
        metadata=dict(id=str(uuid4()), schema_version="0.4.0"),
        specification=str(spec.id),
        report=dict(
            status=dict(
                completion="completed", solution="feasible" if published else "unknown"
            ),
            runtime=dict(
                implementations=[
                    dict(kind="evaluator", name="unit-context-test", version="1")
                ]
            ),
            outcomes=[item.to_data() for item in result.outcomes],
        ),
    )
    if published:
        output = deepcopy(data)
        output["metadata"] = dict(
            id=str(uuid4()), previous=str(model.id), schema_version="0.7.0"
        )
        output["system"]["formulations"][0]["values"][1]["quantity"] = amount
        output_model = Model.from_data(output)
        store.put(output_model)
        raw["outputs"] = [str(output_model.id)]
    else:
        raw["report"]["diagnostics"] = [
            dict(
                severity="info",
                code="trace_only",
                message="Policy evaluated without publication",
            )
        ]
    run = Run.from_data(raw)
    conversions.clear()
    report = validate(run, resolver=store, units=units)
    assert report.valid, report.issues
    assert conversions and all(context is units for context, _, _ in conversions)
