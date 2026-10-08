"""Design-derived financial declarations used by the two design walkthroughs.

Source identity, topology and provenance remain in the input Model. Authoring
adds generated Values and finite equations; it does not solve, fetch or store.
The annual amounts use AUD explicitly. Rates described as per-area/per-volume
are amounts per payment, not rates with an implicit time dimension.
"""

from rangekeeper.model import ValueKind

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, cast
from uuid import UUID, uuid4, uuid5

from rangekeeper.model import (
    Model,
    Definitions,
    System,
    Update,
    Metadata,
    Measure,
    Value,
    Quantity,
    Formulation,
)
from rangekeeper.model.characteristics import value as local_value
from rangekeeper.model.content import decode, encode
from rangekeeper.model.definitions import find_classifications
from rangekeeper.model.flux import Flow
from rangekeeper.model.duration import make_periods

from rangekeeper.model.expression import Reference
from rangekeeper.model.formulation import declare
from rangekeeper.model.duration import Frequency, PeriodTiming
from rangekeeper.model.expression.authoring import (
    reference,
    literal,
    equal,
    add,
    multiply,
    divide,
    power,
    sum as expression_sum,
)
from rangekeeper.specification import Specification
from rangekeeper.specification.targets import unknown_flow
from rangekeeper.schema.records import Assignment, Specification as SpecificationRecord

# Reviewed teaching assumptions from the original design walkthrough.
EFFICIENCY = dict(hotel=0.8, retail=0.675, residential=0.75, parking=0.9)
RENT = dict(hotel=750, retail=1000, residential=600, parking=0)
GROWTH = dict(hotel=0.035, retail=0.075, residential=0.055, parking=0)
VACANCY = dict(hotel=0.025, retail=0.075, residential=0.015, parking=0)
FLOOR_OPEX = dict(hotel=-175, retail=-225, residential=-125, parking=-65)
FACADE_OPEX = dict(hotel=-50, retail=-100, residential=-50, parking=-25)
FLOOR_CAPEX = dict(hotel=-100, retail=-150, residential=-75, parking=-50)
_COMPONENTS = (
    "pgi",
    "vacancy",
    "egi",
    "floor_opex",
    "facade_opex",
    "opex",
    "floor_capex",
    "utility_capex",
    "capex",
    "noi",
    "nacf",
)
_PREFIX = "Design financial / "


def classification_id(model: Model, code: str) -> UUID:
    """Resolve one authoring code to UUID; absent or ambiguous codes fail."""
    matches = find_classifications(model.definitions, code=code)
    if len(matches) != 1:
        raise ValueError(f"expected exactly one classification for {code!r}")
    return matches[0].id


def select_contributors(model: Model, *, root: UUID) -> tuple[UUID, ...]:
    """Select unique floor and utility contributors reachable by spatial edges.

    Shared membership and repeated paths do not duplicate contribution. Cycles
    and unrelated membership do not expand the reviewed calculation scope.
    """
    model.entity(root)
    spatial = classification_id(model, "spatiallyContains")
    kinds = {classification_id(model, "floor"), classification_id(model, "utilities")}
    assert model.system is not None
    children: dict[UUID, list[UUID]] = {}
    for edge in model.system.relationships or ():
        if edge.classification == spatial:
            children.setdefault(edge.source, []).append(edge.target)
    seen, pending = set(), [root]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        pending.extend(children.get(current, ()))
    # Assemblies may share a utilities classification but are not cost inputs.
    entities = {e.id: e for e in model.system.entities or ()}
    return tuple(
        uid
        for uid in sorted(seen, key=str)
        if uid in entities and entities[uid].classification in kinds
    )


def _use(model: Model, owner: UUID) -> str:
    """Read the floor's explicit use or agreeing spatial-parent uses."""
    assert model.system is not None
    own = local_value(model.entity(owner).characteristics, "use")
    if own is not None:
        choices = [decode(own.content)] if own.content is not None else []
    else:
        spatial = classification_id(model, "spatiallyContains")
        parents = {
            e.source
            for e in model.system.relationships or ()
            if e.target == owner and e.classification == spatial
        }
        choices = []
        for parent in parents:
            item = local_value(model.entity(parent).characteristics, "use")
            if item is not None and item.content is not None:
                choices.append(decode(item.content))
    if (
        not choices
        or any(x != choices[0] for x in choices)
        or choices[0] not in EFFICIENCY
    ):
        raise ValueError(f"absent, conflicting or unsupported use for {owner}")
    return cast(str, choices[0])


def _source(model: Model, owner: UUID, key: str) -> Value:
    item = local_value(model.entity(owner).characteristics, key)
    if item is None or item.kind is not ValueKind.MEASUREMENT or item.quantity is None:
        raise ValueError(f"{owner}/{key} requires a resolved source measurement")
    return item


def values(model: Model, owner: UUID | None = None) -> dict[str, Value]:
    """Return a detached key index of immutable example Values for one owner."""
    assert model.system is not None
    name = _PREFIX + (str(owner) if owner else "aggregate")
    matches = [f for f in model.system.formulations or () if f.name == name]
    if len(matches) != 1:
        raise ValueError(
            f'expected one financial declaration for {owner or "aggregate"}'
        )
    return {v.key: v for v in matches[0].values or ()}


def author(
    model: Model,
    *,
    root: UUID,
    utility_kinds: Mapping[UUID, str],
    contributors: Sequence[UUID] | None = None,
) -> Model:
    """Add parameters and unresolved shapes; return a new revision.

    Utility interpretation is an explicit UUID-to-plant/cores mapping. There is
    no name heuristic at runtime. The reviewed horizon is 2001--2010 plus 2011
    income for reversion. Existing equations are rejected to avoid accidentally
    solving unrelated declarations. No source Value or historical Claim changes.
    """
    if model.system is None or model.system.formulations:
        raise ValueError("design authoring requires a source Model without equations")
    selected = select_contributors(model, root=root)
    if contributors is not None:
        requested = tuple(dict.fromkeys(contributors))
        if not set(requested) <= set(selected):
            raise ValueError("contributors must belong to the declared spatial scope")
        selected = requested
    if not selected:
        raise ValueError("design requires at least one contributor")
    floor_kind = classification_id(model, "floor")
    utilities = {
        uid for uid in selected if model.entity(uid).classification != floor_kind
    }
    if set(utility_kinds) != utilities or set(utility_kinds.values()) - {
        "plant",
        "cores",
    }:
        raise ValueError(
            "provide exactly the selected utility identities and their reviewed kinds"
        )
    if len(selected) != len(set(selected)):
        raise ValueError("duplicate contributor")
    periods = make_periods(date(2001, 1, 1), frequency=Frequency.YEAR, count=11)
    namespace = uuid4()
    measures = {}
    for key, unit in [
        ("money", "AUD"),
        ("ratio", "dimensionless"),
        ("area", "meter ** 2"),
        ("rent", "AUD / meter ** 2"),
        ("utility_cost", "AUD / meter ** 3"),
    ]:
        measures[unit] = Measure(
            id=uuid5(namespace, key), code="design_" + key, name=key, units=unit
        )

    def amount(owner, key, unit, magnitude=None):
        options = (
            {}
            if magnitude is None
            else {"quantity": Quantity(magnitude=magnitude, units=unit)}
        )
        return Value(
            id=uuid5(owner, key),
            key=key,
            kind=ValueKind.MEASUREMENT,
            measure=measures[unit].id,
            **options,
        )

    def flow(owner, key, *, count=11):
        return Value(
            id=uuid5(owner, key),
            key=key,
            kind=ValueKind.FLOW,
            measure=measures["AUD"].id,
            flow=Flow.from_periods(
                periods[:count],
                (None,) * count,
                units="AUD",
                keys=tuple(f"y{i + 1}" for i in range(count)),
                dates=tuple(
                    p.resolve(timing=PeriodTiming.LAST) for p in periods[:count]
                ),
            ),
        )

    declarations = []
    for uid in selected:
        owner = uuid5(namespace, str(uid))
        items = []
        if model.entity(uid).classification == floor_kind:
            use = _use(model, uid)
            for key, unit, magnitude in [
                ("efficiency", "dimensionless", EFFICIENCY[use]),
                ("rent", "AUD / meter ** 2", RENT[use]),
                ("growth", "dimensionless", GROWTH[use]),
                ("vacancy_rate", "dimensionless", VACANCY[use]),
                ("floor_cost", "AUD / meter ** 2", FLOOR_OPEX[use]),
                ("facade_cost", "AUD / meter ** 2", FACADE_OPEX[use]),
                ("floor_capital", "AUD / meter ** 2", FLOOR_CAPEX[use]),
            ]:
                items.append(amount(owner, key, unit, magnitude))
            items.append(amount(owner, "facade_area", "meter ** 2"))
            for key in ("gfa", "perimeter", "ftf"):
                _source(model, uid, key)
        else:
            _source(model, uid, "volume")
            items.append(
                amount(
                    owner,
                    "utility_cost",
                    "AUD / meter ** 3",
                    -1000 if utility_kinds[uid] == "plant" else -100,
                )
            )
        items.extend(
            amount(owner, key, "dimensionless", 0.035)
            for key in ("opex_growth", "capex_growth")
        )
        items.extend(flow(owner, key) for key in _COMPONENTS)
        declarations.append(
            Formulation(id=owner, name=_PREFIX + str(uid), values=tuple(items))
        )
    owner = uuid5(namespace, "aggregate")
    items = [
        Value(
            id=uuid5(owner, "contributors"),
            key="contributors",
            kind=ValueKind.PROPERTY,
            content=encode(tuple(selected)),
        )
    ]
    items.extend(flow(owner, key) for key in _COMPONENTS)
    items.extend(
        flow(owner, key, count=10) for key in ("reversion", "total", "discounted")
    )
    items.extend(
        [
            amount(owner, "cap_rate", "dimensionless", 0.05),
            amount(owner, "discount_rate", "dimensionless", 0.07),
            amount(owner, "pv", "AUD"),
        ]
    )
    declarations.append(
        Formulation(id=owner, name=_PREFIX + "aggregate", values=tuple(items))
    )
    system = cast(dict[str, Any], model.system.to_data())
    system["formulations"] = [f.to_data() for f in declarations]
    assert model.definitions is not None
    definitions = cast(dict[str, Any], model.definitions.to_data())
    definitions.setdefault("measures", []).extend(
        m.to_data() for m in measures.values()
    )
    return model.revise(
        Update(
            system=System.from_data(system),
            definitions=Definitions.from_data(definitions),
        )
    )


def formulate(model: Model) -> Model:
    """Declare component equations, identity-deduplicated sums and discounted PV.

    Capital payments fall at 2005 and 2010 year ends. Their growth exponents are
    zero and one, matching the old five-year projection. Reversion is 2011 NACF
    divided by the cap rate and received in 2010; it is deliberately not NOI.
    Every source magnitude remains an explicit solve assignment.
    """
    assert model.system is not None
    aggregate = values(model)
    contributors = _contributors(model)
    equations = []
    bound = set()

    def r(item, key=None):
        bound.add(item.id)
        return reference(
            Reference(target=item.id)
            if key is None
            else Reference(
                target=next(m.id for m in item.flow.movements if m.key == key)
            )
        )

    def put(item, key, rhs):
        equations.append(
            (str(item.id) + "/" + (key or "scalar"), equal(r(item, key), rhs))
        )

    floor_kind = classification_id(model, "floor")
    for uid in contributors:
        v = values(model, uid)
        floor = model.entity(uid).classification == floor_kind
        if floor:
            area = _source(model, uid, "gfa")
            put(
                v["facade_area"],
                None,
                multiply(
                    r(_source(model, uid, "perimeter")), r(_source(model, uid, "ftf"))
                ),
            )
        for i in range(11):
            key = f"y{i+1}"
            growth = power(add(literal(1), r(v["opex_growth"])), literal(i))
            capital = (
                power(add(literal(1), r(v["capex_growth"])), literal((i + 1) // 5 - 1))
                if (i + 1) % 5 == 0
                else None
            )
            if floor:
                put(
                    v["pgi"],
                    key,
                    multiply(
                        multiply(multiply(r(area), r(v["efficiency"])), r(v["rent"])),
                        power(add(literal(1), r(v["growth"])), literal(i)),
                    ),
                )
                put(
                    v["vacancy"],
                    key,
                    multiply(
                        multiply(literal(-1), r(v["vacancy_rate"])), r(v["pgi"], key)
                    ),
                )
                put(
                    v["floor_opex"],
                    key,
                    multiply(multiply(r(area), r(v["floor_cost"])), growth),
                )
                put(
                    v["facade_opex"],
                    key,
                    multiply(
                        multiply(r(v["facade_area"]), r(v["facade_cost"])), growth
                    ),
                )
                put(
                    v["floor_capex"],
                    key,
                    (
                        multiply(multiply(r(area), r(v["floor_capital"])), capital)
                        if capital
                        else literal(0, "AUD")
                    ),
                )
                put(v["utility_capex"], key, literal(0, "AUD"))
            else:
                for name in (
                    "pgi",
                    "vacancy",
                    "floor_opex",
                    "facade_opex",
                    "floor_capex",
                ):
                    put(v[name], key, literal(0, "AUD"))
                put(
                    v["utility_capex"],
                    key,
                    (
                        multiply(
                            multiply(
                                r(_source(model, uid, "volume")), r(v["utility_cost"])
                            ),
                            capital,
                        )
                        if capital
                        else literal(0, "AUD")
                    ),
                )
            for name, left, right in [
                ("egi", "pgi", "vacancy"),
                ("opex", "floor_opex", "facade_opex"),
                ("capex", "floor_capex", "utility_capex"),
                ("noi", "egi", "opex"),
                ("nacf", "noi", "capex"),
            ]:
                put(v[name], key, add(r(v[left], key), r(v[right], key)))
    for name in _COMPONENTS:
        for i in range(11):
            key = f"y{i+1}"
            put(
                aggregate[name],
                key,
                expression_sum(
                    [r(values(model, uid)[name], key) for uid in contributors]
                ),
            )
    for i in range(10):
        key = f"y{i+1}"
        put(
            aggregate["reversion"],
            key,
            (
                divide(r(aggregate["nacf"], "y11"), r(aggregate["cap_rate"]))
                if i == 9
                else literal(0, "AUD")
            ),
        )
        put(
            aggregate["total"],
            key,
            add(r(aggregate["nacf"], key), r(aggregate["reversion"], key)),
        )
        put(
            aggregate["discounted"],
            key,
            divide(
                r(aggregate["total"], key),
                power(add(literal(1), r(aggregate["discount_rate"])), literal(i + 1)),
            ),
        )
    put(
        aggregate["pv"],
        None,
        expression_sum([r(aggregate["discounted"], f"y{i+1}") for i in range(10)]),
    )
    declaration = declare(
        id=uuid4(),
        name="Design equations",
        equations=equations,
        values=sorted(bound, key=str),
    )
    system = cast(dict[str, Any], model.system.to_data())
    system["formulations"].append(declaration.to_data())
    return model.revise(Update(system=System.from_data(system)))


def specify(model: Model) -> Specification:
    """Assign declared inputs and source measurements, selecting all result symbols.

    Unresolved source measurements fail during authoring. Recorded result values
    are never reused implicitly. This operation neither solves nor writes files.
    """
    assert model.system is not None
    inputs: dict[UUID, Value] = {}
    unknowns: list = []
    aggregate = values(model)
    for uid in _contributors(model):
        for key in ("gfa", "perimeter", "ftf", "volume"):
            item = local_value(model.entity(uid).characteristics, key)
            if item is not None and item.quantity is not None:
                inputs[item.id] = item
    for declaration in model.system.formulations or ():
        if not (declaration.name or "").startswith(_PREFIX):
            continue
        for item in declaration.values or ():
            if item.kind is ValueKind.FLOW:
                unknowns.extend(unknown_flow(model, item.id))
            elif item.kind is ValueKind.MEASUREMENT:
                if item.key in ("pv", "facade_area"):
                    unknowns.append(Reference(target=item.id))
                elif item.quantity is not None:
                    inputs[item.id] = item
    return Specification(
        SpecificationRecord(
            metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
            model=model.id,
            assignments=tuple(
                Assignment(
                    target=Reference(target=v.id), quantity=cast(Quantity, v.quantity)
                )
                for v in inputs.values()
            ),
            unknowns=tuple(unknowns),
        )
    )


def fixture() -> Model:
    """Construct a small public synthetic design; no private service data is copied."""
    from rangekeeper.migration.speckle import MappingSpec, convert_speckle

    namespace = UUID("bce1e752-588a-4c52-a22a-43d4f87cfc9b")
    ids = {
        key: str(uuid5(namespace, key))
        for key in ("property", "space", "floor", "cores")
    }
    raw = []
    for key, kind, fields, children in [
        ("property", "property", {}, ["space", "cores"]),
        ("space", "space", {"use": "hotel"}, ["floor"]),
        ("floor", "floor", {"gfa": 1000, "perimeter": 120, "ftf": 3, "number": 1}, []),
        ("cores", "utilities", {"volume": 20, "use": "cores"}, []),
    ]:
        fields = cast(dict[str, Any], fields)
        item: dict[str, Any] = {
            "entityId": ids[key],
            "name": key,
            "type": kind,
            **fields,
        }
        item["speckle_type"] = (
            "Objects.Rangekeeper.Assembly" if children else "Objects.Rangekeeper.Entity"
        )
        if children:
            item["relationships"] = [
                {"source": None, "target": ids[c], "type": "spatiallyContains"}
                for c in children
            ]
        raw.append(item)
    result = convert_speckle(
        {"objects": raw},
        mapping=MappingSpec(
            classifications=("property", "space", "floor", "utilities"),
            relationships=("spatiallyContains",),
            measurements={
                "gfa": "meter ** 2",
                "perimeter": "meter",
                "ftf": "meter",
                "volume": "meter ** 3",
            },
            properties=("use", "number"),
        ),
        revision_id=namespace,
    )
    if result.model is None:
        raise ValueError(result.issues)
    return result.model


def _contributors(model: Model) -> tuple[UUID, ...]:
    content = values(model)["contributors"].content
    if content is None:
        raise ValueError("contributors must be declared")
    result = decode(content)
    if not isinstance(result, tuple) or not all(
        isinstance(uid, UUID) for uid in result
    ):
        raise ValueError("contributors must be an ordered UUID tuple")
    return result
