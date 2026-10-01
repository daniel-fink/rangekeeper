"""Solver-neutral results; deterministic geometry is separate from run metadata."""

from dataclasses import asdict, dataclass, field

from .model import Rect


@dataclass
class Result:
    status: str
    strict_status: str
    mode: str = "strict"
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

    def geometry_document(self):
        return {
            "schema": "rk-layout-geometry-v2",
            "problem_fingerprint": self.problem_fingerprint,
            "mode": self.mode,
            "rectangles": {i: asdict(r) for i, r in self.rectangles.items()},
            "grids": self.grids,
            "metrics": self.measurements,
            "findings": self.findings,
        }
