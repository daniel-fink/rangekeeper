"""The public configuration of an execution: the one source of its defaults."""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from rangekeeper.execution.acceptance import Tolerances
from rangekeeper.execution.backends import Backend
from rangekeeper.execution.settings import Limits
from rangekeeper.quantity import UnitSystem

BackendOption = str | int | float | bool


@dataclass(frozen=True, kw_only=True)
class ExecutionConfig:
    """The limits, tolerances, unit system and backend options of an execution.

    Each execution default has this class as its one source.

    - ``backend`` is a Backend, or the name of one in
      ``rangekeeper.execution.backends.registry``.
    - ``units`` is the unit system of each case. Without it, each case uses the
      unit system of its input Model.
    - ``limits`` is the default budget of each leaf case. A Specification's
      ``settings`` replace a limit for its own cases.
    - ``tolerances`` is the policy of independent verification. It is separate
      from the solver's own tolerances.
    - ``backend_options`` go to the backend unchanged. Each backend documents
      the options that it reads and the options that it refuses.
    - ``allow_underdetermined`` publishes the verified candidate of an
      underdetermined solve as its output. By default an underdetermined solve
      has no output; either way its Run's solution is ``underdetermined`` and
      names the free unknowns (ADR-016).
    """

    backend: Backend | str = "pyomo-highs"
    units: UnitSystem | None = None
    limits: Limits = Limits()
    tolerances: Tolerances = Tolerances()
    backend_options: Mapping[str, BackendOption] = field(
        default_factory=lambda: MappingProxyType({})
    )
    allow_underdetermined: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.backend, str) and not isinstance(self.backend, Backend):
            raise TypeError("backend must be a Backend or a registered name")
        if self.units is not None and not isinstance(self.units, UnitSystem):
            raise TypeError("units must be a UnitSystem")
        if not isinstance(self.limits, Limits):
            raise TypeError("limits must be Limits")
        if not isinstance(self.tolerances, Tolerances):
            raise TypeError("tolerances must be Tolerances")
        if type(self.allow_underdetermined) is not bool:
            raise TypeError("allow_underdetermined must be True or False")
        options = dict(self.backend_options)
        for name, value in options.items():
            if not isinstance(name, str):
                raise TypeError("backend option names must be strings")
            if not isinstance(value, BackendOption):
                raise TypeError(f"backend option {name} must be a JSON scalar")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"backend option {name} must be finite")
        object.__setattr__(self, "backend_options", MappingProxyType(options))
