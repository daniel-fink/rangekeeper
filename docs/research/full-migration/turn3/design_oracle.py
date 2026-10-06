"""Check the real design's published component flows by independent arithmetic.

This reads private files without executing declarations or invoking a solver.
The reviewed teaching constants and timing convention are explicit here. Only
counts and maximum numerical error are printed; private quantities stay local.
"""

from datetime import date
import argparse
import json
import math
from pathlib import Path
from uuid import UUID
from rangekeeper.io import json as codec
from rangekeeper.model import Model
from rangekeeper.model.content import decode
from rangekeeper.model.characteristics import value as local_value

p = argparse.ArgumentParser()
p.add_argument("output", type=Path)
a = p.parse_args()
source = codec.read("/private/tmp/rk-turn3-private/design-model.json", kind=Model)
result = json.loads(a.output.read_text())
classes = {
    c.code: c.id for t in source.definitions.taxonomies for c in t.classifications
}
objects = {
    item.id: item for item in (*source.system.entities, *source.system.assemblies)
}
parent = {}
for edge in source.system.relationships:
    if edge.classification == classes["spatiallyContains"]:
        parent.setdefault(edge.target, []).append(edge.source)


def quantity(uid, key, units):
    q = local_value(objects[uid].characteristics, key).quantity
    assert q.units == units
    return q.magnitude


def use(uid):
    choices = []
    for candidate in (uid, *parent.get(uid, ())):
        item = local_value(objects[candidate].characteristics, "use")
        if item is not None:
            choices.append(decode(item.content))
    assert choices and len(set(choices)) == 1
    return choices[0]


# Efficiency, rent, rent growth, vacancy, floor/facade OPEX, floor CAPEX.
parameters = {
    "hotel": (0.8, 750, 0.035, 0.025, -175, -50, -100),
    "retail": (0.675, 1000, 0.075, 0.075, -225, -100, -150),
    "residential": (0.75, 600, 0.055, 0.015, -125, -50, -75),
    "parking": (0.9, 0, 0, 0, -65, -25, -50),
}
keys = (
    "pgi",
    "vacancy",
    "egi",
    "floor_opex",
    "facade_opex",
    "opex",
    "floor_capex",
    "utility_capex",
    "capex",
    "noi",
    "nacf",
)
aggregate = {key: [0.0] * 11 for key in keys}
maximum = 0.0
checks = 0


def check(actual, expected):
    global maximum, checks
    assert math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-6), (
        actual,
        expected,
    )
    maximum = max(maximum, abs(actual - expected))
    checks += 1


def check_flow(value, expected):
    assert value["flow"]["units"] == "AUD"
    rows = value["flow"]["movements"]
    assert len(rows) == len(expected)
    for i, (row, amount) in enumerate(zip(rows, expected)):
        assert row["key"] == f"y{i + 1}"
        assert row["date"] == date(2001 + i, 12, 31).isoformat()
        check(row["magnitude"], amount)


contributors = set()
for form in result["system"]["formulations"]:
    name = form.get("name", "")
    if not name.startswith("Design financial / ") or name.endswith("aggregate"):
        continue
    uid = UUID(name.split(" / ")[1])
    assert uid not in contributors
    contributors.add(uid)
    values = {v["key"]: v for v in form["values"]}
    expected = {key: [] for key in keys}
    floor = objects[uid].classification == classes["floor"]
    if floor:
        efficiency, rent, growth, vacancy, floor_cost, facade_cost, capital = (
            parameters[use(uid)]
        )
        area = quantity(uid, "gfa", "meter ** 2")
        facade = quantity(uid, "perimeter", "meter") * quantity(uid, "ftf", "meter")
        check(values["facade_area"]["quantity"]["magnitude"], facade)
    else:
        rate = -1000 if objects[uid].name == "plinthplant" else -100
        volume = quantity(uid, "volume", "meter ** 3")
    for i in range(11):
        factor = 1.035**i
        capital_factor = 1.035 ** ((i + 1) // 5 - 1) if (i + 1) % 5 == 0 else 0.0
        row = {key: 0.0 for key in keys}
        if floor:
            row.update(
                pgi=area * efficiency * rent * (1 + growth) ** i,
                floor_opex=area * floor_cost * factor,
                facade_opex=facade * facade_cost * factor,
                floor_capex=area * capital * capital_factor,
            )
            row["vacancy"] = -row["pgi"] * vacancy
        else:
            row["utility_capex"] = volume * rate * capital_factor
        row.update(
            egi=row["pgi"] + row["vacancy"],
            opex=row["floor_opex"] + row["facade_opex"],
            capex=row["floor_capex"] + row["utility_capex"],
        )
        row["noi"] = row["egi"] + row["opex"]
        row["nacf"] = row["noi"] + row["capex"]
        for key in keys:
            expected[key].append(row[key])
            aggregate[key][i] += row[key]
    for key in keys:
        check_flow(values[key], expected[key])
assert len(contributors) == 36
values = {
    v["key"]: v
    for f in result["system"]["formulations"]
    if f.get("name") == "Design financial / aggregate"
    for v in f["values"]
}
for key in keys:
    check_flow(values[key], aggregate[key])
reversion = [0.0] * 9 + [aggregate["nacf"][10] / 0.05]
total = [amount + sale for amount, sale in zip(aggregate["nacf"][:10], reversion)]
discounted = [amount / 1.07 ** (i + 1) for i, amount in enumerate(total)]
for key, amounts in [
    ("reversion", reversion),
    ("total", total),
    ("discounted", discounted),
]:
    check_flow(values[key], amounts)
check(values["pv"]["quantity"]["magnitude"], sum(discounted))
print(
    json.dumps(
        {
            "status": "passed",
            "contributors": len(contributors),
            "quantity_checks": checks,
            "maximum_absolute_error": maximum,
        }
    )
)
