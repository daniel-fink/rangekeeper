"""Generated node checks accept exactly the nodes that jsonschema accepts.

A node check tests one record and treats each child record as valid. The
oracle validates the whole node with jsonschema; its children come from the
fixtures, so they are valid and only the node's own content can differ.
"""

from copy import deepcopy
from functools import cache
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

from rangekeeper.schema import validation
from rangekeeper.schema.checks import CHECKS
from rangekeeper.schema.index import walk_data
from rangekeeper.schema.records import _TYPES

EXAMPLES = Path(__file__).resolve().parents[2] / "examples/schema"
UUID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
PROBES = (
    None,
    True,
    0,
    -1,
    1.5,
    2.0,
    "",
    " ",
    " x",
    "x",
    "a b",
    UUID,
    UUID.upper(),
    "2026-01-31",
    "2026-02-30",
    "2026-01-31T09:30:00+11:00",
    "2026-01-31T09:30:00",
    "f" * 64,
    "unknown-kind",
    [],
    [UUID],
    ["x"],
    [None],
    {},
    {"x": "y"},
)


@cache
def oracle(kind):
    return Draft202012Validator(
        validation.schema_for(kind),
        format_checker=FormatChecker(formats=["date", "date-time"]),
    )


def documents():
    for path in sorted(EXAMPLES.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        if not isinstance(data, dict) or "metadata" not in data:
            continue
        kind = (
            "Run"
            if "report" in data
            else "Specification"
            if path.name.startswith("specification")
            else "Model"
        )
        if oracle(kind).is_valid(data):
            yield kind, data


@cache
def samples():
    """Return one or more valid nodes of each kind found in the fixtures."""
    found: dict[str, list[dict]] = {}
    for kind, data in documents():
        stack = [(kind, data)]
        while stack:
            current, node = stack.pop()
            bucket = found.setdefault(current, [])
            if len(bucket) < 4:
                bucket.append(node)
            for name, field in validation._slot_map(current).items():
                value = node.get(name)
                kinds = [
                    o["kind"]
                    for o in field["options"]
                    if o["category"] in ("record", "keyed") and o["kind"] in _TYPES
                ]
                if not kinds or value is None:
                    continue
                items = (
                    value.values()
                    if field["mapping"]
                    else value
                    if field["many"]
                    else [value]
                )
                stack += [
                    (kinds[0], child) for child in items if isinstance(child, dict)
                ]
    return found


@cache
def field_oracle(kind, name):
    schema = validation.schema_for(kind)
    part = schema["$defs"][kind]["properties"][name]
    return Draft202012Validator(
        {"$defs": schema["$defs"], **part},
        format_checker=FormatChecker(formats=["date", "date-time"]),
    )


def candidates(kind, name, depth):
    """Yield wire values for one field: child records, enum members and probes."""
    field = validation._slot_map(kind)[name]
    schema = validation.schema_for(kind)["$defs"]
    singles = []
    for option in field["options"]:
        if option["category"] in ("record", "keyed") and depth < 6:
            child = synthesize(option["kind"], depth + 1)
            if child is not None:
                singles.append(child)
        if option["category"] == "enum":
            singles += schema[option["kind"]]["enum"]
    singles += [p for p in PROBES if not isinstance(p, (list, dict))]
    if field["mapping"]:
        yield from ({"k": item} for item in singles)
    elif field["many"]:
        yield from ([item] for item in singles)
        yield []
    else:
        yield from singles


def pick(kind, name, depth):
    return next(
        (
            v
            for v in candidates(kind, name, depth)
            if field_oracle(kind, name).is_valid(v)
        ),
        None,
    )


@cache
def _synthesize(kind, depth):
    slots = validation._slot_map(kind)
    required = validation.schema_for(kind)["$defs"][kind].get("required", [])
    node = {name: pick(kind, name, depth) for name in required}
    errors = len(list(oracle(kind).iter_errors(node)))
    improved = True
    while errors and improved:
        improved = False
        for name in slots:
            for value in candidates(kind, name, depth):
                trial = {**node, name: value}
                count = len(list(oracle(kind).iter_errors(trial)))
                if count < errors:
                    node, errors, improved = trial, count, True
                    break
    return None if errors else node


def synthesize(kind, depth=0):
    """Return a valid wire node of ``kind`` built from the schema, or None."""
    return deepcopy(_synthesize(kind, depth))


def agree(kind, node):
    expected = oracle(kind).is_valid(node)
    actual = not CHECKS[kind](node)
    assert actual == expected, (kind, node)


def test_walk_data_reaches_every_sample():
    # The fixtures exercise most kinds; the probes below test each of them.
    assert len(samples()) >= 40
    assert walk_data  # Traversal order is not part of this contract.


@pytest.mark.parametrize("kind", sorted(CHECKS))
def test_node_checks_match_jsonschema(kind):
    nodes = list(samples().get(kind, ()))
    synthetic = synthesize(kind)
    if synthetic is not None:
        nodes.append(synthetic)
    assert nodes, f"no valid {kind} node"
    for node in nodes:
        agree(kind, node)
        for name in validation._slot_map(kind):
            removed = {k: v for k, v in node.items() if k != name}
            agree(kind, removed)
            record = any(
                option["category"] == "record"
                for option in validation._slot_map(kind)[name]["options"]
            )
            for probe in PROBES:
                # A node check does not look inside a child record.
                if not (record and isinstance(probe, dict)):
                    agree(kind, {**node, name: probe})
        agree(kind, {**node, "unexpected": 1})
