"""Compare raw LinkML JSON Schema with the logically simplified packaged artifact."""

import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import time
from jsonschema import Draft202012Validator, FormatChecker
from linkml.generators.jsonschemagen import JsonSchemaGenerator
import yaml

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
spec = importlib.util.spec_from_file_location(
    "generation", Path(__file__).with_name("generate.py")
)
generation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generation)
with tempfile.TemporaryDirectory(prefix="rk-simplification-") as directory:
    directory = Path(directory)
    for path in (ROOT / "schema").glob("*.yaml"):
        shutil.copy2(path, directory / path.name)
    shutil.copy2(ROOT / "tools/schema/bundle.yaml", directory / "bundle.yaml")
    raw = json.loads(
        JsonSchemaGenerator(
            str(directory / "bundle.yaml"), top_class="Model", not_closed=False
        ).serialize()
    )
    raw = {key: raw[key] for key in ("$schema", "$id", "$defs")}
    simplified = deepcopy(raw)
    generation.simplify_conjunctions(simplified)
    cases = []
    for kind in raw["$defs"]:
        for label, value in [
            ("null", None),
            ("false", False),
            ("zero", 0),
            ("array", []),
            ("empty", {}),
            ("extra", {"unexpected": True}),
        ]:
            cases.append((kind, label, value))
    for path in (ROOT / "schema/examples").glob("*.yaml"):
        data = yaml.safe_load(path.read_text())
        if "metadata" not in data:
            continue
        kind = (
            "Run"
            if "report" in data
            else "Specification" if path.name.startswith("specification") else "Model"
        )
        cases.append((kind, path.name, data))
        for field in data:
            omitted = deepcopy(data)
            omitted.pop(field)
            cases.append((kind, path.name + "/omit/" + field, omitted))
            null = deepcopy(data)
            null[field] = None
            cases.append((kind, path.name + "/null/" + field, null))
    for value in [
        None,
        {},
        {"target": "annual_rent"},
        {"target": "00000000-0000-0000-0000-000000000001"},
        {"value": "00000000-0000-0000-0000-000000000001", "movement": "p1"},
    ]:
        cases.append(("Reference", "reference", value))
    validators = {}

    def valid(which, kind, value):
        key = which, kind
        if key not in validators:
            base = raw if which == "raw" else simplified
            validators[key] = Draft202012Validator(
                {**base, "$ref": f"#/$defs/{kind}"}, format_checker=FormatChecker()
            )
        return validators[key].is_valid(value)

    outcomes = []
    for kind, label, value in cases:
        a, b = valid("raw", kind, value), valid("simplified", kind, value)
        assert a == b, (kind, label, a, b)
        outcomes.append(dict(kind=kind, case=label, accepted=a))
    # A deep unary tree exercises the duplicated recursive allOf/anyOf route.
    node = dict(
        id="00000000-0000-0000-0000-000000000001",
        kind="quantity",
        quantity=dict(magnitude=1, units="dimensionless"),
    )
    for i in range(9):
        node = dict(
            id=f"00000000-0000-0000-0000-{i+2:012d}",
            kind="unary",
            operator="negate",
            operand=node,
        )
    timing = {}
    for which in ("raw", "simplified"):
        start = time.perf_counter()
        assert valid(which, "Expression", node)
        timing[which] = time.perf_counter() - start
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            dict(
                matching_cases=len(outcomes),
                differences=0,
                depth=9,
                timing_seconds=timing,
                outcomes=outcomes,
            ),
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            dict(matching_cases=len(outcomes), differences=0, timing_seconds=timing)
        )
    )
