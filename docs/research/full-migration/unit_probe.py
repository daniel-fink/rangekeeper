"""Reproduce the unit path used by legacy Stream.product without resampling.

Run from src with the recorded scalar runtime. This probe calls the same
multiply_units/remove_dimension helpers as Stream.product, using a fresh Pint
registry. It does not test Stream alignment, mutate production code or change
the legacy unit registry. Examples distinguish time coordinates from units.
"""

import importlib.metadata
import json
import math
from pathlib import Path
import sys

import pint

from rangekeeper.measure import multiply_units, remove_dimension


def main():
    units = pint.UnitRegistry()
    units.define("AUD = [currency_AUD]")
    cases = {
        "factor_times_monthly_rent": [units.dimensionless, units.AUD / units.month],
        "price_times_area": [units.AUD / units.meter**2 / units.month, units.meter**2],
        "rent_times_month_duration": [units.AUD / units.month, units.month],
        "two_rates": [units.meter / units.second, units.meter / units.second],
        "factor_times_recorded_amount": [units.dimensionless, units.AUD],
    }
    results = []
    for name, terms in cases.items():
        product = multiply_units(terms, registry=units)
        try:
            reduced = str(remove_dimension(units.Quantity(1, product), "[time]", units).units)
        except NotImplementedError as error:
            reduced = f"{type(error).__name__}: {error}"
        results.append({"case": name, "ordinary_product_units": str(product),
                        "legacy_product_units": reduced})
    # Check dimensional reasoning independently of the legacy reduction helper.
    assert math.isclose((1.1 * units.Quantity(100, "AUD/month")).to("AUD/month").magnitude, 110)
    assert (units.Quantity(100, "AUD/month") * units.Quantity(2, "month")).to("AUD").magnitude == 200
    report = {
        "command": "PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-scalar-runtime/bin/python ../docs/research/full-migration/unit_probe.py",
        "cwd": str(Path.cwd()), "python": sys.version,
        "versions": {name: importlib.metadata.version(name) for name in ("pint", "pandas")},
        "scope": "Unit helpers only; no full Stream or Polars execution benchmark",
        "cases": results,
        "explicit_two_month_amount": str(units.Quantity(100, "AUD/month") * units.Quantity(2, "month")),
    }
    path = Path(__file__).with_name("unit-probe.json")
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
