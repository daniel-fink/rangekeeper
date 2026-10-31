"""Derive the base plan of the mixed-use development, at 2027 prices.

Usage, from the repository root:

    python examples/data/derive_base_plan.py          # write the base plan file
    python examples/data/derive_base_plan.py --check  # fail if the file differs

The script writes ``mixed_use_property/base_plan.json`` from three files of the
data package: ``inventory.csv`` (the 33 floors and the utilities),
``assumptions.json`` (rates by use) and ``development.json`` (the plan). Each
value has its units and its origin. After a change, update the file's ``bytes``
and ``sha256`` in ``manifest.json``. Walkthrough lesson 03 loads the file with
``helpers.load_base_plan()``. The script uses only the standard library.

The plan has three packages: the shared plinth (``shared``), Building A
(``building_a``) and Building B (``building_b``), from the ``branch`` column of
the inventory. Amounts are at 2027 prices; the lesson's equations grow them.

- Dates: the base date, the sale date, and the start and opening of each
  package, from the plan.
- Budget of a package: floor GFA times the construction rate of the use, plus
  the soft cost and contingency fractions of that hard cost. The construction
  finance allowance is not in a budget: lesson 03 calculates the loan interest.
- Income of a building: for each rented use, floor GFA times the use's
  efficiency, times its 2027 rent, times one less its vacancy. The plinth holds
  parking, which earns no rent.
- Operating cost of a package: a positive amount. Floor GFA times the floor
  OPEX rate, plus perimeter times floor-to-floor height times the facade OPEX
  rate, for each floor of the package.
- Renewal of a package: a positive amount for one five-yearly payment. Floor
  GFA times the floor capital rate, plus the volume of the package's cores or
  plant times the utility capital rate. The plinth's costs are shared: they
  are not allocated to the buildings.
- Funding: the equity and the loan limit (the plan's bridge limit).
"""

import csv
import json
import sys
from math import fsum
from pathlib import Path

DATA = Path(__file__).resolve().parent / "mixed_use_property"
USES = ("hotel", "residential", "retail", "parking")
# Each package of the plan: its key, its inventory branch and its phase name.
PACKAGES = {
    "shared": ("plinth", "Shared plinth"),
    "building_a": ("buildingA", "Building A"),
    "building_b": ("buildingB", "Building B"),
}
# The prefix of each package's value keys in lesson 03.
PREFIXES = {"shared": "shared", "building_a": "a", "building_b": "b"}


def inventory() -> list[dict[str, str]]:
    """Return the inventory rows: 33 floors with a known use, and the utilities."""
    with (DATA / "inventory.csv").open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    floors = [row for row in rows if row["classification"] == "floor"]
    if len(floors) != 33 or any(row["effective_use"] not in USES for row in floors):
        raise ValueError("The inventory must have 33 floors, each with a known use")
    return rows


def value(magnitude: float, units: str, origin: str) -> dict[str, object]:
    """Return one amount as JSON content."""
    return {"magnitude": magnitude, "units": units, "origin": origin}


def day(text: str, origin: str) -> dict[str, object]:
    """Return one date as JSON content."""
    return {"date": text, "origin": origin}


class Package:
    """The floors and utilities of one package, with the rates of the plan."""

    def __init__(self, rows: list[dict[str, str]], branch: str) -> None:
        self.floors = [
            row
            for row in rows
            if row["classification"] == "floor" and row["branch"] == branch
        ]
        self.utilities = [
            row
            for row in rows
            if row["classification"] == "utilities"
            and row["branch"] == branch
            and row["volume_m3"]
        ]

    def gfa(self, use: str) -> float:
        """Return the floor GFA of one use, in square metres."""
        return fsum(
            float(row["gfa_m2"]) for row in self.floors if row["effective_use"] == use
        )

    def uses(self) -> list[str]:
        """Return the uses of the package's floors, in the order of ``USES``."""
        return [use for use in USES if self.gfa(use) > 0]

    def floor_sum(self, rate: dict[str, float]) -> float:
        """Return the sum over floors of GFA times the rate of each floor's use."""
        return fsum(
            float(row["gfa_m2"]) * rate[row["effective_use"]] for row in self.floors
        )

    def facade_sum(self, rate: dict[str, float]) -> float:
        """Return the sum over floors of facade area times the rate of the use."""
        return fsum(
            float(row["perimeter_m"]) * float(row["ftf_m"]) * rate[row["effective_use"]]
            for row in self.floors
        )

    def volume_sum(self, rate: dict[str, float]) -> float:
        """Return the sum over utilities of volume times the rate of the utility."""
        return fsum(
            float(row["volume_m3"]) * rate[row["source_use"]] for row in self.utilities
        )


def by_use(assumptions: dict, name: str) -> dict[str, float]:
    """Return one rate of ``use_assumptions`` for each use, as a positive amount."""
    return {use: -item[name] for use, item in assumptions["use_assumptions"].items()}


def dates(plan: dict) -> dict[str, object]:
    """Return the dates of the plan that lesson 03 fixes."""
    phases = {phase["name"]: phase for phase in plan["phases"]}
    return {
        "base_date": day(plan["base_date"], "development.json base date"),
        "sale_date": day(plan["valuation"]["sale_date"], "development.json sale date"),
        "start_date": day(
            phases["Shared plinth"]["start"], "Start of the shared plinth's works"
        ),
        "b_start": day(phases["Building B"]["start"], "Start of Building B's works"),
    }


def budgets(plan: dict, packages: dict[str, Package]) -> dict[str, object]:
    """Return the land cost and the budget of each package."""
    rates = plan["construction_AUD_per_m2"]
    soft = plan["soft_cost_fraction_of_hard_cost"]
    contingency = plan["contingency_fraction_of_hard_cost"]
    found = {
        "land_cost": value(plan["land_cost_AUD"], "AUD", "development.json land cost")
    }
    for key, package in packages.items():
        hard = package.floor_sum(rates)
        found[f"{PREFIXES[key]}_cost"] = value(
            hard * (1 + soft + contingency),
            "AUD",
            f"GFA × construction rate by use, + {soft:.0%} soft costs "
            f"+ {contingency:.0%} contingency; no finance allowance",
        )
    return found


def operations(assumptions: dict, packages: dict[str, Package]) -> dict[str, object]:
    """Return the income, operating cost and renewal of each package."""
    uses = assumptions["use_assumptions"]
    found: dict[str, object] = {}
    for key in ("building_a", "building_b"):
        package = packages[key]
        found[f"{PREFIXES[key]}_income"] = value(
            fsum(
                package.gfa(use)
                * uses[use]["efficiency"]
                * uses[use]["initial_rent_AUD_per_m2_per_year"]
                * (1 - uses[use]["vacancy"])
                for use in package.uses()
            ),
            "AUD pa",
            "GFA × efficiency × 2027 rent × (1 − vacancy), by use",
        )
    utility = {
        name: -rate
        for name, rate in assumptions["utility_capex_AUD_per_m3_per_payment"].items()
    }
    for key, package in packages.items():
        prefix = PREFIXES[key]
        found[f"{prefix}_opex"] = value(
            package.floor_sum(by_use(assumptions, "floor_opex_AUD_per_m2_per_year"))
            + package.facade_sum(
                by_use(assumptions, "facade_opex_AUD_per_m2_per_year")
            ),
            "AUD pa",
            "Floor and facade OPEX of the package's floors, at 2027 prices",
        )
        found[f"{prefix}_renewal"] = value(
            package.floor_sum(by_use(assumptions, "floor_capex_AUD_per_m2_per_payment"))
            + package.volume_sum(utility),
            "AUD",
            "Floor capital rate × GFA, + utility capital rate × volume of the "
            "package's cores or plant, for one five-yearly renewal",
        )
    return found


def funding(plan: dict) -> dict[str, object]:
    """Return the equity and the loan limit."""
    money = plan["funding"]
    return {
        "equity": value(money["equity_AUD"], "AUD", "development.json equity"),
        "loan_limit": value(
            money["bridge_limit_AUD"], "AUD", "development.json bridge limit"
        ),
    }


def derive() -> dict[str, object]:
    """Return the base plan file content."""
    assumptions = json.loads((DATA / "assumptions.json").read_text(encoding="utf-8"))
    plan = json.loads((DATA / "development.json").read_text(encoding="utf-8"))
    rows = inventory()
    packages = {key: Package(rows, branch) for key, (branch, _) in PACKAGES.items()}
    phases = {phase["name"]: phase for phase in plan["phases"]}
    order = (
        "land_cost",
        "shared_cost",
        "a_cost",
        "b_cost",
        "a_income",
        "b_income",
        "shared_opex",
        "a_opex",
        "b_opex",
        "shared_renewal",
        "a_renewal",
        "b_renewal",
        "equity",
        "loan_limit",
    )
    amounts = {
        **budgets(plan, packages),
        **operations(assumptions, packages),
        **funding(plan),
    }
    return {
        "description": "The base plan of the mixed-use development, at 2027 "
        "prices. Derived by examples/data/derive_base_plan.py; recreate the "
        "file, do not edit it by hand.",
        "from": ["inventory.csv", "assumptions.json", "development.json"],
        "currency": plan["currency"],
        "phases": [
            {
                "key": key,
                "name": name,
                "start": phases[name]["start"],
                "open": phases[name]["open"],
            }
            for key, (_, name) in PACKAGES.items()
        ],
        "values": {**dates(plan), **{key: amounts[key] for key in order}},
        "areas": {
            key: {
                use: value(package.gfa(use), "sqm", "inventory.csv floor GFA")
                for use in package.uses()
            }
            for key, package in packages.items()
        },
        "rates": {
            use: value(rate, "AUD per sqm", "development.json construction rate")
            for use, rate in plan["construction_AUD_per_m2"].items()
        },
    }


def text() -> str:
    """Return the base plan file text, as the script writes it."""
    return json.dumps(derive(), indent=2, ensure_ascii=False) + "\n"


def main(arguments: list[str]) -> int:
    """Write the base plan file, or with ``--check`` compare it with a new derivation."""
    path = DATA / "base_plan.json"
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
