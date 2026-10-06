"""Structural validation against packaged, closed LinkML-derived schemas."""

from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
import json

from jsonschema import Draft202012Validator, FormatChecker

from ..diagnostics import Issue, ValidationReport


@lru_cache(maxsize=1)
def _artifacts():
    root = files(__package__)
    return tuple(
        json.loads(root.joinpath(name).read_text())
        for name in ("schema.json", "slots.json", "manifest.json")
    )


def schema_for(kind: str) -> dict:
    """Return a detached schema for one class, including shared definitions."""
    schema = _artifacts()[0]
    if kind not in schema["$defs"]:
        raise KeyError(kind)
    return {**deepcopy(schema), "$ref": f"#/$defs/{kind}"}


@lru_cache(maxsize=None)
def _slot_map(kind: str):
    """Share immutable generated slot metadata inside record access and traversal.

    A read of a UUID or child record must not copy the whole class declaration.
    The public slots_for function still returns a detached, editable dictionary.
    """
    from .._records import _freeze

    return _freeze(_artifacts()[1][kind])


def slots_for(kind: str) -> dict:
    return deepcopy(_artifacts()[1][kind])


def document_version(kind: str) -> str:
    return str(_artifacts()[2]["document_versions"][kind])


@lru_cache(maxsize=None)
def _validator(kind: str):
    return Draft202012Validator(
        schema_for(kind), format_checker=FormatChecker(formats=["date", "date-time"])
    )


def validate(kind: str, data: object) -> ValidationReport:
    """Validate a detached JSON-compatible value without mutating it."""
    from .._records import _json_copy

    try:
        data = _json_copy(data)
    except (TypeError, ValueError) as error:
        return ValidationReport((Issue("structure.json", str(error)),))
    issues = []
    for error in _validator(kind).iter_errors(data):
        path = "".join(
            "/" + str(part).replace("~", "~0").replace("/", "~1")
            for part in error.absolute_path
        )
        issues.append(Issue(f"structure.{error.validator}", error.message, path=path))
    return ValidationReport(tuple(issues))
