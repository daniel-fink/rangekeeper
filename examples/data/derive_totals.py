"""Derive the stabilised-year totals of the mixed-use property.

Usage, from the repository root:

    python examples/data/derive_totals.py          # write the totals file
    python examples/data/derive_totals.py --check  # fail if the file differs

The script writes ``mixed_use_property/totals_2032.json`` from three files of the
data package: ``inventory.csv`` (the 33 floors), ``assumptions.json`` (rates by
use) and ``development.json`` (the plan). Each total has its units and its
origin. After a change, update the file's ``bytes`` and ``sha256`` in
``manifest.json``. Walkthrough lesson 02 loads the file with
``helpers.load_property(year=2032)``. The script uses only the standard library.

- Lettable area: floor GFA of the use times the use's efficiency.
- Rent: the 2027 rent of the use, grown at its annual income growth rate to the
  year, on the plan's one growth calendar.
- Vacancy: the use's vacancy, in percent. Parking earns no rent, so it has no
  area, rent or vacancy total.
- Operating cost: a positive amount. Floor GFA times the floor OPEX rate, plus
  perimeter times floor-to-floor height times the facade OPEX rate, for every
  floor of every use, grown at the annual OPEX growth rate to the year.
- Works cost: floor GFA times the construction rate of the use, plus the soft
  cost and contingency fractions of that hard cost, plus the construction
  finance allowance. The plan includes the allowance in the SFFA cost.
"""

import csv
import json
import sys
from math import fsum
from pathlib import Path

DATA = Path(__file__).resolve().parent / "mixed_use_property"
YEAR = 2032
USES = ("hotel", "residential", "retail", "parking")
RENTED = USES[:-1]


def floors() -> list[dict[str, str]]:
    """Return the 33 floor rows of the inventory, each with a known use."""
    with (DATA / "inventory.csv").open(newline="", encoding="utf-8") as file:
        rows = [row for row in csv.DictReader(file) if row["classification"] == "floor"]
    if len(rows) != 33 or any(row["effective_use"] not in USES for row in rows):
        raise ValueError("The inventory must have 33 floors, each with a known use")
    return rows


def gfa(rows: list[dict[str, str]], use: str) -> float:
    """Return the floor GFA of one use, in square metres."""
    return fsum(float(row["gfa_m2"]) for row in rows if row["effective_use"] == use)


def total(magnitude: float, units: str, origin: str) -> dict[str, object]:
    """Return one total as JSON content."""
    return {"magnitude": magnitude, "units": units, "origin": origin}


def derive(year: int = YEAR) -> dict[str, object]:
    """Return the totals file content for one stabilised ``year``."""
    assumptions = json.loads((DATA / "assumptions.json").read_text(encoding="utf-8"))
    plan = json.loads((DATA / "development.json").read_text(encoding="utf-8"))
    if not plan["stabilised_year"] <= year < int(plan["horizon_end_exclusive"][:4]):
        raise ValueError(f"{year} is not a stabilised year of the plan")
    years = year - int(plan["base_date"][:4])
    uses = assumptions["use_assumptions"]
    rows = floors()
    opex = fsum(
        float(row["gfa_m2"])
        * -uses[row["effective_use"]]["floor_opex_AUD_per_m2_per_year"]
        + float(row["perimeter_m"])
        * float(row["ftf_m"])
        * -uses[row["effective_use"]]["facade_opex_AUD_per_m2_per_year"]
        for row in rows
    )
    growth = assumptions["annual_opex_growth"]
    rates = plan["construction_AUD_per_m2"]
    soft = plan["soft_cost_fraction_of_hard_cost"]
    contingency = plan["contingency_fraction_of_hard_cost"]
    finance = plan["construction_finance_allowance_AUD"]
    works = fsum(gfa(rows, use) * rates[use] for use in USES) * (1 + soft + contingency)
    totals = {
        "works_cost": total(
            works + finance,
            "AUD",
            f"GFA × construction rate by use, + {soft:.0%} soft costs "
            f"+ {contingency:.0%} contingency, + {finance / 1e6:g} million AUD "
            "finance allowance",
        ),
        "operating_cost": total(
            opex * (1 + growth) ** years,
            "AUD pa",
            f"Floor and facade OPEX of all uses, grown {growth:.1%} pa "
            f"for {years} years",
        ),
    }
    for use in RENTED:
        item = uses[use]
        rent = item["initial_rent_AUD_per_m2_per_year"]
        rent_growth = item["annual_income_growth"]
        totals[f"{use}_area"] = total(
            gfa(rows, use) * item["efficiency"],
            "sqm",
            f"inventory.csv GFA × efficiency {item['efficiency']:g}",
        )
        totals[f"{use}_rent"] = total(
            rent * (1 + rent_growth) ** years,
            "AUD per sqm pa",
            f"{rent:g} AUD per sqm pa, grown {rent_growth:.1%} pa for {years} years",
        )
        totals[f"{use}_vacancy"] = total(item["vacancy"] * 100, "%", "assumptions.json")
    return {
        "description": f"Totals of the mixed-use property in the stabilised year "
        f"{year}. Derived by examples/data/derive_totals.py; recreate the file, "
        "do not edit it by hand.",
        "year": year,
        "from": ["inventory.csv", "assumptions.json", "development.json"],
        "totals": totals,
    }


def text(year: int = YEAR) -> str:
    """Return the totals file text, as the script writes it."""
    return json.dumps(derive(year), indent=2, ensure_ascii=False) + "\n"


def main(arguments: list[str]) -> int:
    """Write the totals file, or with ``--check`` compare it with a new derivation."""
    path = DATA / f"totals_{YEAR}.json"
    if arguments == ["--check"]:
        if path.read_text(encoding="utf-8") != text():
            print(f"{path.name} differs; run this script again", file=sys.stderr)
            return 1
        return 0
    if arguments:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    path.write_text(text(), encoding="utf-8", newline="\n")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
