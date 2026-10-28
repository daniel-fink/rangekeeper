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

from rangekeeper.schema.runtime import Record
from rangekeeper.shared import pointer
from rangekeeper.shared.codes import Code
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.shared.validation import _document_id, require, require_new


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
        path = pointer.child("", *schema_error.absolute_path)
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


# Schema-directed semantic helpers. They raise ContractError through require.


def require_declarations(documents):
    """Check declaration identities through schema slots, excluding opaque payloads."""
    from rangekeeper.schema.index import walk_data

    identities = set()
    for kind, data in documents:
        for record, path in walk_data(kind, data):
            if "id" in record:
                require_new(identities, record["id"], path=path + "/id")
    return identities


def checked_record(kind, value, label, issues):
    """Retain one structurally validated record and contextualize boundary failures."""
    from rangekeeper.schema.records import _TYPES
    from rangekeeper.shared.errors import ValidationError

    if isinstance(value, Record):
        if value._kind == kind:
            return value
        issues.append(
            Issue(
                Code.STRUCTURE_KIND,
                f"expected {kind}, received {value._kind}",
                path=label,
            )
        )
        return None
    try:
        return _TYPES[kind].from_data(value)
    except ValidationError as error:
        issues.extend(
            issue.replace(document_id=_document_id(value), path=label + issue.path)
            for issue in error.report.issues
        )
    except (ValueError, TypeError) as error:
        issues.append(
            Issue(Code.STRUCTURE_JSON, str(error), _document_id(value), label)
        )
    return None


def checked(
    kind: str,
    value: Record | Mapping[str, object],
    label: str,
    issues: list[Issue],
) -> dict:
    """Expose one detached representation from the shared structural preparation."""
    record = checked_record(kind, value, label, issues)
    return record.to_data() if record is not None else {}


def validate_known_reference_types(root: Record, *, index) -> None:
    """Check locally resolvable reference types without requiring external targets.

    Partial Specifications can point outside their declaration scope. A target
    already declared locally cannot masquerade as another record kind.
    Complete Model/composition validation owns reference existence checks.
    """
    from uuid import UUID

    from rangekeeper.schema.index import walk
    from rangekeeper.schema.records import _TYPES, Movement, Reference, Value

    for record, _, path in walk(root):
        for name, field in _slot_map(record._kind).items():
            types = tuple(
                _TYPES[option["kind"]]
                for option in field["options"]
                if option["category"] == "uuid" and option["kind"] in _TYPES
            )
            if isinstance(record, Reference) and name == "target":
                types = (Value, Movement)
            if not types:
                continue
            value = getattr(record, name)
            entries = enumerate(value) if isinstance(value, tuple) else ((None, value),)
            for position, identity in entries:
                if isinstance(identity, UUID) and identity in index.records:
                    actual = index.records[identity]
                    expected = tuple(kind.__name__ for kind in types)
                    require(
                        isinstance(actual, types),
                        f"{identity} targets {actual._kind}; "
                        f"expected {', '.join(expected)}",
                        code=Code.REFERENCE_KIND,
                        targets=(identity,),
                        values={"expected": expected, "actual": actual._kind},
                        path=f"{path}/{name}"
                        + (f"/{position}" if position is not None else ""),
                    )


def _structure_code(keyword: object) -> Code:
    """Return the code of a failed JSON Schema keyword."""
    try:
        return Code(f"structure.{keyword}")
    except ValueError:
        return Code.STRUCTURE
