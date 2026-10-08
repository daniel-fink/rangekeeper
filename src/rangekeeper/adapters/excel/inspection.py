"""Workbook health observations from the existing immutable snapshot."""

from dataclasses import dataclass

from rangekeeper.adapters.excel.snapshot import Cell, Workbook


@dataclass(frozen=True, slots=True)
class HealthObservation:
    """Selected native cells explain a health finding without graph construction."""

    code: str
    name: str
    cells: tuple[Cell, ...]
    explanation: str


def health(workbook: Workbook) -> tuple[HealthObservation, ...]:
    """Inspect stored errors and missing formula caches without recalculation."""
    cells = tuple(c for sheet in workbook.worksheets for c in sheet.cells.values())
    formulas = tuple(c for c in cells if c.formula is not None)
    return (
        HealthObservation(
            "cache",
            "Formula caches",
            tuple(c for c in formulas if not c.cache_present),
            f"{len(formulas)} formulas inspected; caches are read, never calculated.",
        ),
        HealthObservation(
            "errors",
            "Excel errors",
            tuple(c for c in cells if c.data_type == "e" or c.cached_type == "e"),
            "Includes stored formula results and literal error cells.",
        ),
    )
