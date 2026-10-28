"""Check that the generator rejects slots that records cannot represent.

Run in the pinned schema environment, from the repository root.
"""

import importlib.util
from pathlib import Path

from linkml_runtime.linkml_model.meta import SlotDefinition

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


def field(**annotations):
    return SlotDefinition(name="field", annotations=annotations)


assert generation.slot_annotations("Example", field()) == {"lineage": False}
assert generation.slot_annotations("Example", field(lineage=True)) == {"lineage": True}
for label, value in {
    "unknown annotation": field(other=True),
    "text annotation": field(lineage="true"),
}.items():
    try:
        generation.slot_annotations("Example", value)
    except ValueError as error:
        print(f"Rejected {label}: {error}")
    else:
        raise SystemExit(f"The generator accepted a {label}")
