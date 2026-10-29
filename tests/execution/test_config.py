"""ExecutionConfig is the one source of execution defaults (#128)."""

import importlib.util
from dataclasses import fields

import pytest

from rangekeeper.errors import Code
from rangekeeper.execution import (
    ExecutionConfig,
    Limits,
    Tolerances,
    execute,
    settings,
)
from rangekeeper.execution.backends import PyomoHighs
from rangekeeper.run import CompletionStatus, SolutionStatus
from rangekeeper.schema.records import Settings
from tests.execution.test_execution import setup, spec

needs_backend = pytest.mark.skipif(
    any(importlib.util.find_spec(name) is None for name in ("pyomo", "highspy")),
    reason="requires the optional execution extra",
)


def test_defaults_have_one_source():
    config = ExecutionConfig()
    assert config.backend == "pyomo-highs"
    assert config.units is None
    assert config.limits == Limits()
    assert config.tolerances == Tolerances()
    assert dict(config.backend_options) == {}
    limits, findings = settings.resolve(None, defaults=config.limits)
    assert limits == config.limits and findings == ()


def test_requested_settings_replace_only_their_own_defaults():
    defaults = Limits(
        time_limit=5, iteration_limit=7, symbol_limit=9, constraint_limit=11
    )
    limits, _ = settings.resolve(Settings(iteration_limit=3), defaults=defaults)
    assert limits == Limits(
        time_limit=5, iteration_limit=3, symbol_limit=9, constraint_limit=11
    )


@pytest.mark.parametrize(
    "name,value,error",
    [
        ("time_limit", 0, ValueError),
        ("time_limit", float("inf"), ValueError),
        ("time_limit", True, TypeError),
        ("iteration_limit", 0, ValueError),
        ("symbol_limit", 1.5, TypeError),
        ("constraint_limit", -1, ValueError),
    ],
)
def test_limits_reject_values_that_no_attempt_can_use(name, value, error):
    with pytest.raises(error):
        Limits(**{name: value})


@pytest.mark.parametrize(
    "changes,error",
    [
        ({"backend": 3}, TypeError),
        ({"units": "SI"}, TypeError),
        ({"limits": {"time_limit": 1}}, TypeError),
        ({"tolerances": 1e-9}, TypeError),
        ({"backend_options": {1: "on"}}, TypeError),
        ({"backend_options": {"presolve": ["on"]}}, TypeError),
        ({"backend_options": {"tolerance": float("nan")}}, ValueError),
    ],
)
def test_config_checks_its_fields(changes, error):
    with pytest.raises(error):
        ExecutionConfig(**changes)


def test_backend_options_are_frozen():
    options = {"presolve": "off"}
    config = ExecutionConfig(backend_options=options)
    options["presolve"] = "on"
    assert config.backend_options["presolve"] == "off"
    with pytest.raises(TypeError):
        config.backend_options["presolve"] = "on"  # type: ignore[index]
    assert {field.name for field in fields(ExecutionConfig)} == {
        "backend",
        "units",
        "limits",
        "tolerances",
        "backend_options",
    }


def test_config_limits_apply_when_the_specification_has_no_settings():
    class Uncalled:
        def solve(self, *args, **kwargs):
            raise AssertionError("the symbol limit must stop the attempt")

    store, _ = setup()
    run = execute(
        specification=spec(settings={}),
        store=store,
        config=ExecutionConfig(backend=Uncalled(), limits=Limits(symbol_limit=1)),
    ).run
    assert run.report.status.completion == CompletionStatus.FAILED
    assert any(d.code == Code.SYMBOL_LIMIT for d in run.report.diagnostics)


@needs_backend
def test_backend_options_reach_the_solver_and_its_evidence():
    store, _ = setup()
    run = execute(
        specification=spec(),
        store=store,
        config=ExecutionConfig(backend_options={"presolve": "off"}),
    ).run
    assert run.report.status.solution == SolutionStatus.FEASIBLE
    evidence = next(
        d.values for d in run.report.diagnostics if d.code == Code.SOLVER_TERMINATION
    )
    assert evidence["solver_options"]["presolve"] == "off"


def test_a_reserved_backend_option_fails_the_attempt_with_evidence():
    store, _ = setup()
    config = ExecutionConfig(
        backend=PyomoHighs(), backend_options={"output_flag": True}
    )
    run = execute(specification=spec(), store=store, config=config).run
    assert run.report.status.completion == CompletionStatus.FAILED
    assert not run.record.outputs
    assert any(
        d.code == Code.UNSUPPORTED_CAPABILITY and "output_flag" in d.message
        for d in run.report.diagnostics
    )
