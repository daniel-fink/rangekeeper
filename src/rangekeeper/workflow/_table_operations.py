"""Workflow wiring for format-independent table operations."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID

from rangekeeper.shared import structured as _structured

from rangekeeper.workflow._contracts import OperationDeclaration, Produced
from rangekeeper.workflow._declarations import sequence, text
from rangekeeper.workflow._schema import obj
from rangekeeper.workflow.evidence import tabular
from rangekeeper.workflow.evidence.predicates import Predicate, select_where
from rangekeeper.workflow.evidence.tabular import NumberSpec
from rangekeeper.workflow.evidence.transform import TransformSpec, transform


def _specifications(value, kind, *, parse=False):
    """Copy a policy mapping in encounter order, preserving each boundary's checks."""
    if parse:
        if not isinstance(value, Mapping):
            raise TypeError("specifications must be a mapping")
        return {text(key): kind.from_mapping(item) for key, item in value.items()}
    if not isinstance(value, Mapping) or any(
        type(key) is not str or not isinstance(item, kind)
        for key, item in value.items()
    ):
        raise TypeError(f"Expected {kind.__name__} mapping")
    return MappingProxyType(dict(value))


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
        object.__setattr__(
            self, "specifications", _specifications(self.specifications, NumberSpec)
        )

    @classmethod
    def from_mapping(cls, data):
        return cls(
            input=data["input"],
            specifications=_specifications(
                data["specifications"], NumberSpec, parse=True
            ),
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
        object.__setattr__(
            self, "specifications", _specifications(self.specifications, TransformSpec)
        )

    @classmethod
    def from_mapping(cls, data):
        return cls(
            input=data["input"],
            specifications=_specifications(
                data["specifications"], TransformSpec, parse=True
            ),
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
            from rangekeeper.workflow.evidence.predicates import Predicate

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


def number_schema():
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
    return number


def request_properties():
    string = {"type": "string", "minLength": 1}
    names = {"type": "array", "items": string}
    number = number_schema()
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
    where = obj({"column": string, "equals": {}, "in": {"type": "array"}}, ("column",))
    where["oneOf"] = [{"required": ["equals"]}, {"required": ["in"]}]
    properties = {
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
    return properties


def _numbers(request, inputs, context):
    return tabular.numbers(
        inputs[request.input],
        specifications=request.specifications,
        settings=context.settings,
        name=context.name,
    )


def _transform(request, inputs, context):
    return transform(
        inputs[request.input],
        specifications=request.specifications,
        settings=context.settings,
        name=context.name,
    )


def _select(request, inputs, context):
    evidence = inputs[request.input]
    if request.where is not None:
        return select_where(
            evidence,
            predicate=Predicate.from_mapping(request.where),
            columns=request.columns,
            name=context.name,
        )
    ids = None if request.row_ids is None else tuple(UUID(x) for x in request.row_ids)
    return tabular.select(
        evidence, row_ids=ids, columns=request.columns, name=context.name
    )


def _concat(request, inputs, context):
    return tabular.concat((inputs[k] for k in request.inputs), name=context.name)


OPERATIONS = {
    "numbers": OperationDeclaration(
        NumbersSpec,
        _numbers,
        Produced.from_evidence,
        lambda: request_properties()["numbers"],
        inputs=(("input", "table"),),
    ),
    "transform": OperationDeclaration(
        TransformsSpec,
        _transform,
        Produced.from_evidence,
        lambda: request_properties()["transform"],
        inputs=(("input", "table"),),
    ),
    "select": OperationDeclaration(
        SelectSpec,
        _select,
        Produced.from_evidence,
        lambda: request_properties()["select"],
        inputs=(("input", "table"),),
    ),
    "concat": OperationDeclaration(
        ConcatSpec,
        _concat,
        Produced.from_evidence,
        lambda: request_properties()["concat"],
        inputs=(("inputs", "table"),),
        repeated_inputs=("inputs",),
    ),
}
