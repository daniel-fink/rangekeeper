"""Write the 1.0.0a2 samples with the published 1.0.0a2 package.

The Model has a query Expression whose Filter has a classification and a Label
Criterion: the two fields whose meaning #121 changed. From the repository root:

    uv run --isolated --no-project --python 3.13 \
        --with "rangekeeper[bundle]==1.0.0a2" \
        python tools/upgrade/tests/samples/1.0.0a2/build.py
"""

from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

import rangekeeper
from rangekeeper import Model
from rangekeeper.io import bundle
from rangekeeper.io import json as json_codec

HERE = Path(__file__).parent
NAMESPACE = UUID("6f1c8f8e-4b8e-4c55-9d0c-1a2a3a4a5a6a")


def uid(name: str) -> str:
    """Return a fixed UUID for a sample name."""
    return str(uuid5(NAMESPACE, name))


def classification(code: str, parent: str | None = None) -> dict[str, Any]:
    """Return a Classification with an optional parent."""
    return {
        "id": uid(code),
        "code": code,
        "name": code,
        **({} if parent is None else {"parent": uid(parent)}),
    }


def entity(code: str, kind: str, use: str) -> dict[str, Any]:
    """Return an Entity with a Classification and a "use" Label."""
    label = {"id": uid(code + "/use"), "key": "use", "classifications": [uid(use)]}
    return {
        "id": uid(code),
        "code": code,
        "classification": uid(kind),
        "characteristics": {"labels": [label]},
    }


def model() -> Model:
    """Return a Model whose query Filter matches exactly in 1.0.0a2."""
    query = {
        "starting_at": uid("site"),
        "filter": {
            "classification": uid("floor"),
            "labels": [{"key": "use", "classification": uid("hotel")}],
        },
        "projection": {"kind": "entity"},
        "duplicates": "distinct",
    }
    taxonomies = [
        {
            "id": uid("kinds"),
            "code": "kinds",
            "name": "Kinds",
            "classifications": [
                classification("floor"),
                classification("podium", "floor"),
            ],
        },
        {
            "id": uid("uses"),
            "code": "uses",
            "name": "Uses",
            "classifications": [
                classification("hotel"),
                classification("suite", "hotel"),
            ],
        },
    ]
    return Model.from_data(
        {
            "metadata": {
                "id": uid("model"),
                "schema_version": "1.0.0",
                "name": "Filters that 1.0.0a2 matched exactly",
            },
            "definitions": {"taxonomies": taxonomies},
            "system": {
                "entities": [
                    entity("site", "floor", "hotel"),
                    entity("level_1", "floor", "hotel"),
                    entity("level_2", "podium", "suite"),
                ],
                "formulations": [
                    {
                        "id": uid("formulation"),
                        "expressions": [
                            {"id": uid("query"), "kind": "query", "query": query}
                        ],
                    }
                ],
            },
        }
    )


def main() -> None:
    """Write model.json and the Bundle next to this script."""
    assert rangekeeper.__version__ == "1.0.0a2", rangekeeper.__version__
    sample = model()
    json_codec.write(document=sample, path=HERE / "model.json")
    bundle.write(root=HERE / "bundle", model=sample)


if __name__ == "__main__":
    main()
