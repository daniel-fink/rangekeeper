"""Solver-neutral results; deterministic geometry is separate from run metadata."""

from dataclasses import asdict, dataclass, field
from enum import Enum, unique

from rangekeeper.adapters.cytoscape.layout.model import Rect


@unique
class ResultStatus(Enum):
    UNKNOWN = "unknown"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    OPTIMAL = "optimal"


@unique
class StrictStatus(Enum):
    SAT = "sat"
    UNSAT = "unsat"
    UNKNOWN = "unknown"


@unique
class ResultMode(Enum):
    STRICT = "strict"
    DIAGNOSTIC = "diagnostic"


@dataclass
class Result:
    status: ResultStatus
    strict_status: StrictStatus
    mode: ResultMode = ResultMode.STRICT
    rectangles: dict[str, Rect] = field(default_factory=dict)
    grids: dict[str, dict] = field(default_factory=dict)
    measurements: dict = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)
    phases: list[dict] = field(default_factory=list)
    reason: str = ""
    solver_version: str = ""
    problem_fingerprint: str = ""
    build_seconds: float = 0
    first_solution_seconds: float | None = None
    search_scope: dict = field(default_factory=dict)
    incumbent_source: str = ""
    elapsed_seconds: float = 0
    solver_statistics: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if (
            not isinstance(self.status, ResultStatus)
            or not isinstance(self.strict_status, StrictStatus)
            or not isinstance(self.mode, ResultMode)
        ):
            raise TypeError("Result requires ResultStatus, StrictStatus and ResultMode")

    def to_mapping(self):
        data = asdict(self)
        for name in ("status", "strict_status", "mode"):
            data[name] = data[name].value
        return data

    def geometry_document(self):
        return {
            "schema": "rk-layout-geometry-v2",
            "problem_fingerprint": self.problem_fingerprint,
            "mode": self.mode.value,
            "rectangles": {i: asdict(r) for i, r in self.rectangles.items()},
            "grids": self.grids,
            "metrics": self.measurements,
            "findings": self.findings,
        }
