"""Explicit, inspectable affinity construction; never changes graph membership.

No fields are selected automatically. A signal family can be represented once,
so a caller cannot accidentally weight a count and its redundant type label twice.
"""

from dataclasses import asdict, dataclass
from itertools import combinations
from math import isfinite

from rangekeeper.graph import Feature, Graph, Measurement


@dataclass(frozen=True)
class Signal:
    source: str  # classification, label, feature, measurement
    key: str
    kind: str  # numeric or category (sets use Jaccard similarity)
    family: str
    weight: int = 1


def affinities(
    graph: Graph,
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
    entities = {str(e.id): e for e in graph.entities}
    if not set(members) <= entities.keys():
        raise ValueError("Unknown member")
    columns: list[dict] = []
    for signal in signals:
        if signal.source not in {
            "classification",
            "label",
            "feature",
            "measurement",
        } or signal.kind not in {"numeric", "category"}:
            raise ValueError("Unsupported signal selector")
        if not signal.family or type(signal.weight) is not int or signal.weight <= 0:
            raise ValueError("Signals require a family and positive integer weight")
        if signal.source in {"classification", "label"} and signal.kind != "category":
            raise ValueError("Classifications and labels are categorical")
        if signal.source == "measurement" and signal.kind != "numeric":
            raise ValueError("Measurements require numeric comparison")
        values, unit = {}, None
        for identifier in sorted(members):
            entity = entities[identifier]
            value = None
            if signal.source == "classification":
                if entity.classification:
                    value = [str(entity.classification.id)]
            elif signal.source == "label":
                label = entity.labels.get(signal.key)
                if label and label.classifications:
                    value = sorted(str(c.id) for c in label.classifications)
            else:
                characteristic = (
                    entity.features
                    if signal.source == "feature"
                    else entity.measurements
                ).get(signal.key)
                if characteristic is not None:
                    fact = graph.provenance.fact_for(characteristic)
                    if fact is not None and fact.current_claim is None:
                        # Unresolved conflicting evidence cannot drive an affinity.
                        values[identifier] = None
                        continue
                    if signal.source == "measurement":
                        assert isinstance(characteristic, Measurement)
                        quantity = characteristic.quantity.to_base_units()
                        this_unit = str(quantity.units)
                        if unit is not None and unit != this_unit:
                            raise ValueError(
                                "Incompatible measurement units in selected signal"
                            )
                        unit = this_unit
                        value = float(quantity.magnitude)
                    else:
                        assert isinstance(characteristic, Feature)
                        value = characteristic.value
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
        columns.append({
            "signal": asdict(signal),
            "unit": unit,
            "values": values,
            "active": len(unique) > 1,
            "range": [min(observed), max(observed)]
            if signal.kind == "numeric" and observed
            else None,
            "missing": sum(v is None for v in values.values()),
        })
    active = [c for c in columns if c["active"]]
    denominator = sum(c["signal"]["weight"] for c in active)
    edges, pairs = [], []
    for left, right in combinations(sorted(members), 2):
        score = 0
        components = []
        for column in active:
            a, b = column["values"][left], column["values"][right]
            contribution = 0
            if a is not None and b is not None:
                if column["signal"]["kind"] == "numeric":
                    lo, hi = column["range"]
                    contribution = max(0.0, 1 - abs(a - b) / (hi - lo))
                else:
                    contribution = len(set(a) & set(b)) / len(set(a) | set(b))
            score += column["signal"]["weight"] * contribution
            components.append({
                "family": column["signal"]["family"],
                "similarity": contribution,
                "both_available": a is not None and b is not None,
            })
        strength = int(100 * score / denominator + 1e-9) if denominator else 0
        retained = strength >= threshold
        pairs.append({
            "left": left,
            "right": right,
            "strength": strength,
            "retained": retained,
            "components": components,
        })
        if retained:
            edges.append((left, right, strength))
    return tuple(edges), {"threshold": threshold, "columns": columns, "pairs": pairs}
