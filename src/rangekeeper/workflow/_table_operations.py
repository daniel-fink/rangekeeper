"""Workflow wiring for format-independent table operations."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID

from rangekeeper import _structured

from ._contracts import OperationDeclaration, Produced
from ._declarations import sequence, text
from ._schema import obj
from rangekeeper.evidence import fingerprint, tabular
from rangekeeper.evidence.predicates import Predicate, select_where
from rangekeeper.evidence.tabular import NumberSpec
from rangekeeper.evidence.transform import TransformSpec, transform


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

    @classmethod
    def from_mapping(cls, data):
        raw = data["specifications"]
        if not isinstance(raw, Mapping):
            raise TypeError("specifications must be a mapping")
        return cls(
            input=data["input"],
            specifications={
                text(key): NumberSpec.from_mapping(value) for key, value in raw.items()
            },
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

    @classmethod
    def from_mapping(cls, data):
        raw = data["specifications"]
        if not isinstance(raw, Mapping):
            raise TypeError("specifications must be a mapping")
        return cls(
            input=data["input"],
            specifications={
                text(key): TransformSpec.from_mapping(value)
                for key, value in raw.items()
            },
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
            from rangekeeper.evidence.predicates import Predicate

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


def describe_table(value):
    return Produced(value, fingerprint(value))


OPERATIONS = {
    "numbers": OperationDeclaration(
        NumbersSpec,
        _numbers,
        describe_table,
        lambda: request_properties()["numbers"],
        inputs=(("input", "table"),),
    ),
    "transform": OperationDeclaration(
        TransformsSpec,
        _transform,
        describe_table,
        lambda: request_properties()["transform"],
        inputs=(("input", "table"),),
    ),
    "select": OperationDeclaration(
        SelectSpec,
        _select,
        describe_table,
        lambda: request_properties()["select"],
        inputs=(("input", "table"),),
    ),
    "concat": OperationDeclaration(
        ConcatSpec,
        _concat,
        describe_table,
        lambda: request_properties()["concat"],
        inputs=(("inputs", "table"),),
        repeated_inputs=("inputs",),
    ),
}
