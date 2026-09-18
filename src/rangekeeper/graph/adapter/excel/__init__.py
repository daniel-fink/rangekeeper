"""Snapshot-bound XLSX reading and explicit physical-range extraction.

Optional openpyxl/PyYAML dependencies are loaded at read/decode time only.
"""

from .extraction import extract_table
from .reader import read
from .snapshot import Cell, Workbook, Worksheet, WorksheetInspection
from .specification import (
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
    "Rows",
    "StopBefore",
    "Workbook",
    "Worksheet",
    "WorksheetInspection",
    "extract_table",
    "load_specification",
    "read",
]
