"""Apply the 1.0 rename map to the package, its tests and docs, or to consumer code.

Run `python -m tools.codemod --help` from the repository root. The README in this
folder describes the map and the options.
"""

from .engine import Codemod, build_index, index_from_json, index_to_json
from .renamemap import MapError, RenameMap
from .report import Change, Report

__all__ = [
    "Change",
    "Codemod",
    "MapError",
    "RenameMap",
    "Report",
    "build_index",
    "index_from_json",
    "index_to_json",
]
