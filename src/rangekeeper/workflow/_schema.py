"""Schema assembly for the closed catalog; operations own their request fields."""

from dataclasses import MISSING


def obj(properties, required=()):
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(required),
    }


def schema():
    from ._table_operations import number_schema
    from .catalog import OPERATIONS

    string = {"type": "string", "minLength": 1}
    names = {"type": "array", "items": string}
    boolean = {"type": "boolean"}
    number = number_schema()
    result = {
        "version": 2,
        "documents": ["sources", "model", "decisions", "checks"],
        "executableContent": False,
        "operations": {
            name: obj(
                {
                    "id": string,
                    "operation": {"const": name},
                    **declaration.properties(),
                },
                ["id", "operation"]
                + [
                    key
                    for key, f in declaration.request_type.__dataclass_fields__.items()
                    if f.default is MISSING and f.default_factory is MISSING
                ],
            )
            for name, declaration in OPERATIONS.items()
        },
    }
    numeric = result["operations"]["numbers"]
    numeric["required"].remove("specifications")
    numeric["oneOf"] = [
        {"required": ["specifications"]},
        {"required": ["specifications_ref"]},
    ]
    binding = obj({"value": {}, "column": string, "evidence": string})
    binding["oneOf"] = [
        {
            "required": ["value"],
            "not": {"anyOf": [{"required": ["column"]}, {"required": ["evidence"]}]},
        },
        {"required": ["column"], "not": {"required": ["value"]}},
    ]
    condition = obj(
        {
            "binding": binding,
            "equals": {},
            "in": {"type": "array"},
            "available": boolean,
        },
        ("binding",),
    )
    condition["oneOf"] = [{"required": [key]} for key in ("equals", "in", "available")]
    measurement = obj(
        {
            "key": string,
            "kind": {"enum": ["measurement", "parameter", "decision"]},
            "integer": boolean,
            "measure": string,
            "binding": binding,
            "when": condition,
            "decisions": names,
            "evidence": {"type": "array", "items": binding},
            "on_unavailable": obj(
                {
                    "binding": binding,
                    "topic": string,
                    "explanation": string,
                }
            ),
        },
        ("key", "measure", "binding"),
    )
    result["shared_declarations"] = {
        "number_sets": {
            "type": "object",
            "additionalProperties": {"type": "object", "additionalProperties": number},
        },
        "measurement_sets": {
            "type": "object",
            "additionalProperties": {"type": "array", "items": measurement},
        },
        "measurement_use": obj(
            {"measurements_ref": string, "measurements_evidence": string},
            ("measurements_ref",),
        ),
    }
    result["operations"]["select"]["not"] = {
        "required": ["where", "row_ids"],
        "properties": {"where": {"type": "object"}, "row_ids": {"type": "array"}},
    }
    return result
