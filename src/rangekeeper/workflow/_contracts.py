"""Internal contracts for RK-owned operation registrations, not a plugin API."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any
from uuid import UUID

from rangekeeper.workflow.operation import Outcome
from rangekeeper.workflow.evidence import Claim, Evidence, Source, fingerprint

from rangekeeper.workflow._declarations import fields, plain, text


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

    @classmethod
    def from_evidence(cls, value: Evidence) -> "Produced":
        """Retain the exact Evidence and its fingerprint, without inventing a native Source."""
        return cls(value, fingerprint(value))


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
    repeated_inputs: tuple[str, ...] = ()
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
        parser = getattr(self.request_type, "from_mapping", None)
        return parser(data) if parser is not None else self.request_type(**data)

    def dependencies(self, request: Any) -> tuple[tuple[str, str], ...]:
        return tuple(
            (name, kind)
            for field, kind in self.inputs
            for name in (
                getattr(request, field)
                if field in self.repeated_inputs
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
