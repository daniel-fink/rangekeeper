"""Table display for pivots, rendered by native Polars.

The display needs the ``calculations`` extra (Polars) and no chart or graph
dependency. ``Pivot.display()`` returns a ``PivotTable``. Stream tables are in
``rangekeeper.flow``, which owns Stream display (ADR-010).
"""

from dataclasses import dataclass

from rangekeeper.flow._table import render


@dataclass(frozen=True)
class PivotTable:
    """Rows indented by depth, one column per pivot column, with units.

    "—" marks a cell with no contributor. "?" marks a cell with no value under
    its column's coverage policy, for example because a contributor is missing.
    """

    pivot: object
    precision: int = 2

    def __post_init__(self):
        if type(self.precision) is not int or not 0 <= self.precision <= 12:
            raise ValueError("precision must be an integer from 0 to 12")

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
                    raise TypeError("display requires scalar Quantity cells")
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
