"""Explicit upgrades for discovered layout profiles; no implicit format guessing."""

from copy import deepcopy
from uuid import UUID
from rangekeeper.model import Model


def upgrade_profile(profile: dict, *, model: Model) -> dict:
    """Return a v3 profile bound to canonical classification IDs and Value keys.

    Old measurement selectors use their Measure code as the owner-local key.
    Their declared Measure supplies explicit comparison units. Missing or
    ambiguous definitions raise ValueError; neither input is mutated.
    """
    result = deepcopy(profile)
    version = result.get("schema")
    if version not in {"rk-layout-profile-v1", "rk-layout-profile-v2"}:
        raise ValueError("Only layout profiles v1/v2 can be upgraded")
    definitions = model.definitions
    classes = (
        [c for t in (definitions.taxonomies or ()) for c in (t.classifications or ())]
        if definitions
        else []
    )

    def identity(code):
        matches = [c for c in classes if c.code == code or str(c.id) == code]
        if len(matches) != 1:
            raise ValueError(f"Unknown or ambiguous classification: {code}")
        return str(matches[0].id)

    result["grid_classifications"] = [
        identity(c) for c in result["grid_classifications"]
    ]
    order = result["stack_order"]
    order["classification"] = identity(order["classification"])
    order["key"] = order.pop("feature")
    order["source"] = "property"
    for signal in result["signals"]:
        if signal["source"] == "feature":
            signal["source"] = "property"
        elif signal["source"] == "measurement":
            measures = [
                m
                for m in ((definitions.measures or ()) if definitions else ())
                if m.code == signal["key"]
            ]
            if len(measures) != 1:
                raise ValueError(f"Unknown or ambiguous Measure: {signal['key']}")
            signal.update(source="quantity", units=measures[0].units)
    if version.endswith("v1"):
        result["policy"] = {
            k: result.pop(k) for k in ("canvas", "footprints", "weights")
        }
        result["policy"]["spacing"] = {"padding": 16, "header": 28, "gap": 12}
    result.update(schema="rk-layout-profile-v3", preset="stacked-compact-v1")
    return result
