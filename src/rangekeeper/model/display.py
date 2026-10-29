"""Table display for pivots, rendered by native Polars.

The display needs the ``calculations`` extra (Polars) and no chart or graph
dependency. ``Pivot.display()`` returns a ``PivotTable``. Stream tables are in
``rangekeeper.flow``, which owns Stream display (ADR-010).
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rangekeeper.flow._table import render
from rangekeeper.shared.errors import ContractError

if TYPE_CHECKING:
    # The pivot module imports this module to display a Pivot.
    from rangekeeper.model.system.pivot import Pivot


@dataclass(frozen=True, kw_only=True)
class PivotTable:
    """Rows indented by depth, one column per pivot column, with units.

    "—" marks a cell with no contributor. "?" marks a cell with no value under
    its column's coverage policy, for example because a contributor is missing.
    """

    pivot: "Pivot"
    precision: int = 2

    def __post_init__(self):
        if type(self.precision) is not int:
            raise TypeError("precision must be an int")
        if not 0 <= self.precision <= 12:
            raise ContractError(
                "precision must be from 0 to 12", values={"precision": self.precision}
            )

    def _cells(self):
        from rangekeeper.quantity import Quantity

        pivot = self.pivot
        rows = pivot.rows
        headers = ["Row"]
        for item, label in zip(pivot.columns, pivot._labels(), strict=True):
            units = next(
                (
                    entry.available.units
                    for entry in item.result.entries.values()
                    if entry.available is not None
                ),
                None,
            )
            headers.append(label if units is None else f"{label} [{units}]")
        depths, body = {}, []
        for index, id in enumerate(rows.preorder()):
            parent = rows.parent(id)
            depths[id] = 0 if parent is None else depths[parent] + 1
            entity = rows.view.entity(id)
            label = entity.name or entity.code or f"Entity {index + 1}"
            cells = ["  " * depths[id] + label]
            for item in pivot.columns:
                value = pivot.value(id, item)
                if value is not None and not isinstance(value, Quantity):
                    raise ContractError(
                        "display shows Quantity cells; this Pivot holds Flows"
                    )
                if not pivot.coverage(id, item).selected:
                    cells.append("—")
                elif value is None:
                    cells.append("?")
                else:
                    cells.append(f"{value.magnitude:,.{self.precision}f}")
            body.append(cells)
        return headers, body

    def _render(self, *, html: bool):
        return render(*self._cells(), html=html)

    def _repr_html_(self):
        return self._render(html=True)

    def __str__(self):
        return self._render(html=False)

    def __repr__(self):
        return str(self)
