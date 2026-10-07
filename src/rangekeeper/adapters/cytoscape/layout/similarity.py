"""Explicit, inspectable affinity construction; never changes graph membership.

No fields are selected automatically. A signal family can be represented once,
so a caller cannot accidentally weight a count and its redundant type label twice.
"""

from dataclasses import asdict, dataclass
from itertools import combinations
from math import isfinite

from uuid import UUID
from rangekeeper.model import ValueKind, Model
from rangekeeper.model.characteristics import value as find_value, label as find_label
from rangekeeper.model.content import decode
from rangekeeper.model.provenance import fact_for
from rangekeeper.units import default_units


@dataclass(frozen=True)
class Signal:
    source: str  # classification, label, property, quantity
    key: str
    kind: str  # numeric or category (sets use Jaccard similarity)
    family: str
    weight: int = 1
    units: str | None = None


def resolved(model, item):
    """An absent Fact is unasserted; conflicting Claims cannot drive presentation."""
    fact = fact_for(model, item.id)
    return fact is None or (
        bool(fact.reconciliation.selected)
        if fact.reconciliation
        else len(fact.claims) == 1
    )


def select(model, owner, source, key, *, units=None):
    """Read a known property or convert a quantity; never replace missing with zero."""
    item = find_value(owner.characteristics, key)
    if item is None or not resolved(model, item):
        return None
    if source == "property":
        if item.kind is not ValueKind.PROPERTY:
            raise ValueError(f"{owner.id}/{key} is not a property Value")
        return decode(item.content) if item.content is not None else None
    if source != "quantity" or not units:
        raise ValueError("Quantity selection requires explicit units")
    if item.kind is not ValueKind.MEASUREMENT:
        raise ValueError(f"{owner.id}/{key} is not a measurement Value")
    return (
        default_units.convert(item.quantity, to=units).magnitude
        if item.quantity is not None
        else None
    )


def affinities(
    graph: Model,
    members: tuple[str, ...],
    signals: tuple[Signal, ...],
    *,
    threshold: int = 60,
):
    """Return weighted pairs plus evidence of normalization and missingness.

    Numeric measurements are converted to common base units before comparison.
    Missing data earns zero similarity, never a missing-value cluster. Constant
    columns contribute nothing. The denominator is fixed across pairs, so partial
    observations cannot become perfect matches by dropping unavailable signals.
    """
    if type(threshold) is not int or not 1 <= threshold <= 100:
        raise ValueError("Threshold must be an integer from 1 to 100")
    if len(set(members)) != len(members):
        raise ValueError("Repeated member")
    if len({s.family for s in signals}) != len(signals):
        raise ValueError("Select only one signal per evidence family")
    entities = {str(e.id): e for e in graph.find_entities()}
    if not set(members) <= entities.keys():
        raise ValueError("Unknown member")
    columns: list[dict] = []
    for signal in signals:
        if signal.source not in {
            "classification",
            "label",
            "property",
            "quantity",
        } or signal.kind not in {"numeric", "category"}:
            raise ValueError("Unsupported signal selector")
        if not signal.family or type(signal.weight) is not int or signal.weight <= 0:
            raise ValueError("Signals require a family and positive integer weight")
        if signal.source in {"classification", "label"} and signal.kind != "category":
            raise ValueError("Classifications and labels are categorical")
        if signal.source == "quantity" and signal.kind != "numeric":
            raise ValueError("Measurements require numeric comparison")
        if signal.source == "quantity" and not signal.units:
            raise ValueError("Quantity signals require explicit comparison units")
        if signal.source != "quantity" and signal.units is not None:
            raise ValueError("Only quantity signals have units")
        values, unit = {}, signal.units
        for identifier in sorted(members):
            entity = entities[identifier]
            if signal.source == "classification":
                value = [str(entity.classification)] if entity.classification else None
            elif signal.source == "label":
                label = find_label(entity.characteristics, signal.key)
                value = (
                    sorted(str(c) for c in label.classifications or ())
                    if label and resolved(graph, label)
                    else None
                )
            else:
                value = select(
                    graph, entity, signal.source, signal.key, units=signal.units
                )
            if signal.kind == "numeric":
                value = (
                    float(value)
                    if isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and isfinite(value)
                    else None
                )
            elif value is not None:
                if isinstance(value, (tuple, list, set, frozenset)):
                    if not all(type(v) is str for v in value):
                        raise ValueError("Categorical sets must contain strings")
                    value = sorted(set(value)) or None
                elif type(value) is str and value.strip():
                    value = [value]
                else:
                    value = None
            values[identifier] = value
        observed = [v for v in values.values() if v is not None]
        unique = {tuple(v) if isinstance(v, list) else v for v in observed}
        columns.append(
            {
                "signal": asdict(signal),
                "unit": unit,
                "values": values,
                "active": len(unique) > 1,
                "range": (
                    [min(observed), max(observed)]
                    if signal.kind == "numeric" and observed
                    else None
                ),
                "missing": sum(v is None for v in values.values()),
            }
        )
    active = [c for c in columns if c["active"]]
    denominator = sum(c["signal"]["weight"] for c in active)
    edges, pairs = [], []
    for left, right in combinations(sorted(members), 2):
        score: float = 0
        components = []
        for column in active:
            a, b = column["values"][left], column["values"][right]
            contribution: float = 0
            if a is not None and b is not None:
                if column["signal"]["kind"] == "numeric":
                    lo, hi = column["range"]
                    contribution = max(0.0, 1 - abs(a - b) / (hi - lo))
                else:
                    contribution = len(set(a) & set(b)) / len(set(a) | set(b))
            score += column["signal"]["weight"] * contribution
            components.append(
                {
                    "family": column["signal"]["family"],
                    "similarity": contribution,
                    "both_available": a is not None and b is not None,
                }
            )
        strength = int(100 * score / denominator + 1e-9) if denominator else 0
        retained = strength >= threshold
        pairs.append(
            {
                "left": left,
                "right": right,
                "strength": strength,
                "retained": retained,
                "components": components,
            }
        )
        if retained:
            edges.append((left, right, strength))
    return tuple(edges), {"threshold": threshold, "columns": columns, "pairs": pairs}
