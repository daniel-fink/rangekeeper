"""Load the totals and the base plan of the mixed-use property from its data package.

``load_property(year=)`` reads ``totals_<year>.json`` from
``examples/data/mixed_use_property`` and returns one Quantity for each key, with
its origin. ``load_base_plan()`` reads ``base_plan.json``: the dates, budgets,
incomes, operating costs, renewals and funding of the development, each with its
origin, and the areas, rates and phases of the plan. Neither does arithmetic.
``data_path(name=)`` gives the path of a document of the data package, for
``rk.io.load``.
``examples/data/derive_totals.py`` and ``examples/data/derive_base_plan.py``
derive the files from the floor inventory and the teaching assumptions, and
document how. The lessons declare every financial equation (ADR-020, principle
10). Lesson 06 shows the floors behind each total.
"""

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path

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


@dataclass(frozen=True)
class Phase:
    """One package of the plan: its key, its name, its start and its opening."""

    key: str
    name: str
    start: date
    open: date


def _value(item: Mapping[str, object]) -> rk.Quantity | date:
    """Return the date or the Quantity of one plan value."""
    if "date" in item:
        return date.fromisoformat(str(item["date"]))
    return rk.Quantity(magnitude=item["magnitude"], units=str(item["units"]))


def _quantities(items: Mapping[str, Mapping]) -> dict[str, rk.Quantity]:
    """Return the Quantity of each item, by key."""
    return {
        key: rk.Quantity(magnitude=item["magnitude"], units=item["units"])
        for key, item in items.items()
    }


class BasePlan(Mapping[str, "rk.Quantity | date"]):
    """The base plan's values by key: a date or a Quantity, each with its origin.

    ``areas[package][use]`` is the floor area of one use in one package, and
    ``rates[use]`` the construction rate of the use. ``phases`` gives the start
    and opening of each package. A notebook shows the key, value and origin of
    each value.
    """

    def __init__(
        self,
        values: Mapping[str, tuple["rk.Quantity | date", str]],
        *,
        areas: Mapping[str, Mapping[str, rk.Quantity]],
        rates: Mapping[str, rk.Quantity],
        phases: tuple[Phase, ...],
        title: str,
    ):
        self._values = dict(values)
        self.areas = {package: dict(uses) for package, uses in areas.items()}
        self.rates = dict(rates)
        self.phases = phases
        self.title = title

    def __getitem__(self, key: str) -> "rk.Quantity | date":
        return self._values[key][0]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def origin(self, key: str) -> str:
        """Return the origin of one value."""
        return self._values[key][1]

    def _rows(self) -> list[tuple[str, str, str]]:
        return [
            (
                key,
                value.isoformat() if isinstance(value, date) else _shown(value),
                origin,
            )
            for key, (value, origin) in self._values.items()
        ]

    def _repr_html_(self) -> str:
        rows = "".join(
            f"<tr><td><code>{escape(key)}</code></td>"
            f'<td style="text-align:right">{escape(shown)}</td>'
            f"<td>{escape(origin)}</td></tr>"
            for key, shown, origin in self._rows()
        )
        return (
            f"<table><caption>{escape(self.title)}</caption>"
            "<thead><tr><th>key</th><th>value</th><th>origin</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )

    def __repr__(self) -> str:
        rows = self._rows()
        width = max(len(key) for key, _, _ in rows)
        lines = [self.title]
        for key, shown, origin in rows:
            lines.append(f"{key:<{width}}  {shown:>24}  {origin}")
        return "\n".join(lines)


def data_path(*, name: str) -> Path:
    """Return the path of one file of the data package; the file must exist."""
    path = DATA / name
    if not path.is_file():
        raise ValueError(f"The data package has no file {name!r}")
    return path


def load_base_plan() -> BasePlan:
    """Return the base plan of the mixed-use development, at 2027 prices.

    The plan has three packages: the shared plinth (``shared``), Building A
    (``building_a``) and Building B (``building_b``). The budgets leave out the
    construction finance allowance, and the plinth's operating cost and renewal
    are not split between the buildings.
    """
    content = json.loads((DATA / "base_plan.json").read_text(encoding="utf-8"))
    values = {
        key: (_value(item), str(item["origin"]))
        for key, item in content["values"].items()
    }
    phases = tuple(
        Phase(
            key=item["key"],
            name=item["name"],
            start=date.fromisoformat(item["start"]),
            open=date.fromisoformat(item["open"]),
        )
        for item in content["phases"]
    )
    return BasePlan(
        values,
        areas={
            package: _quantities(uses) for package, uses in content["areas"].items()
        },
        rates=_quantities(content["rates"]),
        phases=phases,
        title="Mixed-use development, base plan at 2027 prices",
    )
