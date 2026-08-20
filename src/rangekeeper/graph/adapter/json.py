from __future__ import annotations

import json as json_library
from collections.abc import Mapping
from os import PathLike
from pathlib import Path

from ..materialization import Record, Snapshot
from .errors import AdapterEncodingError


def dumps(snapshot: Snapshot, *, indent: int | None = None) -> str:
    """Encode a Snapshot as deterministic JSON text."""
    if not isinstance(snapshot, Snapshot):
        raise TypeError("snapshot must be a Snapshot")
    return json_library.dumps(
        _snapshot_data(snapshot),
        ensure_ascii=False,
        indent=indent,
        separators=None if indent is not None else (",", ":"),
        sort_keys=True,
    )


def loads(text: str) -> Snapshot:
    """Decode JSON text into a validated Snapshot."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    try:
        data = json_library.loads(text)
    except json_library.JSONDecodeError as error:
        raise AdapterEncodingError(f"invalid Snapshot JSON: {error.msg}") from error
    return _snapshot_from_data(data)


def dump(
    snapshot: Snapshot,
    path: str | PathLike[str],
    *,
    indent: int | None = 2,
) -> None:
    """Write a Snapshot to a UTF-8 JSON file."""
    Path(path).write_text(f"{dumps(snapshot, indent=indent)}\n", encoding="utf-8")


def load(path: str | PathLike[str]) -> Snapshot:
    """Read a Snapshot from a UTF-8 JSON file."""
    return loads(Path(path).read_text(encoding="utf-8"))


def _snapshot_data(snapshot: Snapshot) -> dict[str, object]:
    return {
        "schema_version": snapshot.schema_version,
        "records": [
            {
                "record_type": record.record_type,
                "identifier": record.identifier,
                "values": _plain_value(record.values),
            }
            for record in snapshot.records
        ],
    }


def _plain_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain_value(item) for item in value]
    return value


def _snapshot_from_data(data: object) -> Snapshot:
    if not isinstance(data, Mapping):
        raise AdapterEncodingError("Snapshot JSON root must be an object")
    if set(data) != {"schema_version", "records"}:
        raise AdapterEncodingError(
            "Snapshot JSON must contain exactly 'schema_version' and 'records'"
        )
    schema_version = data["schema_version"]
    if type(schema_version) is not int:
        raise AdapterEncodingError("Snapshot schema_version must be an integer")
    record_data = data["records"]
    if not isinstance(record_data, list):
        raise AdapterEncodingError("Snapshot records must be an array")

    records = []
    for index, item in enumerate(record_data):
        if not isinstance(item, Mapping):
            raise AdapterEncodingError(f"Snapshot record {index} must be an object")
        if set(item) != {"record_type", "identifier", "values"}:
            raise AdapterEncodingError(
                f"Snapshot record {index} must contain exactly record_type, "
                "identifier, and values"
            )
        try:
            records.append(
                Record(
                    record_type=item["record_type"],
                    identifier=item["identifier"],
                    values=item["values"],
                )
            )
        except (TypeError, ValueError) as error:
            raise AdapterEncodingError(
                f"Snapshot record {index} is invalid: {error}"
            ) from error
    try:
        return Snapshot(schema_version=schema_version, records=tuple(records))
    except (TypeError, ValueError) as error:
        raise AdapterEncodingError(f"Snapshot JSON is invalid: {error}") from error
