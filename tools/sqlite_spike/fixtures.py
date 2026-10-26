"""Small canonical and geometry fixture for the experimental storage contract."""

import json
from uuid import NAMESPACE_URL, uuid5

from package import GEOMETRY_FORMAT, encoded


def uid(name):
    return str(uuid5(NAMESPACE_URL, "rk-sqlite-spike/" + name))


def fixture():
    model = {
        "metadata": {
            "id": uid("model"),
            "schema_version": "0.7.0",
            "name": "SQLite contract probe",
        },
        "definitions": {
            "measures": [
                {"id": uid("area"), "code": "area", "name": "Area", "units": "m^2"}
            ],
            "taxonomies": [
                {
                    "id": uid("taxonomy"),
                    "code": "taxonomy",
                    "name": "Probe",
                    "classifications": [
                        {"id": uid("class"), "code": "adjacent", "name": "Adjacent"}
                    ],
                }
            ],
        },
        "system": {
            "entities": [
                {
                    "id": uid("a"),
                    "characteristics": {
                        "values": [
                            {
                                "id": uid("zero"),
                                "key": "area",
                                "kind": "measurement",
                                "measure": uid("area"),
                                "quantity": {"magnitude": -0.0, "units": "m^2"},
                            },
                            {
                                "id": uid("false"),
                                "key": "enabled",
                                "kind": "property",
                                "content": {"kind": "boolean", "text": "False"},
                            },
                            {
                                "id": uid("unresolved"),
                                "key": "unknown",
                                "kind": "property",
                            },
                            {
                                "id": uid("null"),
                                "key": "null",
                                "kind": "property",
                                "content": {"kind": "null"},
                            },
                        ]
                    },
                },
                {"id": uid("b"), "name": None, "characteristics": {"values": []}},
            ],
            "assemblies": [
                {
                    "id": uid("assembly"),
                    "name": "First",
                    "entities": [uid("a"), uid("b")],
                    "relationships": [uid("rel")],
                },
                {"id": uid("shared"), "name": "Second", "entities": [uid("a")]},
            ],
            "relationships": [
                {
                    "id": uid("rel"),
                    "source": uid("a"),
                    "target": uid("b"),
                    "classification": uid("class"),
                }
            ],
        },
        "provenance": {
            "claims": [
                {
                    "id": uid("claim"),
                    "kind": "asserted",
                    "method": {"code": "probe", "version": "1"},
                    "content": {
                        "id": uid("a"),
                        "values": [False, 0, 0.0, -0.0, None, {}, []],
                    },
                }
            ],
            "facts": [{"target": uid("zero"), "claims": [uid("claim")]}],
        },
    }
    quad = {
        "id": "quad",
        "speckle_type": "Objects.Geometry.Mesh",
        "units": "m",
        "vertices": [0, 0, 0, 2, 0, 0, 2, 2, 0, 0, 2, 0],
        "faces": [4, 0, 1, 2, 3],
    }
    transport = {"quad": encoded(quad)}
    associations = [
        {"model_revision": uid("model"), "domain_id": uid("a"), "content_id": "quad"}
    ]
    descriptor = {
        "format": GEOMETRY_FORMAT,
        "root_id": "quad",
        "units": "m",
        "coordinate_system": "local Cartesian",
    }
    return json.dumps(model), transport, associations, descriptor
