"""Load the totals of the mixed-use property from its data package.

``load_property(year=)`` reads the floor inventory and the teaching assumptions
of ``examples/data/mixed_use_property`` and returns one total for each key, with
its origin. Each total is a sum over the 33 floor objects at the rates of the
floor's use, on the plan's growth calendar. The lesson declares every financial
equation between the totals (ADR-020, principle 10). Lesson 06 shows the floors
behind each total.
"""

import csv
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from html import escape
from math import fsum

import rangekeeper as rk

from .plot import DATA

USES = ("hotel", "residential", "retail", "parking")
RENTED = USES[:-1]  # Parking earns no rent.


def _shown(quantity: rk.Quantity) -> str:
    """Show a Quantity to two decimal places; the Quantity keeps every digit."""
    return f"{float(quantity.magnitude):,.2f} {quantity.units}"


@dataclass(frozen=True)
class Total:
    """One total: its Quantity and where it comes from."""

    quantity: rk.Quantity
    origin: str


class Totals(Mapping[str, rk.Quantity]):
    """Quantities by key. A notebook shows the key, quantity and origin of each."""

    def __init__(self, totals: Mapping[str, Total], *, title: str):
        self._totals = dict(totals)
        self.title = title

    def __getitem__(self, key: str) -> rk.Quantity:
        return self._totals[key].quantity

    def __iter__(self) -> Iterator[str]:
        return iter(self._totals)

    def __len__(self) -> int:
        return len(self._totals)

    def origin(self, key: str) -> str:
        """Return the origin of one total."""
        return self._totals[key].origin

    def _repr_html_(self) -> str:
        rows = "".join(
            f"<tr><td><code>{escape(key)}</code></td>"
            f'<td style="text-align:right">{escape(_shown(total.quantity))}</td>'
            f"<td>{escape(total.origin)}</td></tr>"
            for key, total in self._totals.items()
        )
        return (
            f"<table><caption>{escape(self.title)}</caption>"
            "<thead><tr><th>key</th><th>quantity</th><th>origin</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )

    def __repr__(self) -> str:
        width = max(len(key) for key in self._totals)
        lines = [self.title]
        for key, total in self._totals.items():
            shown = _shown(total.quantity)
            lines.append(f"{key:<{width}}  {shown:>24}  {total.origin}")
        return "\n".join(lines)


def _floors():
    with (DATA / "inventory.csv").open(newline="", encoding="utf-8") as file:
        rows = [row for row in csv.DictReader(file) if row["classification"] == "floor"]
    if len(rows) != 33 or any(row["effective_use"] not in USES for row in rows):
        raise ValueError("The inventory must have 33 floors, each with a known use")
    return rows


def _income(totals, *, uses, growth_years):
    for use in RENTED:
        rates = uses[use]
        rent = rates["initial_rent_AUD_per_m2_per_year"]
        growth = rates["annual_income_growth"]
        totals[f"{use}_area"] = Total(
            rk.Quantity(magnitude=_gfa(use) * rates["efficiency"], units="sqm"),
            f"inventory.csv GFA × efficiency {rates['efficiency']:g}",
        )
        totals[f"{use}_rent"] = Total(
            rk.Quantity(
                magnitude=rent * (1 + growth) ** growth_years, units="AUD per sqm pa"
            ),
            f"{rent:g} AUD per sqm pa, grown {growth:.1%} pa for {growth_years} years",
        )
        totals[f"{use}_vacancy"] = Total(
            rk.Quantity(magnitude=rates["vacancy"] * 100, units="%"),
            "assumptions.json",
        )


def _gfa(use):
    return fsum(
        float(row["gfa_m2"]) for row in _floors() if row["effective_use"] == use
    )


def load_property(*, year: int) -> Totals:
    """Return the totals of the completed property in one stabilised ``year``.

    Lettable area is floor GFA times the use's efficiency. Rents and operating
    costs grow from the plan's base year on one calendar (``development.json``).
    The operating cost is a positive amount: floor and facade OPEX of every use,
    parking included. The works cost is the plan's construction budget with soft
    costs and contingency, and its construction finance allowance.
    """
    assumptions = json.loads((DATA / "assumptions.json").read_text(encoding="utf-8"))
    plan = json.loads((DATA / "development.json").read_text(encoding="utf-8"))
    base = int(plan["base_date"][:4])
    end = int(plan["horizon_end_exclusive"][:4])
    if type(year) is not int or not plan["stabilised_year"] <= year < end:
        raise ValueError(
            f"year must be a stabilised year, {plan['stabilised_year']} to {end - 1}"
        )
    uses = assumptions["use_assumptions"]
    totals = {}
    opex = fsum(
        float(row["gfa_m2"])
        * -uses[row["effective_use"]]["floor_opex_AUD_per_m2_per_year"]
        + float(row["perimeter_m"])
        * float(row["ftf_m"])
        * -uses[row["effective_use"]]["facade_opex_AUD_per_m2_per_year"]
        for row in _floors()
    )
    growth = assumptions["annual_opex_growth"]
    rates = plan["construction_AUD_per_m2"]
    soft = plan["soft_cost_fraction_of_hard_cost"]
    contingency = plan["contingency_fraction_of_hard_cost"]
    finance = plan["construction_finance_allowance_AUD"]
    works = fsum(_gfa(use) * rates[use] for use in USES) * (1 + soft + contingency)
    totals["works_cost"] = Total(
        rk.Quantity(magnitude=works + finance, units="AUD"),
        f"GFA × construction rate by use, + {soft:.0%} soft costs "
        f"+ {contingency:.0%} contingency, + {finance / 1e6:g} million AUD "
        "finance allowance",
    )
    totals["operating_cost"] = Total(
        rk.Quantity(magnitude=opex * (1 + growth) ** (year - base), units="AUD pa"),
        f"Floor and facade OPEX of all uses, grown {growth:.1%} pa "
        f"for {year - base} years",
    )
    _income(totals, uses=uses, growth_years=year - base)
    return Totals(totals, title=f"Mixed-use property, stabilised year {year}")
