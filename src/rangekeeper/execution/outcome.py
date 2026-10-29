"""The result of an execution: its finalized Run, outputs and case Outcomes."""

from collections.abc import Iterator
from dataclasses import dataclass

from rangekeeper.model import Model
from rangekeeper.run import Run


@dataclass(frozen=True)
class Outcome:
    """The finalized Run of one Specification, with its outputs and cases.

    ``outputs`` are the accepted output Models, in the order of
    ``run.record.outputs``. A batch has one Outcome in ``cases`` for each of
    its direct cases, in Specification order; a leaf has none. An Outcome is
    immutable and holds no store.
    """

    run: Run
    outputs: tuple[Model, ...] = ()
    cases: tuple["Outcome", ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.run, Run):
            raise TypeError("run must be a Run")
        if tuple(model.id for model in self.outputs) != tuple(
            self.run.record.outputs or ()
        ):
            raise ValueError("outputs must be the Run's outputs, in order")
        if tuple(case.run.id for case in self.cases) != tuple(
            self.run.record.spawns or ()
        ):
            raise ValueError("cases must be the Run's spawned cases, in order")

    def walk(self) -> Iterator["Outcome"]:
        """Yield each case Outcome before its parent, ending with this one."""
        for case in self.cases:
            yield from case.walk()
        yield self
