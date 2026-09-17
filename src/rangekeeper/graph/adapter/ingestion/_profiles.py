"""Trusted content profiles; no public plugin discovery or YAML registration."""

from collections.abc import Iterable
from typing import Any, Protocol, TypeVar
from uuid import UUID

from ...table import Table
from ._values import encode
from .errors import EvidenceValidationError

Key = tuple[str, ...]


T_contra = TypeVar("T_contra", contravariant=True)


class _ContentProfile(Protocol[T_contra]):
    format: str

    def validate_data(self, data: T_contra) -> None: ...
    def resolve_output(self, data: T_contra, key: Key) -> object: ...
    def validate_scope(self, data: T_contra, key: Key) -> None: ...
    def required_outputs(self, data: T_contra) -> Iterable[Key] | None: ...
    def encode_data(self, data: T_contra) -> object: ...


def _row_ids(data: Table) -> tuple[UUID, ...]:
    ids = []
    for row in data.rows:
        if row.id is None:
            raise EvidenceValidationError(
                "missing_row_ids", "Evidence requires an ID on every row"
            )
        ids.append(row.id)
    return tuple(ids)


class _TableProfile:
    format = "rk.table-evidence/v1"

    def validate_data(self, data: Table) -> None:
        _row_ids(data)
        for row in data.rows:
            for value in row.values.values():
                encode(value)

    def _row(self, data: Table, key: Key) -> int:
        try:
            identifier = UUID(key[1])
            if str(identifier) != key[1]:
                raise ValueError("Noncanonical UUID")
            return _row_ids(data).index(identifier)
        except (ValueError, IndexError) as exc:
            raise EvidenceValidationError(
                "invalid_address", "Unknown/noncanonical row ID", key=key
            ) from exc

    def validate_scope(self, data: Table, key: Key) -> None:
        if not key:
            return
        if len(key) not in (2, 3) or key[0] != "rows":
            raise EvidenceValidationError(
                "invalid_address", "Expected row or cell address", key=key
            )
        self._row(data, key)
        if len(key) == 3 and key[2] not in data.columns:
            raise EvidenceValidationError("invalid_address", "Unknown column", key=key)

    def resolve_output(self, data: Table, key: Key) -> object:
        self.validate_scope(data, key)
        if len(key) != 3:
            raise EvidenceValidationError(
                "invalid_address", "Claim must address a cell", key=key
            )
        return data.rows[self._row(data, key)].values[key[2]]

    def required_outputs(self, data: Table) -> Iterable[Key]:
        return (
            ("rows", str(uid), column)
            for uid in _row_ids(data)
            for column in data.columns
        )

    def encode_data(self, data: Table) -> object:
        return {
            "columns": data.columns,
            "rows": [
                [str(row.id), [encode(row.values[c]) for c in data.columns]]
                for row in data.rows
            ],
        }


_PROFILES: dict[type, _ContentProfile[Any]] = {Table: _TableProfile()}


def profile_for(data: object) -> _ContentProfile[Any]:
    try:
        return _PROFILES[type(data)]
    except KeyError as exc:
        raise EvidenceValidationError(
            "unsupported_content", f"No trusted profile for {type(data).__name__}"
        ) from exc
