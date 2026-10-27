"""The narrow immutable boundary consumed by execution orchestration."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from rangekeeper.execution.compiler import Compiled
from rangekeeper.execution.settings import Limits
from rangekeeper.schema.records import Implementation


@dataclass(frozen=True)
class Result:
    """A backend claim and candidate; only independent acceptance can publish it."""

    termination: str
    candidate: Mapping[UUID, float] | None = None
    implementations: tuple[Implementation, ...] = ()
    evidence: Mapping[str, object] = field(default_factory=dict)


class Backend(Protocol):
    """Backends must enforce the remaining wall deadline and return finite evidence."""

    def solve(self, problem: Compiled, *, limits: Limits, remaining: float) -> Result:
        """Solve a compiled problem within the remaining seconds; return a Result."""
        ...
