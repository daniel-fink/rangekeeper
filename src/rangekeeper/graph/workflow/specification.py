"""Strict immutable workflow declarations. YAML is data, never executable code."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any
from uuid import UUID

from rangekeeper.graph import _structured
from rangekeeper.graph.adapter.excel import ExtractionSpec
from rangekeeper.graph.adapter.excel.classification import RowClassificationSpec
from rangekeeper.graph.workflow.ingestion.tabular import NumberSpec
from rangekeeper.graph.workflow.ingestion.transform import TransformSpec

from ._declarations import fields, plain, sequence, text


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadSpec:
    """Binds a logical source to allowed filenames and an expected edition, keeping
    filesystem choices out of graph identity.
    """

    files: tuple[str, ...]
    source_key: str
    checksum: str | None = None

    def __post_init__(self):
        paths = sequence(self.files)
        if not paths:
            raise ValueError("read requires file candidates")
        for p in paths:
            text(p)
            if Path(p).is_absolute() or ".." in Path(p).parts:
                raise ValueError("Input paths must stay under input_root")
        text(self.source_key)
        if self.checksum is not None:
            text(self.checksum)
        object.__setattr__(self, "files", paths)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExtractSpec:
    """Connects a prior workbook output to an existing ExtractionSpec; the wrapper
    supplies workflow wiring rather than another extraction algorithm.
    """

    input: str
    specification: ExtractionSpec
    unique_stop: bool = False

    def __post_init__(self):
        text(self.input)
        if not isinstance(self.specification, ExtractionSpec):
            raise TypeError("Expected ExtractionSpec")
        if type(self.unique_stop) is not bool:
            raise TypeError("unique_stop must be boolean")
        if self.unique_stop and self.specification.rows.stop_before is None:
            raise ValueError("unique_stop requires a stopping marker")


@dataclass(frozen=True, slots=True, kw_only=True)
class ClassifySpec:
    """Supplies both extracted Evidence and its native snapshot because physical
    occupancy cannot be inferred from interpreted values alone.
    """

    input: str
    workbook: str
    specification: RowClassificationSpec

    def __post_init__(self):
        text(self.input)
        text(self.workbook)
        if not isinstance(self.specification, RowClassificationSpec):
            raise TypeError("Expected RowClassificationSpec")


@dataclass(frozen=True, slots=True, kw_only=True)
class NumbersSpec:
    """Connects a named table to output-column NumberSpec policies. The plural
    wrapper owns dependency wiring; the singular NumberSpec owns numeric
    admissibility.
    """

    input: str
    specifications: Mapping[str, NumberSpec]

    def __post_init__(self):
        text(self.input)
        if not isinstance(self.specifications, Mapping) or any(
            type(k) is not str or not isinstance(v, NumberSpec)
            for k, v in self.specifications.items()
        ):
            raise TypeError("Expected NumberSpec mapping")
        object.__setattr__(
            self, "specifications", MappingProxyType(dict(self.specifications))
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class TransformsSpec:
    """Connects a named table to reusable TransformSpec policies, allowing label
    interpretation to remain independent of the workflow runner.
    """

    input: str
    specifications: Mapping[str, TransformSpec]

    def __post_init__(self):
        text(self.input)
        if not isinstance(self.specifications, Mapping) or any(
            type(k) is not str or not isinstance(v, TransformSpec)
            for k, v in self.specifications.items()
        ):
            raise TypeError("Expected TransformSpec mapping")
        object.__setattr__(
            self, "specifications", MappingProxyType(dict(self.specifications))
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SelectSpec:
    """Declares which observations a later step needs while delegating Claim
    preservation and Issue-scope projection to ingestion.
    """

    input: str
    where: Mapping[str, object] | None = None
    columns: tuple[str, ...] | None = None
    row_ids: tuple[str, ...] | None = None

    def __post_init__(self):
        text(self.input)
        if self.where is not None:
            from .ingestion.predicates import Predicate

            Predicate.from_mapping(self.where)
            if self.row_ids is not None:
                raise ValueError("Specify where or row_ids")
            object.__setattr__(self, "where", _structured.freeze_mapping(self.where))
        for key in ("columns", "row_ids"):
            if getattr(self, key) is not None:
                values = sequence(getattr(self, key))
                for v in values:
                    text(v)
                    if key == "row_ids":
                        UUID(v)
                object.__setattr__(self, key, values)


@dataclass(frozen=True, slots=True, kw_only=True)
class ConcatSpec:
    """Makes input order explicit so combining source ranges remains repeatable and
    reviewable.
    """

    inputs: tuple[str, ...]

    def __post_init__(self):
        values = sequence(self.inputs)
        if not values:
            raise ValueError("concat requires at least one input")
        for v in values:
            text(v)
        object.__setattr__(self, "inputs", values)


@dataclass(frozen=True, slots=True)
class OperationDeclaration:
    """One closed descriptor for request parsing and dependency validation.

    The runner has explicit dispatch branches; this catalog is not a plugin API.
    """

    request_type: type[
        ReadSpec
        | ExtractSpec
        | ClassifySpec
        | NumbersSpec
        | TransformsSpec
        | SelectSpec
        | ConcatSpec
    ]
    inputs: tuple[tuple[str, str], ...] = ()
    output: str = "table"
    policy_type: (
        type[ExtractionSpec | RowClassificationSpec | NumberSpec | TransformSpec] | None
    ) = None
    policy_field: str = "specification"

    def parse(self, value):
        from dataclasses import MISSING

        attributes = self.request_type.__dataclass_fields__
        data = fields(
            value,
            attributes,
            {
                k
                for k, f in attributes.items()
                if f.default is MISSING and f.default_factory is MISSING
            },
        )
        if self.policy_type is not None:
            raw = data[self.policy_field]
            if self.policy_field == "specifications":
                if not isinstance(raw, Mapping):
                    raise TypeError("specifications must be a mapping")
                data[self.policy_field] = {
                    text(k): self.policy_type.from_mapping(v) for k, v in raw.items()
                }
            else:
                data[self.policy_field] = self.policy_type.from_mapping(raw)
        return self.request_type(**data)

    def dependencies(self, request):
        return tuple(
            (name, kind)
            for field, kind in self.inputs
            for name in (
                getattr(request, field)
                if field == "inputs"
                else (getattr(request, field),)
            )
        )


_OPERATIONS = {
    "read": OperationDeclaration(ReadSpec, output="workbook"),
    "extract": OperationDeclaration(
        ExtractSpec, (("input", "workbook"),), policy_type=ExtractionSpec
    ),
    "classify_rows": OperationDeclaration(
        ClassifySpec,
        (("input", "table"), ("workbook", "workbook")),
        policy_type=RowClassificationSpec,
    ),
    "numbers": OperationDeclaration(
        NumbersSpec,
        (("input", "table"),),
        policy_type=NumberSpec,
        policy_field="specifications",
    ),
    "transform": OperationDeclaration(
        TransformsSpec,
        (("input", "table"),),
        policy_type=TransformSpec,
        policy_field="specifications",
    ),
    "select": OperationDeclaration(SelectSpec, (("input", "table"),)),
    "concat": OperationDeclaration(ConcatSpec, (("inputs", "table"),)),
}


@dataclass(frozen=True, slots=True, kw_only=True)
class StepSpec:
    """Gives one reusable operation a stable name and explicit dependencies,
    allowing YAML to connect capabilities without embedding executable code.
    """

    id: str
    operation: str
    request: (
        ReadSpec
        | ExtractSpec
        | ClassifySpec
        | NumbersSpec
        | TransformsSpec
        | SelectSpec
        | ConcatSpec
    )

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
            **{
                k: plain(getattr(self.request, k))
                for k in self.request.__dataclass_fields__
            },
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


def schema() -> Mapping[str, object]:
    """Return the closed operation catalog as JSON-serializable schema data.

    Helps tools author registered steps without discovering the API by trial and
    error. It covers the step catalog, not the complete model, decisions and
    checks language.
    """
    from dataclasses import MISSING

    def obj(properties, required=()):
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
            "required": list(required),
        }

    string = {"type": "string", "minLength": 1}
    names = {"type": "array", "items": string}
    boolean = {"type": "boolean"}
    number = obj(
        {
            "column": string,
            "integer": boolean,
            "nonnegative": boolean,
            "missing_markers": names,
        },
        ("column",),
    )
    transform = obj(
        {
            "operation": {
                "enum": [
                    "normalize",
                    "capture",
                    "capture_integer",
                    "lookup",
                    "agreement",
                    "fallback",
                    "format",
                    "match",
                ]
            },
            "columns": {**names, "minItems": 1, "uniqueItems": True},
            "pattern": {"type": ["string", "null"]},
            "group": {"type": "integer", "minimum": 0},
            "case": {"enum": ["preserve", "lower", "upper", "casefold"]},
            "flags": {"enum": ["", "ignorecase"]},
            "values": {"type": "object"},
            "default": {},
            "template": {"type": ["string", "null"]},
        },
        ("operation", "columns"),
    )
    comparison = {"enum": ["exact", "trim"]}
    rows = obj(
        {
            "start": {"type": "integer", "minimum": 1},
            "end": {"type": "integer", "minimum": 1},
            "stop_before": obj(
                {"column": string, "equals": {}, "comparison": comparison},
                ("column", "equals"),
            ),
        },
        ("start",),
    )
    rows["oneOf"] = [{"required": ["end"]}, {"required": ["stop_before"]}]
    extraction = obj(
        {
            "id": string,
            "version": {"const": 1},
            "sheet": string,
            "rows": rows,
            "columns": {
                "type": "array",
                "minItems": 1,
                "items": obj({"name": string, "column": string}, ("name", "column")),
            },
            "expect": obj({"cells": {"type": "object"}, "comparison": comparison}),
            "formula_values": {"const": "cached"},
        },
        ("id", "version", "sheet", "rows", "columns"),
    )
    where = obj({"column": string, "equals": {}, "in": {"type": "array"}}, ("column",))
    where["oneOf"] = [{"required": ["equals"]}, {"required": ["in"]}]
    properties = {
        "read": {
            "files": {**names, "minItems": 1},
            "source_key": string,
            "checksum": {"type": ["string", "null"]},
        },
        "extract": {
            "input": string,
            "specification": extraction,
            "unique_stop": boolean,
        },
        "classify_rows": {
            "input": string,
            "workbook": string,
            "specification": obj(
                {
                    "identifier": string,
                    "pattern": string,
                    "output": string,
                    "columns": names,
                },
                ("identifier", "pattern"),
            ),
        },
        "numbers": {
            "input": string,
            "specifications_ref": string,
            "specifications": {"type": "object", "additionalProperties": number},
        },
        "transform": {
            "input": string,
            "specifications": {"type": "object", "additionalProperties": transform},
        },
        "select": {
            "input": string,
            "columns": {"type": ["array", "null"], "items": string},
            "row_ids": {
                "type": ["array", "null"],
                "items": {"type": "string", "format": "uuid"},
            },
            "where": {"anyOf": [where, {"type": "null"}]},
        },
        "concat": {"inputs": {**names, "minItems": 1}},
    }
    result = {
        "version": 1,
        "documents": ["sources", "model", "decisions", "checks"],
        "executableContent": False,
        "operations": {
            name: obj(
                {"id": string, "operation": {"const": name}, **properties[name]},
                ["id", "operation"]
                + [
                    key
                    for key, f in declaration.request_type.__dataclass_fields__.items()
                    if f.default is MISSING and f.default_factory is MISSING
                ],
            )
            for name, declaration in _OPERATIONS.items()
        },
    }

    numeric = result["operations"]["numbers"]
    numeric["required"].remove("specifications")
    numeric["oneOf"] = [
        {"required": ["specifications"]},
        {"required": ["specifications_ref"]},
    ]
    binding = obj({"value": {}, "column": string, "evidence": string})
    binding["oneOf"] = [
        {
            "required": ["value"],
            "not": {"anyOf": [{"required": ["column"]}, {"required": ["evidence"]}]},
        },
        {"required": ["column"], "not": {"required": ["value"]}},
    ]
    condition = obj(
        {
            "binding": binding,
            "equals": {},
            "in": {"type": "array"},
            "available": boolean,
        },
        ("binding",),
    )
    condition["oneOf"] = [{"required": [key]} for key in ("equals", "in", "available")]
    measurement = obj(
        {
            "measure": string,
            "binding": binding,
            "when": condition,
            "decisions": names,
            "evidence": {"type": "array", "items": binding},
            "on_unavailable": obj({
                "feature": string,
                "binding": binding,
                "topic": string,
                "explanation": string,
            }),
        },
        ("measure", "binding"),
    )
    result["shared_declarations"] = {
        "number_sets": {
            "type": "object",
            "additionalProperties": {"type": "object", "additionalProperties": number},
        },
        "measurement_sets": {
            "type": "object",
            "additionalProperties": {"type": "array", "items": measurement},
        },
        "measurement_use": obj(
            {"measurements_ref": string, "measurements_evidence": string},
            ("measurements_ref",),
        ),
    }
    result["operations"]["select"]["not"] = {
        "required": ["where", "row_ids"],
        "properties": {"where": {"type": "object"}, "row_ids": {"type": "array"}},
    }
    return result
