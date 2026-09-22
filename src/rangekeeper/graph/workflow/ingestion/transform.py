"""Bounded, declarative text interpretation; original observations are preserved."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from string import Formatter
from uuid import NAMESPACE_URL, uuid5

from rangekeeper.graph import _structured
from rangekeeper.graph.operation import Operation, Outcome, _Failure, _invoke
from rangekeeper.graph.operation import fingerprint as operation_fingerprint
from rangekeeper.graph.provenance import Claim, Method
from rangekeeper.graph.table import Table
from rangekeeper.graph.workflow.ingestion import (
    Evidence,
    Issue,
    IssueSeverity,
    fingerprint,
    tabular,
)

from ._derivation import settings_inputs


@dataclass(frozen=True, slots=True, kw_only=True)
class TransformSpec:
    """Makes label interpretation, agreement and fallback policy reviewable as
    bounded data instead of arbitrary expressions. Capture-to-integer is
    explicit and does not broaden NumberSpec coercion.
    """

    operation: str
    columns: tuple[str, ...] = ()
    pattern: str | None = None
    group: int = 0
    case: str = "preserve"
    values: Mapping[str, object] = field(default_factory=dict)
    default: object = None
    template: str | None = None
    flags: str = ""

    def __post_init__(self):
        allowed = {
            "normalize",
            "capture",
            "capture_integer",
            "lookup",
            "agreement",
            "fallback",
            "format",
            "match",
        }
        if self.operation not in allowed:
            raise ValueError(f"Unknown transformation: {self.operation}")
        if not isinstance(self.columns, (tuple, list)):
            raise TypeError("columns must be an ordered sequence")
        columns = tuple(self.columns)
        if not columns or any(type(x) is not str or not x for x in columns):
            raise ValueError("columns must be a nonempty sequence of names")
        if len(set(columns)) != len(columns):
            raise ValueError("Duplicate transform inputs")
        if (
            self.operation
            in {"normalize", "capture", "capture_integer", "lookup", "match"}
            and len(columns) != 1
        ):
            raise ValueError(f"{self.operation} requires one column")
        if self.case not in {"preserve", "lower", "upper", "casefold"}:
            raise ValueError("Unsupported text normalization")
        if self.flags not in {"", "ignorecase"}:
            raise ValueError("flags must be empty or ignorecase")
        if type(self.group) is not int or self.group < 0:
            raise ValueError("group must be a nonnegative integer")
        if self.operation in {"capture", "capture_integer", "match"}:
            if type(self.pattern) is not str:
                raise TypeError("pattern must be text")
            compiled = re.compile(self.pattern)
            if self.group > compiled.groups:
                raise ValueError("Capture group is not in the pattern")
        elif self.pattern is not None or self.group != 0 or self.flags:
            raise ValueError("Pattern options require a capture or match operation")
        if self.operation != "normalize" and self.case != "preserve":
            raise ValueError("case requires normalize")
        if self.operation != "lookup" and (self.values or self.default is not None):
            raise ValueError("values/default require lookup")
        if self.operation == "format":
            if type(self.template) is not str:
                raise TypeError("format requires template")
            for _, key, spec, conversion in Formatter().parse(self.template):
                if key is not None and (key not in columns or spec or conversion):
                    raise ValueError("Templates allow only declared plain field names")
        elif self.template is not None:
            raise ValueError("template requires format")
        object.__setattr__(self, "columns", columns)
        object.__setattr__(self, "values", _structured.freeze_mapping(self.values))
        # Evidence payloads cannot be arbitrary mutable structured declarations.
        from rangekeeper.graph.workflow.ingestion._encoding import encode

        for value in (*self.values.values(), self.default):
            encode(value)

    @classmethod
    def from_mapping(cls, value):
        """Turns a configuration declaration into the same immutable policy used by
        direct Python callers, preserving one interpretation contract.
        """
        if not isinstance(value, Mapping):
            raise TypeError("TransformSpec requires a mapping")
        return cls(**dict(value))

    def to_mapping(self):
        """Exposes effective options for the operation record so an interpretation
        can be inspected and replayed.
        """
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


def transform(
    evidence: Evidence[Table],
    *,
    specifications: Mapping[str, TransformSpec],
    settings: Claim[str] | None = None,
    name: str | None = None,
) -> Outcome[Evidence[Table]]:
    """Adds interpreted observations while keeping source columns and their Claims
    intact. The operation can be used without YAML or workflow, and downstream
    graph mapping can follow its derivation.
    """
    if not isinstance(evidence, Evidence) or not isinstance(evidence.data, Table):
        raise TypeError("transform requires Evidence[Table]")
    if not isinstance(specifications, Mapping):
        raise TypeError("specifications must be a mapping")
    specs = dict(specifications)
    for column, spec in specs.items():
        if type(column) is not str or not column or not isinstance(spec, TransformSpec):
            raise TypeError("specifications must map column names to TransformSpec")
    if settings is not None and (
        not isinstance(settings, Claim) or type(settings.value) is not str
    ):
        raise TypeError("settings must be Claim[str]")
    output_name = evidence.name if name is None else name
    tabular._text(output_name, "name")

    def execute(operation: Operation):
        columns = list(evidence.data.columns)
        for output, spec in specs.items():
            if output in columns:
                raise _Failure("output_collision", f"Column already exists: {output}")
            if set(spec.columns) - set(columns):
                raise _Failure("missing_column", f"Missing inputs for {output}")
            columns.append(output)
        claims = dict(evidence.claims)
        issues = list(evidence.issues)
        token = operation_fingerprint(operation)
        for row in evidence.data.rows:
            for output, spec in specs.items():
                keys = tuple(("rows", str(row.id), c) for c in spec.columns)
                parents = tuple(dict.fromkeys(claims[k].id for k in keys))
                by_id = {claims[k].id: claims[k] for k in keys}
                upstream = tuple(by_id[k] for k in parents)
                values = (
                    [c.value for c in upstream]
                    if len(upstream) == len(keys)
                    else [claims[k].value for k in keys]
                )
                value, reason = _interpret(spec, values)
                key = ("rows", str(row.id), output)
                claims[key] = Claim.derived(
                    value,
                    from_claims=upstream + (() if settings is None else (settings,)),
                    method=operation.method,
                    id=uuid5(NAMESPACE_URL, token + repr(key)),
                )
                # Keep all source explanations and expose unavailable inputs at the new address.
                if value is None:
                    for issue in tuple(issues):
                        if any(any(k[: len(s)] == s for s in issue.at) for k in keys):
                            changed = replace(issue, at=(key,))
                            issues.append(changed)
                    issues.append(
                        Issue(
                            rule_id=output,
                            code=reason or "unavailable_input",
                            severity=IssueSeverity.WARNING,
                            message={
                                "conflicting_values": "Available observations disagree",
                                "no_match": "Text does not match the declared pattern",
                                "unknown_label": "Label has no declared interpretation",
                                "unavailable_input": "Required observation is unavailable",
                            }.get(
                                reason, reason or "Required observation is unavailable"
                            ),
                            at=(key,),
                            related_claims=upstream,
                        )
                    )
        return tabular._output(
            name=output_name,
            columns=columns,
            row_ids=tabular._row_ids(evidence.data),
            claims=claims,
            issues=issues,
        )

    return _invoke(
        Method(code="rk.tabular.transform", version="2"),
        {
            "name": output_name,
            "specifications": tuple((k, v.to_mapping()) for k, v in specs.items()),
            "settings": None if settings is None else str(settings.id),
        },
        {"evidence": fingerprint(evidence), **settings_inputs(settings)},
        execute,
    )


def _interpret(spec, values):
    op = spec.operation
    if op == "fallback":
        return next((v for v in values if v is not None), None), "unavailable_input"
    if op == "agreement":
        available = [v for v in values if v is not None]
        if not available:
            return None, "unavailable_input"
        return (
            (available[0], None)
            if all(
                type(v) is type(available[0]) and v == available[0] for v in available
            )
            else (None, "conflicting_values")
        )
    if any(v is None for v in values):
        return None, "unavailable_input"
    value = values[0]
    if op == "format":
        return spec.template.format_map(dict(zip(spec.columns, values))), None
    if type(value) is not str:
        return None, "Expected text observation"
    if op == "normalize":
        text = value.strip()
        return (text if spec.case == "preserve" else getattr(text, spec.case)()), None
    if op == "lookup":
        result = spec.values.get(value, spec.default)
        return result, "unknown_label" if result is None else None
    match = re.fullmatch(spec.pattern, value, re.IGNORECASE if spec.flags else 0)
    if op == "match":
        return match is not None, None
    if match is None:
        return None, "no_match"
    result = match.group(spec.group)
    if op == "capture_integer" and result is not None:
        # Conversion is confined to a declared capture; NumberSpec remains strict.
        if re.fullmatch(r"[+-]?\d+", result) is None:
            return None, "Capture is not an integer"
        return int(result), None
    return result, None
