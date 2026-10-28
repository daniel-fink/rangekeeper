"""Convert one 0.x document to the 1.0.0 format, as data.

The input is a Model 0.7.0 or 0.8.0, a Specification 0.7.0 or a Run 0.4.0:
the formats that the 0.9 and 0.10 lines and 1.0.0a1 write. The conversion
changes only what the 1.0.0 format changes:

- `metadata.schema_version` becomes the 1.0.0 document version (#118);
- Period and Span `start_inclusive` and `end_exclusive` become `start` and
  `end` (#119);
- `Specification.policy` becomes `rules`, and `Report.outcomes` becomes
  `rule_evidence` (policy to rule, #95);
- a magnitude in ISO 4217 currency units becomes the canonical text of its
  amount, at 15 significant digits (#117, ADR-023).

Identities, lineage and every other field stay the same. The renames of Python
names in `tools/codemod/rename_map.yaml` change code, not data; the codemod
applies them.
"""

import json
from collections.abc import Mapping
from pathlib import Path

from rangekeeper.io._amounts import amounts
from rangekeeper.money import to_amount
from rangekeeper.schema.validation import document_version
from rangekeeper.shared.amounts import text

# The slot map of 1.0.0a1, the last release that writes the 0.x formats.
LEGACY = json.loads(Path(__file__).with_name("legacy_slots.json").read_text())
SOURCES = {
    "Model": ("0.7.0", "0.8.0"),
    "Specification": ("0.7.0",),
    "Run": ("0.4.0",),
}
# Fields renamed between the 0.x and 1.0.0 formats, by legacy record kind.
FIELDS = {
    "Period": {"start_inclusive": "start", "end_exclusive": "end"},
    "Span": {"start_inclusive": "start", "end_exclusive": "end"},
    "Specification": {"policy": "rules"},
    "Report": {"outcomes": "rule_evidence"},
}


class ConversionError(ValueError):
    """A document that this tool cannot convert."""


def kind_of(data: Mapping) -> str:
    """Return the root kind of a document from its shape."""
    if "report" in data:
        return "Run"
    if "model" in data:
        return "Specification"
    return "Model"


def _fields(kind: str, data: object) -> object:
    """Rename the 0.x fields at every depth, following the legacy slot map."""
    if not isinstance(data, Mapping) or kind not in LEGACY:
        return data
    renamed = FIELDS.get(kind, {})
    result = {}
    for name, value in data.items():
        meta = LEGACY[kind].get(name)
        children = (
            [o["kind"] for o in meta["options"] if o["category"] in ("record", "keyed")]
            if meta is not None
            else []
        )
        if children and value is not None:
            child = children[0]
            if meta["mapping"] and isinstance(value, Mapping):
                value = {k: _fields(child, v) for k, v in value.items()}
            elif meta["many"] and isinstance(value, list):
                value = [_fields(child, v) for v in value]
            elif not meta["many"]:
                value = _fields(child, value)
        result[renamed.get(name, name)] = value
    return result


def _amount(value: object, units: str, path: str) -> object:
    """Return the canonical text of a 0.x currency magnitude."""
    if type(value) in (int, float):
        try:
            return text(to_amount(value))  # type: ignore[arg-type]
        except ValueError as error:
            raise ConversionError(f"{path}: {error}") from error
    return value


def convert(data: Mapping, kind: str | None = None) -> dict:
    """Return the 1.0.0 data of one 0.x document; the input does not change."""
    kind = kind or kind_of(data)
    if kind not in SOURCES:
        raise ConversionError(f"unknown document kind {kind!r}")
    metadata = data.get("metadata")
    version = metadata.get("schema_version") if isinstance(metadata, Mapping) else None
    if version not in SOURCES[kind]:
        expected = " or ".join(SOURCES[kind])
        raise ConversionError(
            f"{kind} format {version!r} is not a 0.x format to convert; "
            f"expected {expected}"
        )
    result = _fields(kind, data)
    assert isinstance(result, dict)
    result["metadata"] = {
        **result["metadata"],
        "schema_version": document_version(kind),
    }
    converted = amounts(kind, result, _amount)
    assert isinstance(converted, dict)
    return converted


__all__ = ["ConversionError", "SOURCES", "convert", "kind_of"]
