"""Prepare/check public fixtures through both canonical language boundaries."""

from rangekeeper.model import ValueKind

import argparse, json
from pathlib import Path
from uuid import uuid4
from datetime import date
from rangekeeper_examples import design
from rangekeeper.model import Model, Update, System, Value
from rangekeeper.model.flux import Flow, Movement
from rangekeeper.model.content import encode
from rangekeeper.io import json as codec

p = argparse.ArgumentParser()
p.add_argument("mode", choices=["prepare", "check"])
p.add_argument("directory", type=Path)
a = p.parse_args()
if a.mode == "prepare":
    model = design.fixture()
    root = model.find_entities(
        classification=design.classification_id(model, "property")
    )[0].id
    utilities = {
        u: "cores"
        for u in design.select_contributors(model, root=root)
        if model.entity(u).name == "cores"
    }
    model = design.formulate(design.author(model, root=root, utility_kinds=utilities))
    data = model.system.to_data()
    owner = data["entities"][0]
    owner.setdefault("characteristics", {}).setdefault("values", []).extend(
        [
            Value(
                id=uuid4(),
                key="rich",
                kind=ValueKind.PROPERTY,
                content=encode(
                    {
                        "null": None,
                        "false": False,
                        "zero": 0,
                        "large": 10**40,
                        "ordered": (3, 2, 1),
                        "date": date(2026, 10, 6),
                    }
                ),
            ).to_data(),
            Value(
                id=uuid4(),
                key="presence",
                kind=ValueKind.FLOW,
                measure=next(
                    m.id
                    for m in model.definitions.measures
                    if m.units == "dimensionless"
                ),
                flow=Flow(
                    units="dimensionless",
                    movements=(
                        Movement(id=uuid4(), key="omitted", date=date(2026, 1, 1)),
                        Movement(
                            id=uuid4(),
                            key="null",
                            date=date(2026, 1, 2),
                            magnitude=None,
                        ),
                        Movement(
                            id=uuid4(), key="zero", date=date(2026, 1, 3), magnitude=0
                        ),
                    ),
                ),
            ).to_data(),
        ]
    )
    # Exercise a direct Movement reference through both language validators.
    movement_id = owner["characteristics"]["values"][-1]["flow"]["movements"][0]["id"]
    data.setdefault("formulations", []).append(
        {
            "id": str(uuid4()),
            "expressions": [
                {
                    "id": str(uuid4()),
                    "kind": "reference",
                    "target": {"target": movement_id},
                }
            ],
        }
    )
    model = model.revise(Update(system=System.from_data(data)))
    a.directory.mkdir(parents=True, exist_ok=True)
    codec.write(model, a.directory / "python.json")
else:
    before = codec.read(a.directory / "python.json", kind=Model)
    after = codec.read(a.directory / "csharp.json", kind=Model)
    assert before.to_data() == after.to_data()
    print(
        "Python → C# → Python: all content, presence and ordered mathematics preserved"
    )
