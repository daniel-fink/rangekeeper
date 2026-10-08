"""Snapshot-bound XLSX reading and explicit physical-range extraction.

Optional openpyxl/PyYAML dependencies are loaded at read/decode time only.
"""

from rangekeeper.adapters.excel.classification import (
    RowClassificationSpec,
    classify_rows,
)
from rangekeeper.adapters.excel.extraction import extract_table
from rangekeeper.adapters.excel.reader import read
from rangekeeper.adapters.excel.snapshot import (
    Cell,
    Workbook,
    Worksheet,
    WorksheetInspection,
)
from rangekeeper.adapters.excel.specification import (
    Column,
    Expectations,
    ExtractionSpec,
    Rows,
    StopBefore,
    load_specification,
)

__all__ = [
    "Cell",
    "Column",
    "Expectations",
    "ExtractionSpec",
    "RowClassificationSpec",
    "Rows",
    "StopBefore",
    "Workbook",
    "Worksheet",
    "WorksheetInspection",
    "classify_rows",
    "extract_table",
    "load_specification",
    "read",
]
