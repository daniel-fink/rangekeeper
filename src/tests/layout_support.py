"""Shared optional-solver checks and strict layout acceptance hooks.

Ordinary tests skip unavailable engines. Explicit acceptance requires both engines
and treats every skip as a failure, including collection and browser-test skips.
Discovery runs once per engine and uses the production MiniZinc toolchain check.
"""

import importlib
from importlib.metadata import version

import pytest


def inspect_solver(name):
    """Return native toolchain metadata or raise with the setup failure.

    MiniZinc resolves RK_MINIZINC before PATH and must expose CP-SAT. Importing Z3
    also loads its native library; a Python package record alone is insufficient.
    These checks start short-lived processes but do not solve or write files.
    """
    if name == "minizinc":
        from rangekeeper.adapters.cytoscape.layout.minizinc_solver import toolchain

        return toolchain()
    if name == "z3":
        z3 = importlib.import_module("z3")
        return {"package": version("z3-solver"), "native": z3.get_version_string()}
    raise ValueError(f"Unknown layout solver: {name}")


class LayoutSolvers:
    """Own one test session's availability cache and skip accounting."""

    def __init__(self, strict):
        self.strict = strict
        self.available = {}
        self.errors = {}
        self.skipped = []

    def inspect(self, name):
        if name not in self.available and name not in self.errors:
            try:
                self.available[name] = inspect_solver(name)
            except Exception as error:
                self.errors[name] = f"{name} unavailable: {error}"
        return self.errors.get(name)

    def pytest_sessionstart(self, session):
        if self.strict:
            errors = [self.inspect(name) for name in ("minizinc", "z3")]
            if any(errors):
                raise pytest.UsageError("; ".join(error for error in errors if error))

    def pytest_runtest_setup(self, item):
        for name in ("minizinc", "z3"):
            if item.get_closest_marker(name):
                error = self.inspect(name)
                if error:
                    if self.strict:
                        pytest.fail(error, pytrace=False)
                    pytest.skip(error)

    def pytest_runtest_logreport(self, report):
        if report.skipped:
            self.skipped.append(report.nodeid)

    def pytest_collectreport(self, report):
        if report.skipped:
            self.skipped.append(report.nodeid)

    def pytest_sessionfinish(self, session, exitstatus):
        if self.strict and self.skipped and exitstatus == pytest.ExitCode.OK:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED

    def pytest_terminal_summary(self, terminalreporter):
        if self.strict and self.skipped:
            terminalreporter.write_sep(
                "=", "Layout acceptance rejected skipped tests", red=True
            )
            for nodeid in self.skipped:
                terminalreporter.write_line(nodeid)


def pytest_addoption(parser):
    parser.getgroup("rangekeeper").addoption(
        "--require-layout-solvers",
        action="store_true",
        help="require MiniZinc/CP-SAT and Z3; fail if any selected test is skipped",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "minizinc: requires native MiniZinc with CP-SAT")
    config.addinivalue_line("markers", "z3: requires the Z3 native solver")
    config.pluginmanager.register(
        LayoutSolvers(config.getoption("require_layout_solvers")), "rk-layout-solvers"
    )
