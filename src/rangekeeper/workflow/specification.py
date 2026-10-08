"""Strict immutable workflow declarations. YAML is data, never executable code."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from copy import deepcopy
from pathlib import Path
from typing import Any

from rangekeeper.shared import structured as _structured

from rangekeeper.workflow._contracts import OperationDeclaration
from rangekeeper.workflow._declarations import fields, sequence, text
from rangekeeper.workflow._schema import schema
from rangekeeper.workflow._table_operations import (
    ConcatSpec,
    NumbersSpec,
    SelectSpec,
    TransformsSpec,
)
from rangekeeper.workflow.catalog import OPERATIONS as _OPERATIONS
from rangekeeper.workflow._model_validation import (
    validate_measurements,
    validate_model_declaration,
)
from rangekeeper.workflow.evidence.tabular import NumberSpec


@dataclass(frozen=True, slots=True, kw_only=True)
class StepSpec:
    """Gives one reusable operation a stable name and explicit dependencies,
    allowing YAML to connect capabilities without embedding executable code.
    """

    id: str
    operation: str
    request: Any

    def __post_init__(self):
        text(self.id)
        if (
            self.operation not in _OPERATIONS
            or type(self.request) is not _OPERATIONS[self.operation].request_type
        ):
            raise ValueError("Unknown operation or wrong request type")

    @classmethod
    def from_mapping(cls, value):
        """Resolves a declaration only through the closed operation catalog and its
        typed request contract; configuration cannot select an arbitrary
        callable.
        """
        fields(
            value, set(value) if isinstance(value, Mapping) else (), {"id", "operation"}
        )
        data = dict(value)
        name = data.pop("id")
        op = data.pop("operation")
        if type(op) is not str or op not in _OPERATIONS:
            raise ValueError(f"Unknown workflow operation: {op}")
        try:
            request = _OPERATIONS[op].parse(data)
        except (TypeError, ValueError) as exc:
            raise type(exc)(f"steps.{name}: {exc}") from exc
        return cls(id=name, operation=op, request=request)

    def to_mapping(self):
        """Records effective request values for reproducibility instead of
        depending on how the source declaration happened to be written.
        """
        return {
            "id": self.id,
            "operation": self.operation,
            **_OPERATIONS[self.operation].parameters(self.request),
        }

    @property
    def inputs(self):
        """Exposes dependency names without opening sources, allowing ordering and
        input-kind errors to be caught before execution.
        """
        return tuple(
            name for name, _ in _OPERATIONS[self.operation].dependencies(self.request)
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowSpec:
    """Retains the reviewed build inputs as one immutable declaration and checks
    dependencies before source execution. Model and check sections currently
    remain validated frozen mappings.
    """

    namespace: str
    steps: tuple[StepSpec, ...]
    model: Mapping[str, Any]
    decisions: Mapping[str, Any]
    checks: Mapping[str, Any]
    hashes: Mapping[str, str]
    declarations: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        text(self.namespace)
        seen = {}
        for step in self.steps:
            if not isinstance(step, StepSpec):
                raise TypeError("steps require StepSpec")
            if step.id in seen:
                raise ValueError(f"Duplicate step: {step.id}")
            if set(step.inputs) - set(seen):
                raise ValueError(f"{step.id} references a missing or later step")
            declaration = _OPERATIONS[step.operation]
            for inp, expected in declaration.dependencies(step.request):
                if seen[inp] != expected:
                    raise ValueError(f"{step.id} expects {expected} input {inp}")
            seen[step.id] = declaration.output
        object.__setattr__(self, "steps", tuple(self.steps))
        for key in ("model", "decisions", "checks", "hashes", "declarations"):
            object.__setattr__(
                self, key, _structured.freeze_mapping(getattr(self, key))
            )
        from rangekeeper.workflow.checking import validate_checks

        try:
            validate_model_declaration(self.model, seen, self.decisions)
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"model: {exc}") from exc
        try:
            validate_checks(self.checks, seen)
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"checks: {exc}") from exc
        from rangekeeper.workflow.source_checks import (
            validate as validate_source_checks,
        )

        validate_source_checks(self.checks.get("source_checks", ()), seen)

    def to_mapping(self):
        """Provides the effective build declaration for configuration lineage and
        audit independently of YAML formatting.
        """
        return {
            "namespace": self.namespace,
            "steps": tuple(s.to_mapping() for s in self.steps),
            "model": self.model,
            "decisions": self.decisions,
            "checks": self.checks,
            "hashes": self.hashes,
            **({"declarations": self.declarations} if self.declarations else {}),
        }


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
            origins.append(
                {
                    "consumer": address,
                    "definition": f"sources.number_sets.{name}",
                }
            )
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


def load(spec_directory: Path) -> WorkflowSpec:
    """Establishes the four-document configuration boundary and records source
    bytes through hashes. This makes reviewed intent available to a repeatable
    build without an LLM or notebook state.
    """
    import hashlib

    from rangekeeper.shared.yaml import decode

    documents = {}
    hashes = {}
    for name in ("sources", "model", "decisions", "checks"):
        path = Path(spec_directory) / (name + ".yaml")
        content = path.read_bytes()
        hashes[path.name] = hashlib.sha256(content).hexdigest()
        doc = decode(content)
        if (
            not isinstance(doc, Mapping)
            or type(doc.get("version")) is not int
            or doc["version"] != 2
        ):
            raise ValueError(
                f"{name}: expected RK workflow version 2; migrate legacy project specifications explicitly"
            )
        documents[name] = dict(doc)
        documents[name].pop("version")
    sources, numeric_origins = resolve_numbers(documents["sources"])
    steps = tuple(StepSpec.from_mapping(v) for v in sequence(sources["steps"]))
    seen = {step.id: _OPERATIONS[step.operation].output for step in steps}
    model, measurement_origins = resolve_measurements(
        documents["model"], seen, documents["decisions"]
    )
    declarations = {}
    if (
        "number_sets" in documents["sources"]
        or "measurement_sets" in documents["model"]
    ):
        declarations = {
            "version": 2,
            "number_sets": documents["sources"].get("number_sets", {}),
            "measurement_sets": documents["model"].get("measurement_sets", {}),
            "uses": [*numeric_origins, *measurement_origins],
        }
    return WorkflowSpec(
        namespace=sources["namespace"],
        steps=steps,
        model=model,
        decisions=documents["decisions"],
        checks=documents["checks"],
        hashes=hashes,
        declarations=declarations,
    )


__all__ = [
    "ConcatSpec",
    "NumbersSpec",
    "OperationDeclaration",
    "SelectSpec",
    "StepSpec",
    "TransformsSpec",
    "WorkflowSpec",
    "load",
    "schema",
]
