"""Resolve two named policy forms without adding execution or template semantics.

The output is ordinary declarations. Definitions remain auditable, and every use
gets its own copy so assigning a total's context cannot change a level's policy.
"""

from collections.abc import Mapping
from copy import deepcopy

from ._declarations import fields, sequence, text
from .composition import validate_measurements
from .ingestion.tabular import NumberSpec


def _registry(value):
    if not isinstance(value, Mapping):
        raise TypeError("Expected a named-set mapping")
    for name in value:
        text(name)
    return value


def resolve_numbers(document):
    """Replace whole-set references; input dependencies and operation order stay explicit."""
    source = fields(
        document, {"namespace", "steps", "number_sets"}, {"namespace", "steps"}
    )
    sets = _registry(source.pop("number_sets", {}))
    for name, declarations in sets.items():
        try:
            for column, policy in _registry(declarations).items():
                text(column)
                NumberSpec.from_mapping(policy)
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"sources.number_sets.{name}: {exc}") from exc
    steps, origins = [], []
    for raw in sequence(source["steps"]):
        step = dict(raw)
        if "specifications_ref" in step:
            name = text(step["specifications_ref"])
            address = f"sources.steps.{step.get('id', '?')}.specifications"
            if step.get("operation") != "numbers":
                raise ValueError(f"{address}: specifications_ref is only for numbers")
            if "specifications" in step:
                raise ValueError(
                    f"{address}: choose inline specifications or specifications_ref"
                )
            if name not in sets:
                raise ValueError(f"{address}: unknown number set {name}")
            step.pop("specifications_ref")
            step["specifications"] = deepcopy(sets[name])
            origins.append({
                "consumer": address,
                "definition": f"sources.number_sets.{name}",
            })
        steps.append(step)
    source["steps"] = steps
    return source, origins


def _bindings(measurements):
    """Visit only supported binding positions; never rewrite arbitrary values."""
    for attr in measurements:
        yield attr["binding"]
        yield from attr.get("evidence", ())
        if attr.get("when") is not None:
            yield attr["when"]["binding"]
        if "binding" in attr.get("on_unavailable", {}):
            yield attr["on_unavailable"]["binding"]


def resolve_measurements(document, seen, decisions):
    """Apply shared bindings in a consumer's row or an explicit single-row context.

    Context changes only relative bindings, including conditions and missing-value
    support. Explicit Evidence references and literal values are always preserved.
    """
    model = deepcopy(document)
    sets = _registry(model.pop("measurement_sets", {}))
    decision_ids = [d["id"] for d in sequence(decisions["decisions"])]
    measures = [m["code"] for m in sequence(model["measures"])]
    for name, values in sets.items():
        try:
            validate_measurements(values, seen, decision_ids, measures)
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"model.measurement_sets.{name}: {exc}") from exc
    origins = []
    for category in ("templates", "objects"):
        for item in sequence(model[category]):
            address = f"model.{category}.{item.get('id', '?')}.measurements"
            if "measurements_evidence" in item and "measurements_ref" not in item:
                raise ValueError(
                    f"{address}: measurements_evidence requires measurements_ref"
                )
            if "measurements_ref" not in item:
                continue
            name = text(item.pop("measurements_ref"))
            origin = {
                "consumer": address,
                "definition": f"model.measurement_sets.{name}",
            }
            try:
                if "measurements" in item:
                    raise ValueError("choose inline measurements or measurements_ref")
                if name not in sets:
                    raise ValueError("unknown measurement set")
                values = deepcopy(sets[name])
                if "measurements_evidence" in item:
                    text(item["measurements_evidence"])
                context = item.pop("measurements_evidence", None)
                if context is not None:
                    text(context)
                    if seen.get(context) != "table":
                        raise ValueError(f"unknown measurement Evidence {context}")
                    origin["evidence"] = context
                for binding in _bindings(values):
                    if "column" in binding and "evidence" not in binding:
                        if context is not None:
                            binding["evidence"] = context
                        elif "table" not in item:
                            raise ValueError(
                                "relative binding requires a template table or measurements_evidence"
                            )
                validate_measurements(values, seen, decision_ids, measures)
                item["measurements"] = values
            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(
                    f"{address} using measurement set {name}: {exc}"
                ) from exc
            origins.append(origin)
    return model, origins
