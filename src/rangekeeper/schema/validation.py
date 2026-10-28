"""Structural validation against packaged, closed LinkML-derived schemas."""

import json
import re
from collections.abc import Mapping
from copy import deepcopy
from functools import cache, lru_cache
from importlib.resources import files
from types import MappingProxyType

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.protocols import Validator
from jsonschema.validators import extend

from rangekeeper.shared.codes import Code
from rangekeeper.shared.diagnostics import Issue, ValidationReport


@lru_cache(maxsize=1)
def _artifacts():
    root = files(__package__)
    return tuple(
        json.loads(root.joinpath(name).read_text(encoding="utf-8"))
        for name in ("schema.json", "slots.json", "manifest.json")
    )


def schema_for(kind: str) -> dict:
    """Return a detached schema for one class, including shared definitions."""
    schema = _artifacts()[0]
    if kind not in schema["$defs"]:
        raise KeyError(kind)
    return {**deepcopy(schema), "$ref": f"#/$defs/{kind}"}


@cache
def _slot_map(kind: str):
    """Share immutable generated slot metadata inside record access and traversal.

    A read of a UUID or child record must not copy the whole class declaration.
    The public slots_for function still returns a detached, editable dictionary.
    """
    from rangekeeper.schema.runtime import _freeze

    return _freeze(_artifacts()[1][kind])


def slots_for(kind: str) -> dict:
    """Return a detached, editable copy of a kind's generated slot metadata."""
    return deepcopy(_artifacts()[1][kind])


def document_version(kind: str) -> str:
    """Return the packaged document version for a record kind."""
    return str(_artifacts()[2]["document_versions"][kind])


def supports_version(version: object, current: str) -> bool:
    """Return whether a reader of format ``current`` reads ``version``.

    A reader reads every format with its major version, up to its own version
    (ADR-017). The packaged versions come from ``document_version``.
    """

    def parse(text: object) -> tuple[int, int, int] | None:
        if not isinstance(text, str) or not re.fullmatch(r"\d+\.\d+\.\d+", text):
            return None
        major, minor, patch = (int(part) for part in text.split("."))
        return major, minor, patch

    found, reader = parse(version), parse(current)
    if found is None or reader is None:
        return False
    return found[0] == reader[0] and found <= reader


def _prepare_local_validators(schema: dict):
    """Prepare the packaged single-scope reference graph, or decline it.

    Only the reference dispatch changes. All assertion keywords, error creation,
    and format checks remain with jsonschema. A future resource scope, reference
    form, or root assertion uses the unmodified validator instead.
    """
    if set(schema) - {"$defs", "$id", "$schema"}:
        return None
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict) or not all(
        isinstance(name, str)
        and name
        and not any(char in name for char in "/~%")
        and isinstance(definition, dict)
        for name, definition in definitions.items()
    ):
        return None
    references = {f"#/$defs/{name}" for name in definitions}
    pending = list(definitions.values())
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "$ref":
                    if not isinstance(child, str) or child not in references:
                        return None
                elif key.startswith("$"):
                    # This deliberately also declines such keys in annotations.
                    # Never reinterpret another resource or dialect as this root.
                    return None
                pending.append(child)
        elif isinstance(value, list):
            pending.extend(value)

    # Keep our schema copy private; schema_for still returns independent copies.
    schema = deepcopy(schema)
    prepared: Mapping[str, Validator] = {}
    original_ref = Draft202012Validator.VALIDATORS["$ref"]

    def local_ref(validator, reference, instance, subschema):
        target = prepared.get(reference)
        if target is None:
            yield from original_ref(validator, reference, instance, subschema)
        else:
            yield from target.iter_errors(instance)

    prepared_class = extend(Draft202012Validator, {"$ref": local_ref})
    root = prepared_class(
        schema, format_checker=FormatChecker(formats=["date", "date-time"])
    )
    # Public evolve retains the root's resolution scope. No definition has its
    # own scope or dialect, as checked above. Populate all targets before use so
    # recursive definitions share validators without recursive schema expansion.
    prepared = MappingProxyType(
        {
            f"#/$defs/{name}": root.evolve(schema=definition)
            for name, definition in schema["$defs"].items()
        }
    )
    return MappingProxyType(
        {name: prepared[f"#/$defs/{name}"] for name in schema["$defs"]}
    )


@lru_cache(maxsize=1)
def _prepared_validators():
    return _prepare_local_validators(_artifacts()[0])


@cache
def _validator(kind: str):
    if kind not in _artifacts()[0]["$defs"]:
        raise KeyError(kind)
    prepared = _prepared_validators()
    if prepared is not None:
        return prepared[kind]
    return Draft202012Validator(
        schema_for(kind), format_checker=FormatChecker(formats=["date", "date-time"])
    )


def validate(kind: str, data: object) -> ValidationReport:
    """Validate a detached JSON-compatible value without mutating it."""
    from rangekeeper.schema.runtime import copy_json

    try:
        data = copy_json(data)
    except (TypeError, ValueError) as error:
        return ValidationReport((Issue(Code.STRUCTURE_JSON, str(error)),))
    return _validate_json(kind, data)


def _validate_json(kind: str, data: object) -> ValidationReport:
    """Check an already detached JSON tree at the internal record boundary."""
    issues = []
    for schema_error in _validator(kind).iter_errors(data):
        path = "".join(
            "/" + str(part).replace("~", "~0").replace("/", "~1")
            for part in schema_error.absolute_path
        )
        code = _structure_code(schema_error.validator)
        issues.append(
            Issue(
                code,
                schema_error.message,
                path=path,
                # A keyword without its own code keeps its name as a field.
                values=(
                    {"keyword": schema_error.validator}
                    if code is Code.STRUCTURE
                    else None
                ),
            )
        )
    return ValidationReport(tuple(issues))


def _structure_code(keyword: object) -> Code:
    """Return the code of a failed JSON Schema keyword."""
    try:
        return Code(f"structure.{keyword}")
    except ValueError:
        return Code.STRUCTURE
