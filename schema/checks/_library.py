"""Locate this checkout for standalone conformance commands."""

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rangekeeper.schema.validation import schema_for

root = Path(__file__).resolve().parents[2]
manifest = json.loads((root / "src/rangekeeper/schema/manifest.json").read_text())
for source, expected in manifest["sources"].items():
    if hashlib.sha256((root / source).read_bytes()).hexdigest() != expected:
        raise RuntimeError(
            "Generated artifacts are stale; run tools/schema/generate.py"
        )


def schema_json(kind):
    return json.dumps(schema_for(kind))


def stock(value):
    """Compare magnitudes by value: stock LinkML writes the Amount-or-double union as text.

    The union's default range is string, so a native round trip writes 85.5 as
    "85.5" (ADR-023). Runtime records keep the exact wire type.
    """
    if isinstance(value, dict):
        return {
            key: Decimal(str(child))
            if key == "magnitude" and type(child) in (int, float, str)
            else stock(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [stock(child) for child in value]
    return value


def wire(value):
    """Undo the stock LinkML text magnitudes: numbers stay numbers outside currency units."""
    from rangekeeper.money import is_currency

    def number(text):
        value = Decimal(text)
        return int(value) if value == value.to_integral() else float(value)

    if isinstance(value, list):
        return [wire(child) for child in value]
    if not isinstance(value, dict):
        return value
    result = {key: wire(child) for key, child in value.items()}
    units = result.get("units")
    if not isinstance(units, str) or is_currency(units):
        return result
    if type(result.get("magnitude")) is str:
        result["magnitude"] = number(result["magnitude"])
    for movement in result.get("movements") or ():
        if isinstance(movement, dict) and type(movement.get("magnitude")) is str:
            movement["magnitude"] = number(movement["magnitude"])
    return result


def dump(record):
    """Return the JSON data of a stock LinkML record with wire-typed magnitudes."""
    from linkml_runtime.dumpers import json_dumper

    return wire(json.loads(json_dumper.dumps(record, inject_type=False)))
