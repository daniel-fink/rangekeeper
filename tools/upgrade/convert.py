"""Convert one document of an earlier release to the current formats, as data.

Each release in `RELEASES` names the stored formats it writes:

- **0.x**: a Model 0.7.0 or 0.8.0, a Specification 0.7.0 or a Run 0.4.0, the
  formats that the 0.9 and 0.10 lines and 1.0.0a1 write. The conversion changes
  `metadata.schema_version` to the 1.0.0 document version (#118); the Period and
  Span fields `start_inclusive` and `end_exclusive` to `start` and `end` (#119);
  and a magnitude in ISO 4217 currency units to the canonical text of its amount,
  at 15 significant digits (#117, ADR-023).
- **1.0.0a2**: a Model, Specification or Run 1.0.0 that 1.0.0a2 writes. The
  format version stays 1.0.0.

From both, a query Filter classification and each Label Criterion get
`exclusive: true`. Both releases matched them exactly; since #121 they also
match sub-types unless `exclusive` is true (#386).

A 1.0.0 document does not say which release wrote it, so the caller names the
release. Identities, lineage and every other field stay the same. The renames
of Python names in `tools/codemod/rename_map.yaml` change code, not data; the
codemod applies them.
"""

import json
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any, NamedTuple

from rangekeeper.io._amounts import amounts
from rangekeeper.money import to_amount
from rangekeeper.schema.validation import document_version
from rangekeeper.shared.amounts import text

Data = Mapping[str, Any]
Meta = Mapping[str, Any]


class ConversionError(ValueError):
    """A document that this tool cannot convert."""


class Release(NamedTuple):
    """The stored formats of one earlier release."""

    slots: Mapping[str, Mapping[str, Meta]]
    """The slot map that the release writes, to find records at every depth."""
    digest: str
    """The SHA-256 of the slot map: the schema pin of the release's Bundles."""
    versions: Mapping[str, tuple[str, ...]]
    """The document formats that the release writes, by root kind."""
    renamed: Mapping[str, Mapping[str, str]]
    # The fields of each record kind that hold records with no current form.
    retired: Mapping[str, tuple[str, ...]]
    """Fields that the current formats name otherwise, by record kind."""


def _release(
    slots: str,
    *,
    versions: Mapping[str, tuple[str, ...]],
    renamed: Mapping[str, Mapping[str, str]],
    retired: Mapping[str, tuple[str, ...]],
) -> Release:
    """Return a release with the slot map in the file ``slots`` beside this module."""
    content = Path(__file__).with_name(slots).read_bytes()
    return Release(
        json.loads(content), sha256(content).hexdigest(), versions, renamed, retired
    )


RELEASES = {
    # 1.0.0a1 is the last release that writes the 0.x formats.
    "0.x": _release(
        "legacy_slots.json",
        versions={
            "Model": ("0.7.0", "0.8.0"),
            "Specification": ("0.7.0",),
            "Run": ("0.4.0",),
        },
        renamed={
            "Period": {"start_inclusive": "start", "end_exclusive": "end"},
            "Span": {"start_inclusive": "start", "end_exclusive": "end"},
        },
        retired={"Specification": ("policy",), "Report": ("outcomes",)},
    ),
    "1.0.0a2": _release(
        "alpha2_slots.json",
        versions={kind: ("1.0.0",) for kind in ("Model", "Specification", "Run")},
        renamed={},
        retired={"Specification": ("rules",), "Report": ("rule_evidence",)},
    ),
}
# Records whose Classification matched exactly in every release in RELEASES.
EXACT = ("Filter", "Criterion")


def kind_of(data: Data) -> str:
    """Return the root kind of a document from its shape."""
    if "report" in data:
        return "Run"
    if "model" in data:
        return "Specification"
    return "Model"


def _exact(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    """Keep the exact match of a Filter classification or a Label Criterion.

    No release in RELEASES writes `exclusive` (#121 adds it), so a record that
    has it comes from a later release. A Filter without a classification gets
    no `exclusive`.
    """
    if kind not in EXACT:
        return data
    if "exclusive" in data:
        raise ConversionError(
            f"a {kind} has exclusive, which the releases that this tool "
            "converts do not write; the document is already current"
        )
    if kind == "Filter" and "classification" not in data:
        return data
    return {**data, "exclusive": True}


def _records(meta: Meta, value: object, release: Release) -> object:
    """Convert the records in the value of one field."""
    (kind, *_) = [
        option["kind"]
        for option in meta["options"]
        if option["category"] in ("record", "keyed")
    ]
    if meta["mapping"] and isinstance(value, Mapping):
        return {key: _fields(kind, item, release) for key, item in value.items()}
    if meta["many"] and isinstance(value, list):
        return [_fields(kind, item, release) for item in value]
    if not meta["many"]:
        return _fields(kind, value, release)
    return value


def _holds_records(meta: Meta | None) -> bool:
    if meta is None:
        return False
    return any(o["category"] in ("record", "keyed") for o in meta["options"])


def _fields(kind: str, data: object, release: Release) -> object:
    """Convert the fields at every depth, following the release's slot map."""
    if not isinstance(data, Mapping) or kind not in release.slots:
        return data
    renamed = release.renamed.get(kind, {})
    retired = release.retired.get(kind, ())
    result = {}
    for name, value in data.items():
        # `_refuse_retired` has checked that the field holds nothing.
        if name in retired:
            continue
        meta = release.slots[kind].get(name)
        converted = (
            _records(meta, value, release)
            if _holds_records(meta) and value is not None
            else value
        )
        result[renamed.get(name, name)] = converted
    return _exact(kind, result)


def _amount(value: object, units: str, path: str) -> object:
    """Return the canonical text of a 0.x currency magnitude.

    1.0.0a2 already writes the text, so its documents do not change here.
    """
    if type(value) in (int, float):
        try:
            return text(to_amount(value))  # type: ignore[arg-type]
        except ValueError as error:
            raise ConversionError(f"{path}: {error}") from error
    return value


def _require_version(data: Data, kind: str, release: str) -> None:
    """Require a document format that ``release`` writes."""
    metadata = data.get("metadata")
    version = metadata.get("schema_version") if isinstance(metadata, Mapping) else None
    expected = RELEASES[release].versions[kind]
    if version not in expected:
        raise ConversionError(
            f"{kind} format {version!r} is not a {release} format to convert; "
            f"expected {' or '.join(expected)}"
        )


def _refuse_retired(data: Data, kind: str, release: Release) -> None:
    """Refuse a document that holds records with no current form.

    The old rule records (`RuleSet`, `Decision`, `Action`) and their evidence have no
    form in the 1.0.0 format: a current rule is a query over a window, not a list of
    dated decisions (ADR-021). The tool cannot write one from the other, and it does
    not drop what the document records.
    """
    owner = data.get("report") if kind == "Run" else data
    record = "Report" if kind == "Run" else kind
    if not isinstance(owner, Mapping):
        return
    held = [name for name in release.retired.get(record, ()) if owner.get(name)]
    if held:
        raise ConversionError(
            f"{kind} {data['metadata'].get('id')} holds {' and '.join(held)}: the old "
            "rule records have no 1.0.0 form, so the tool does not convert this "
            "document. Write each rule as a query, "
            "`rk.specification.Window(...).where(condition=...).first(otherwise=...)`, "
            "fix it by key, and solve again"
        )


def convert(data: Data, kind: str | None = None, *, release: str) -> dict[str, Any]:
    """Return the current data of one document of ``release``.

    ``release`` is a key of ``RELEASES``. The input does not change.
    """
    if release not in RELEASES:
        raise ConversionError(f"unknown release {release!r}")
    kind = kind or kind_of(data)
    if kind not in RELEASES[release].versions:
        raise ConversionError(f"unknown document kind {kind!r}")
    _require_version(data, kind, release)
    _refuse_retired(data, kind, RELEASES[release])
    result = _fields(kind, data, RELEASES[release])
    assert isinstance(result, dict)
    result["metadata"] = {
        **result["metadata"],
        "schema_version": document_version(kind),
    }
    converted = amounts(kind, result, _amount)
    assert isinstance(converted, dict)
    return converted


__all__ = ["RELEASES", "ConversionError", "Release", "convert", "kind_of"]
