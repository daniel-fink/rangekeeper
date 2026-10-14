"""The narrow immutable boundary consumed by execution orchestration."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from rangekeeper.schema.records import Implementation
from rangekeeper.run.execution.compiler import Compiled
from rangekeeper.run.execution.settings import Limits


@dataclass(frozen=True)
class Result:
    """A backend claim and candidate; only independent acceptance can publish it."""

    termination: str
    candidate: Mapping[UUID, float] | None = None
    implementations: tuple[Implementation, ...] = ()
    evidence: Mapping[str, object] = field(default_factory=dict)


class Backend(Protocol):
    """Backends must enforce the remaining wall deadline and return finite evidence."""

    def solve(
        self, problem: Compiled, *, limits: Limits, remaining: float
    ) -> Result: ...
