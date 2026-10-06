"""Acceptance must fail on missing engines and skips, not report a green run."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rangekeeper.adapters.cytoscape.layout import minizinc_solver
from tests import layout_support

pytest_plugins = ["pytester"]


@pytest.mark.parametrize("configured", [False, True])
def test_minizinc_discovery_uses_environment_then_path(
    monkeypatch, tmp_path, configured
):
    binary = tmp_path / "minizinc"
    monkeypatch.delenv("RK_MINIZINC", raising=False)
    if configured:
        monkeypatch.setenv("RK_MINIZINC", str(binary))
    monkeypatch.setattr(
        minizinc_solver.shutil,
        "which",
        lambda name: str(binary) if not configured else None,
    )
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        output = (
            "MiniZinc version 2.10.1"
            if command[1] == "--version"
            else json.dumps(
                [{"id": "cp-sat", "name": "OR Tools CP-SAT", "version": "9.15"}]
            )
        )
        return SimpleNamespace(stdout=output)

    monkeypatch.setattr(minizinc_solver.subprocess, "run", run)
    assert layout_support.inspect_solver("minizinc")["executable"] == str(binary)
    assert all(command[0] == str(binary) for command in calls)


def test_discovery_rejects_minizinc_without_cp_sat(monkeypatch, tmp_path):
    monkeypatch.setenv("RK_MINIZINC", str(tmp_path / "minizinc"))
    monkeypatch.setattr(
        minizinc_solver.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(
            stdout="MiniZinc version 2.10.1" if command[1] == "--version" else "[]"
        ),
    )
    with pytest.raises(RuntimeError, match="no CP-SAT"):
        layout_support.inspect_solver("minizinc")


@pytest.mark.parametrize("missing", ["minizinc", "z3"])
def test_session_checks_each_engine_once_and_preserves_failure(monkeypatch, missing):
    calls = []

    def inspect(name):
        calls.append(name)
        if name == missing:
            raise RuntimeError("native tool missing")
        return {"version": "available"}

    monkeypatch.setattr(layout_support, "inspect_solver", inspect)
    state = layout_support.LayoutSolvers(strict=True)
    with pytest.raises(pytest.UsageError, match=missing):
        state.pytest_sessionstart(None)
    assert "native tool missing" in state.inspect(missing)
    assert calls.count(missing) == 1


@pytest.fixture
def isolated_pytest(pytester, monkeypatch):
    # Only the acceptance plugin is loaded in these child sessions. The real
    # solver tests remain independent of these synthetic availability reports.
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[1]))
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    pytester.makeconftest(
        """
pytest_plugins = ["tests.layout_support"]
from tests import layout_support
layout_support.inspect_solver = lambda name: {"version": "synthetic"}
"""
    )
    return pytester


@pytest.mark.parametrize("collection", [False, True])
def test_strict_acceptance_rejects_skips(isolated_pytest, collection):
    source = "import pytest\n"
    source += (
        'pytest.skip("collection gap", allow_module_level=True)\n'
        if collection
        else 'def test_gap():\n    pytest.skip("runtime gap")\n'
    )
    isolated_pytest.makepyfile(
        test_gap=source, test_pass="def test_pass(): assert True"
    )
    result = isolated_pytest.runpytest_subprocess("--require-layout-solvers", "-q")
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(["*Layout acceptance rejected skipped tests*"])


def test_strict_acceptance_allows_complete_run(isolated_pytest):
    isolated_pytest.makepyfile("def test_pass(): assert True")
    result = isolated_pytest.runpytest_subprocess("--require-layout-solvers", "-q")
    result.assert_outcomes(passed=1)
    assert result.ret == pytest.ExitCode.OK


@pytest.mark.parametrize("strict", [False, True])
def test_missing_tool_skips_only_in_optional_mode(isolated_pytest, strict):
    with (isolated_pytest.path / "conftest.py").open("a") as stream:
        stream.write(
            """
def missing(name):
    raise RuntimeError("missing test engine")
layout_support.inspect_solver = missing
"""
        )
    isolated_pytest.makepyfile(
        "import pytest\n@pytest.mark.minizinc\ndef test_solver(): assert True"
    )
    args = ["--require-layout-solvers"] if strict else []
    result = isolated_pytest.runpytest_subprocess(*args, "-q")
    if strict:
        assert result.ret == pytest.ExitCode.USAGE_ERROR
        result.stderr.fnmatch_lines(["*missing test engine*"])
    else:
        result.assert_outcomes(skipped=1)
        assert result.ret == pytest.ExitCode.OK
