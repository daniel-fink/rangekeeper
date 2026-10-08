"""Revision-local mathematical declarations and explicit recorded scalar access."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID
from rangekeeper.shared.validation import require


@dataclass(frozen=True)
class Scope:
    """Lookup tables shared by bounded mathematical checks.

    Top-level tables and the identity set are read-only. Record values are borrowed
    from the caller's prepared envelope, preserving identity; this is a short-lived
    analysis context, not an immutable published document. Checks never mutate it.
    """

    measures: Mapping[UUID, dict]
    entities: Mapping[UUID, dict]
    classifications: Mapping[UUID, dict]
    values: Mapping[UUID, dict]
    targets: Mapping[UUID, tuple[dict, dict | None]]
    domains: Mapping[UUID, dict]
    functions: Mapping[UUID, dict]
    identities: frozenset[UUID]


def build_scope(document, local_values=()) -> Scope:
    """Index schema-valid declarations with UUID keys, without evaluating content.

    Content checks and Function signatures are separate preparation stages. The
    raw mapping boundary converts UUID wire values once into lookup keys.
    """
    measures: dict[UUID, dict] = {}
    entities: dict[UUID, dict] = {}
    classifications: dict[UUID, dict] = {}
    values: dict[UUID, dict] = {}
    targets: dict[UUID, tuple[dict, dict | None]] = {}
    domains: dict[UUID, dict] = {}
    functions: dict[UUID, dict] = {}
    identities: set[UUID] = set()

    def add(collection, record):
        identity = UUID(record["id"])
        require(identity not in identities, f"duplicate identity: {identity}")
        identities.add(identity)
        collection[identity] = record

    for measure in document.get("definitions", {}).get("measures", []):
        add(measures, measure)
    for taxonomy in document.get("definitions", {}).get("taxonomies", []):
        require(UUID(taxonomy["id"]) not in identities, "duplicate taxonomy identity")
        identities.add(UUID(taxonomy["id"]))
        for classification in taxonomy["classifications"]:
            add(classifications, classification)

    def add_value(value):
        add(values, value)
        targets[UUID(value["id"])] = (value, None)
        domains[UUID(value["id"])] = dict(kind=value["kind"])
        if value.get("measure") is not None:
            domains[UUID(value["id"])]["measure"] = value["measure"]
        for movement in (value.get("flow") or {}).get("movements") or ():
            identity = UUID(movement["id"])
            require(identity not in identities, f"duplicate identity: {identity}")
            identities.add(identity)
            targets[identity] = (value, movement)

    system = (document.get("system") or {}) if "metadata" in document else document
    for entity in (*(system.get("entities") or ()), *(system.get("assemblies") or ())):
        add(entities, entity)
        for value in entity.get("characteristics", {}).get("values", []):
            add_value(value)
    for value in local_values:
        add_value(value)
    codes = set()
    functions_source = (
        (document.get("definitions") or {}) if "metadata" in document else document
    )
    for function in functions_source.get("functions") or []:
        add(functions, function)
        require(function["code"] not in codes, "duplicate Function code")
        codes.add(function["code"])
    scope = Scope(
        measures=MappingProxyType(measures),
        entities=MappingProxyType(entities),
        classifications=MappingProxyType(classifications),
        values=MappingProxyType(values),
        targets=MappingProxyType(targets),
        domains=MappingProxyType(domains),
        functions=MappingProxyType(functions),
        identities=frozenset(identities),
    )
    return scope


def reference_key(reference: dict) -> UUID:
    """Return the declaration UUID used as the private numerical symbol token."""
    return UUID(reference["target"])


def resolve_reference(reference: dict, targets):
    """Return the owning Value and optional Movement from the scope's target index."""
    identity = reference_key(reference)
    require(identity in targets, "unknown Value or Movement reference")
    return targets[identity]


def _scalar_units(value, movement, measure) -> str:
    if movement is not None:
        return value["flow"]["units"]
    require(
        value.get("kind") == "measurement",
        "numerical roles require a scalar measurement or Movement",
    )
    return measure(UUID(value["measure"]))["units"]


def numerical_units(reference: dict, targets, measures) -> str:
    """Resolve once, then check scalar eligibility and declared units."""
    value, movement = resolve_reference(reference, targets)
    return _scalar_units(value, movement, measures.__getitem__)


def recorded_quantity(reference: dict, targets, measures):
    """Read one resolved scalar; an absent amount remains unresolved and zero survives."""
    value, movement = resolve_reference(reference, targets)
    units = _scalar_units(value, movement, measures.__getitem__)
    if movement is None:
        return value.get("quantity")
    magnitude = movement.get("magnitude")
    return None if magnitude is None else dict(magnitude=magnitude, units=units)


def _model_target(model, target):
    from rangekeeper.schema.records import Movement

    record = model.resolve(target)
    if isinstance(record, Movement):
        return model.value(model.owner_of(record.id)), record
    return record, None


def target_value(model, target):
    """Return the owning Value with one target-resolution operation."""
    return _model_target(model, target)[0]


def _model_units(model, value, movement):
    from rangekeeper.schema.records import Measure

    return _scalar_units(
        value._data,
        movement._data if movement is not None else None,
        lambda identity: model._index.get(identity, Measure)._data,
    )


def target_units(model, target) -> str:
    """Read declared scalar units without inferring a solve role."""
    value, movement = _model_target(model, target)
    return _model_units(model, value, movement)


def recorded_scalar(model, target):
    """Read explicit scalar content using the same eligibility rules as validation."""
    from rangekeeper.schema.records import Quantity

    value, movement = _model_target(model, target)
    units = _model_units(model, value, movement)
    if movement is not None:
        return (
            None
            if movement.magnitude is None
            else Quantity(magnitude=movement.magnitude, units=units)
        )
    return value.quantity


def scope_for_model(model):
    """Prepare a validated immutable Model without export, reconstruction or analysis."""
    from rangekeeper.schema.records import Entity, Value

    definitions = model._record._data.get("definitions") or {}
    system = model._record._data.get("system") or {}
    entities = {
        identity
        for identity, record in model._index.records.items()
        if isinstance(record, Entity)
    }
    local_values = [
        record._data
        for identity, record in model._index.records.items()
        if isinstance(record, Value) and model._index.owners[identity] not in entities
    ]
    document = dict(
        definitions=definitions,
        functions=definitions.get("functions") or (),
        entities=system.get("entities") or (),
        assemblies=system.get("assemblies") or (),
    )
    return build_scope(document, local_values=local_values)


def validate_values(scope):
    """Check intrinsic Value content after declaration identities are indexed."""
    from rangekeeper.model.content import validate_content
    from rangekeeper.schema.records import Flow, PropertyContent

    for value in scope.values.values():
        kind = value["kind"]
        if kind in ("measurement", "flow"):
            require(
                value.get("measure") is not None
                and UUID(value["measure"]) in scope.measures,
                "unknown Value Measure",
            )
            forbidden = (
                ("flow", "content")
                if kind == "measurement"
                else ("quantity", "content")
            )
            require(
                all(value.get(field) is None for field in forbidden),
                "content incompatible with Value kind",
            )
            if kind == "flow" and value.get("flow") is not None:
                try:
                    Flow.from_data(value["flow"]).check()
                except (ValueError, TypeError) as error:
                    require(False, str(error))
        else:
            require(kind == "property", "unsupported Value kind")
            require(
                all(
                    value.get(field) is None
                    for field in ("measure", "quantity", "flow")
                ),
                "property Value cannot carry measurement content",
            )
            if value.get("content") is not None:
                try:
                    validate_content(PropertyContent.from_data(value["content"]))
                except (ValueError, TypeError) as error:
                    require(False, str(error))
