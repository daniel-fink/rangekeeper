"""Load the totals of the mixed-use property from its data package.

``load_property(year=)`` reads ``totals_<year>.json`` from
``examples/data/mixed_use_property`` and returns one Quantity for each key, with
its origin. It does no arithmetic. ``examples/data/derive_totals.py`` derives the
file from the floor inventory and the teaching assumptions, and documents how.
The lesson declares every financial equation between the totals (ADR-020,
principle 10). Lesson 06 shows the floors behind each total.
"""

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from html import escape

import rangekeeper as rk

from .plot import DATA


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


def load_property(*, year: int) -> Totals:
    """Return the totals of the completed property in one stabilised ``year``.

    The data package has a totals file for 2032 only. The works cost includes
    the plan's soft costs, contingency and construction finance allowance; the
    operating cost is a positive amount. Parking earns no rent, so it has no
    area, rent or vacancy key.
    """
    path = DATA / f"totals_{year}.json"
    if not path.is_file():
        available = sorted(item.stem[-4:] for item in DATA.glob("totals_*.json"))
        raise ValueError(f"No totals for {year}; the data package has {available}")
    content = json.loads(path.read_text(encoding="utf-8"))
    totals = {
        key: Total(
            rk.Quantity(magnitude=item["magnitude"], units=item["units"]),
            item["origin"],
        )
        for key, item in content["totals"].items()
    }
    return Totals(totals, title=f"Mixed-use property, stabilised year {year}")
