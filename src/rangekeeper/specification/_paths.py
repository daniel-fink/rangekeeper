"""Cases across market paths: series matching and their expansion (ADR-014, ADR-021).

``Specification.across`` makes one case for each path of a ``Paths`` document.
A case refers to its path by the UUID of the document and the path key, with
the Movements that each series fixes; it does not copy the amounts. The
composition of a case expands the path into assignments, from the document.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from rangekeeper.market.paths import Paths
from rangekeeper.quantity import Quantity
from rangekeeper.schema.enums import ValueKind
from rangekeeper.schema.records import PathCase, Reference, SeriesBinding, Value
from rangekeeper.shared import pointer
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, MissingReferenceError
from rangekeeper.shared.validation import require

if TYPE_CHECKING:
    from rangekeeper.model import Model

# A mapping from a Model key to a series name, or to the series of each member.
Series = Mapping[str, "str | Mapping[str, str]"]


@dataclass(frozen=True, kw_only=True)
class Match:
    """One path series and the Flow Value that it fixes."""

    series: str
    key: str
    value: Value


def match(*, model: "Model", paths: Paths, series: Series | None) -> tuple[Match, ...]:
    """Return the Flow Value that each series of ``paths`` fixes.

    A series fixes the Model value with its name, unless ``series`` maps a
    Model key to it. A series that fixes no value, a key of ``series`` that
    the paths lack, and a value with two series raise ContractError; its
    ``values`` list the path series and the Model keys.
    """
    mapping = dict(series or {})
    named = {}
    for key, name in mapping.items():
        if not isinstance(key, str):
            raise TypeError("series takes a mapping from Model keys to series names")
        if isinstance(name, Mapping):
            raise ContractError(
                f"series maps members of {key}, but {key} is not a keyed value; "
                "keyed values come with #284",
                **_context(model, paths, key=key),
            )
        if not isinstance(name, str):
            raise TypeError(f"the series of {key} must be the name of a path series")
        if name not in paths.names:
            raise ContractError(
                f"series names the path series {name} for {key}, but the paths "
                f"have only {', '.join(paths.names)}",
                code=Code.REFERENCE_MISSING,
                **_context(model, paths, key=key),
            )
        named[name] = key
    found = []
    for name in paths.names:
        key = named.get(name, name)
        found.append(Match(series=name, key=key, value=_value(model, paths, key=key)))
    _require_one_source(model, paths, found)
    return tuple(found)


def _value(model: "Model", paths: Paths, *, key: str) -> Value:
    """Return the Flow Value with a key, or raise ContractError with the keys."""
    try:
        value = model.value(key=key)
    except MissingReferenceError as error:
        raise ContractError(
            f"the path series {key} fixes no value of the Model; map it to a "
            "Model key with series=",
            code=Code.REFERENCE_MISSING,
            **_context(model, paths, key=key),
        ) from error
    if value.kind is not ValueKind.FLOW or value.flow is None:
        raise ContractError(
            f"{key} is not a Flow value, so a path series cannot fix it",
            **_context(model, paths, key=key),
        )
    return value


def _require_one_source(model: "Model", paths: Paths, found: list[Match]) -> None:
    """Raise ContractError when two series fix the same value."""
    seen: dict[UUID, str] = {}
    for item in found:
        if item.value.id in seen:
            raise ContractError(
                f"{item.key} takes two path series, {seen[item.value.id]} and "
                f"{item.series}",
                code=Code.UNIQUE,
                **_context(model, paths, key=item.key),
            )
        seen[item.value.id] = item.series


def _context(model: "Model", paths: Paths, *, key: str) -> dict[str, Any]:
    """Return the fields of an error about matching: the series and the Model keys."""
    keys = sorted(
        {
            model.key_of(record.id)
            for record in model._index.records.values()
            if isinstance(record, Value) and record.kind is ValueKind.FLOW
        }
    )
    return {
        "document_id": paths.id,
        "values": {"key": key, "series": list(paths.names), "model": keys},
    }


def bindings(
    *, model: "Model", paths: Paths, matches: Iterable[Match]
) -> tuple[SeriesBinding, ...]:
    """Return the binding of each series to the Movements of its value, by Period.

    Each Period of the paths fixes the Movement of the value over the same
    Period. Other Periods raise ContractError with ``ALIGNMENT_DIFFER``, and
    units that do not convert raise UnitError.
    """
    periods = [(period.start, period.end) for period in paths.periods]
    found = []
    for item in matches:
        flow = item.value.flow
        assert flow is not None
        by_period = {
            (m.period.start, m.period.end): m.id
            for m in flow.movements
            if m.period is not None
        }
        if sorted(by_period) != sorted(periods) or len(flow.movements) != len(periods):
            raise ContractError(
                f"the paths have other Periods than the Flow {item.key}",
                code=Code.ALIGNMENT_DIFFER,
                targets=(item.value.id,),
                values={"key": item.key, "series": item.series},
            )
        units = paths.series(name=item.series).units
        model.unit_system.convert(
            quantity=Quantity(magnitude=1, units=units), to=flow.units
        )
        found.append(
            SeriesBinding(
                series=item.series,
                value=Reference(target=item.value.id),
                movements=tuple(Reference(target=by_period[p]) for p in periods),
            )
        )
    return tuple(found)


def path_case(*, paths: Paths, key: str, series: tuple[SeriesBinding, ...]) -> PathCase:
    """Return the reference of a case to one path of ``paths``."""
    return PathCase(paths=paths.id, key=key, series=series)


def targets(path: PathCase | None) -> set[UUID]:
    """Return the Movements that a path fixes."""
    if path is None:
        return set()
    return {ref.target for binding in path.series for ref in binding.movements}


def load(resolver: object, identity: UUID) -> Paths:
    """Return the Paths revision ``identity`` from a resolver that loads Paths."""
    loader = getattr(resolver, "load_paths", None)
    if loader is None:
        raise ContractError(
            f"the Paths revision {identity} is not available: give a resolver "
            "that loads Paths, such as a store",
            code=Code.RESOLVER_MISSING,
            targets=(identity,),
        )
    found = loader(identity)
    if not isinstance(found, Paths) or found.id != identity:
        raise ContractError(
            f"the resolver did not return the Paths revision {identity}",
            code=Code.REFERENCE_IDENTITY,
            targets=(identity,),
        )
    return found


def expand(effective: dict[str, Any], *, paths: Mapping[UUID, Paths]) -> None:
    """Add the assignments of the path of a composed case, from its Paths document.

    The amounts are those of the path's series in each Period, in the units
    of the series. Nothing happens for a case without a path.
    """
    path = effective.get("path")
    if path is None:
        return
    identity = UUID(path["paths"])
    document = paths.get(identity)
    require(
        document is not None,
        f"the Paths revision {identity} of this case is not available",
        code=Code.RESOLVER_MISSING,
        path="/path/paths",
        targets=(identity,),
    )
    assert document is not None
    require(
        path["key"] in document,
        f"the Paths revision {identity} has no path {path['key']}",
        code=Code.REFERENCE_MISSING,
        path="/path/key",
        values={"key": path["key"]},
    )
    member = document[path["key"]]
    assignments = effective.setdefault("assignments", [])
    for index, binding in enumerate(path["series"]):
        flow = member[binding["series"]]
        movements = binding["movements"]
        require(
            len(movements) == len(flow.movements),
            f"series {binding['series']} has {len(flow.movements)} amounts for "
            f"{len(movements)} Movements",
            path=pointer.child("/path/series", index),
        )
        for reference, amount in zip(movements, flow.movements, strict=True):
            quantity = Quantity(magnitude=amount.magnitude, units=flow.units)
            assignments.append(
                {"target": dict(reference), "quantity": quantity.to_data()}
            )
