"""Internal contracts for RK-owned operation registrations, not a plugin API."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any
from uuid import UUID

from rangekeeper.graph.operation import Outcome
from rangekeeper.graph.provenance import Claim, Source

from ._declarations import fields, plain, text


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Only ambient inputs an operation needs; no mutable runner state."""

    input_root: Path
    namespace: UUID
    settings: Claim[str]
    name: str


@dataclass(frozen=True, slots=True)
class Produced:
    """Native value and its declared audit identity, kept outside the value model."""

    value: object
    fingerprint: str
    source: Source | None = None


@dataclass(frozen=True, slots=True)
class OperationDeclaration:
    """Co-locate parsing, dependencies, execution and audit policy for one operation.

    Registrations are supplied by RK code. Configuration cannot register handlers.
    Native outputs need no shared base class and are never forced into a table.
    """

    request_type: type[Any]
    execute: Callable[[Any, Mapping[str, Any], ExecutionContext], Outcome]
    describe: Callable[[Any], Produced]
    properties: Callable[[], Mapping[str, object]]
    inputs: tuple[tuple[str, str], ...] = ()
    output: str = "table"
    policy_type: type[Any] | None = None
    policy_field: str = "specification"
    modules: tuple[str, ...] = ()
    dependencies_used: tuple[str, ...] = ()
    inspect_input: Callable[[Any, Path], Mapping[str, object]] | None = None

    def parse(self, value: Mapping[str, object]) -> Any:
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

    def dependencies(self, request: Any) -> tuple[tuple[str, str], ...]:
        return tuple(
            (name, kind)
            for field, kind in self.inputs
            for name in (
                getattr(request, field)
                if field == "inputs"
                else (getattr(request, field),)
            )
        )

    def parameters(self, request: Any) -> dict[str, object]:
        return {
            f.name: plain(getattr(request, f.name)) for f in dataclass_fields(request)
        }


@dataclass(frozen=True, slots=True)
class SourceCheckDeclaration:
    """A native source check with declared dependencies and strict field validation."""

    inputs: tuple[tuple[str, str], ...]
    evaluate: Callable[[Mapping, Mapping], tuple]
    modules: tuple[str, ...] = ()
    dependencies_used: tuple[str, ...] = ()

    def validate(self, spec, seen):
        required = {"id", "operation", *(name for name, _ in self.inputs)}
        fields(spec, required, required)
        for value in spec.values():
            text(value)
        for field, kind in self.inputs:
            if seen.get(spec[field]) != kind:
                raise ValueError(f"Source check expects {kind} input {spec[field]}")
