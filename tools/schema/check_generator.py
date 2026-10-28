"""Check that the generator rejects slots that records cannot represent.

It also rejects a class or slot without a description.

Run in the pinned schema environment, from the repository root.
"""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "generation", Path(__file__).with_name("generate.py")
)
generation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generation)


def meta(*options, many=False):
    return dict(
        options=[{"kind": kind, "category": category} for kind, category in options],
        required=False,
        many=many,
        mapping=False,
        nullable=False,
        ordered=False,
    )


reserved = generation.reserved_names()
assert {"to_data", "from_data", "has_field"} <= reserved
cases = {
    "keyword": {"Example": {"class": meta(("string", "primitive"))}},
    "record method": {"Example": {"to_data": meta(("string", "primitive"))}},
    "generated method": {"Example": {"replace": meta(("string", "primitive"))}},
    "record union": {
        "Example": {"part": meta(("Period", "record"), ("Span", "record"))}
    },
    "enum collection": {"Example": {"kinds": meta(("ValueKind", "enum"), many=True)}},
}
for label, slots in cases.items():
    try:
        generation.check_slots(slots, reserved)
    except ValueError as error:
        print(f"Rejected {label}: {error}")
    else:
        raise SystemExit(f"The generator accepted a {label} collision")
generation.check_slots(
    {"Example": {"part": meta(("Period", "record"), ("Claim", "uuid"))}}, reserved
)
print(f"Checked {len(cases)} rejected slot shapes")

described = {"description": "An example.", "slots": {"part": "One part."}}
missing = {
    "class": {"Example": {**described, "description": None}},
    "blank class": {"Example": {**described, "description": " "}},
    "slot": {"Example": {**described, "slots": {"part": None}}},
    "blank slot": {"Example": {**described, "slots": {"part": ""}}},
}
for label, metadata in missing.items():
    try:
        generation.check_descriptions(metadata)
    except ValueError as error:
        print(f"Rejected {label} without a description: {error}")
    else:
        raise SystemExit(f"The generator accepted a {label} without a description")
generation.check_descriptions({"Example": described})
print(f"Checked {len(missing)} missing descriptions")
