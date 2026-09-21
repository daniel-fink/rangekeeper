"""Strict immutable workflow declarations. YAML is data, never executable code."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rangekeeper.graph import _structured

from ._contracts import OperationDeclaration
from ._declarations import fields, sequence, text
from ._schema import schema
from ._table_operations import ConcatSpec, NumbersSpec, SelectSpec, TransformsSpec
from .catalog import OPERATIONS as _OPERATIONS


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
        from rangekeeper.graph.workflow.checking import validate_checks
        from rangekeeper.graph.workflow.composition import validate_model

        try:
            validate_model(self.model, seen, self.decisions)
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"model: {exc}") from exc
        try:
            validate_checks(self.checks, seen)
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"checks: {exc}") from exc
        from rangekeeper.graph.workflow.source_checks import (
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


def load(spec_directory: Path) -> WorkflowSpec:
    """Establishes the four-document configuration boundary and records source
    bytes through hashes. This makes reviewed intent available to a repeatable
    build without an LLM or notebook state.
    """
    import hashlib

    from rangekeeper.graph._yaml import decode

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
            or doc["version"] != 1
        ):
            raise ValueError(
                f"{name}: expected RK workflow version 1; migrate legacy project specifications explicitly"
            )
        documents[name] = dict(doc)
        documents[name].pop("version")
    from ._shared import resolve_measurements, resolve_numbers

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
            "version": 1,
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


def __getattr__(name):
    # Existing Python request imports remain available without teaching the
    # generic specification implementation about concrete adapter classes.
    legacy = {
        "ReadSpec": "read",
        "ExtractSpec": "extract",
        "ClassifySpec": "classify_rows",
    }
    if name in legacy:
        return _OPERATIONS[legacy[name]].request_type
    raise AttributeError(name)


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
