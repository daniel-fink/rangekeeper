"""Tests for the rename-pass codemod on a small package."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from tools.codemod import (
    Codemod,
    MapError,
    RenameMap,
    build_index,
    index_from_json,
    index_to_json,
    render,
)
from tools.codemod.cli import main

MAP = {
    "version": 1,
    "package": "pkg",
    "package_root": "src/pkg",
    "exclude": ["history/**"],
    "modules": [
        {"old": "pkg.model.duration", "new": "pkg.duration", "status": "agreed"},
        {"old": "pkg.model.flux", "new": "pkg.flow", "status": "draft"},
        {"old": "pkg.calc", "new": "pkg.finance", "status": "agreed"},
        {"old": "pkg.calc.series", "new": "pkg.flow.series", "status": "draft"},
        {
            "old": "pkg.calc.growth",
            "new": "pkg.finance.growth",
            "status": "pending",
            "pending": "#255 D12",
        },
        {
            "old": "pkg.model.system.projection",
            "new": "pkg.model.system.table",
            "status": "draft",
        },
    ],
    "paths": [{"old": "src/tests", "new": "tests", "status": "agreed"}],
    "symbols": [
        {
            "module": "pkg.model.duration.calendar",
            "name": "measure",
            "new_name": "count_steps",
            "status": "draft",
        },
        {
            "module": "pkg.calc.series",
            "name": "Aggregation",
            "new_name": "FlowAggregate",
            "status": "draft",
        },
        {
            "module": "pkg.model.system.reduction",
            "name": "Aggregation",
            "new_name": "RollupResult",
            "status": "draft",
        },
        {
            "module": "pkg.calc.money",
            "name": "calculate_pv",
            "new_name": "pv",
            "status": "pending",
            "pending": "#255 D19",
        },
    ],
    "attributes": [
        {
            "owner": "pkg.spec.Specification",
            "name": "lock",
            "new_name": "fix",
            "apply": "all",
            "status": "agreed",
        },
        {
            "owner": "pkg.model.flux.Stream",
            "name": "labels",
            "new_name": "names",
            "apply": "review",
            "status": "draft",
        },
    ],
    "parameters": [
        {
            "callable": "*",
            "name": "start_inclusive",
            "new_name": "start",
            "status": "agreed",
            "requires": ["schema"],
        },
    ],
    "fixups": [
        {
            "path": "src/tests/test_use.py",
            "old": "# retired: duration\n",
            "new": "",
            "status": "agreed",
        },
    ],
    "removed": [
        {
            "name": "pkg.calc.series.resample",
            "replacement": "Flow.resample",
            "status": "agreed",
        },
    ],
}

FILES = {
    "src/pkg/__init__.py": '''
        """Root."""

        from importlib import import_module

        _LAZY_MODULES = frozenset({"model", "calc", "spec"})


        def __getattr__(name):
            if name not in _LAZY_MODULES:
                raise AttributeError(name)
            return import_module(f"{__name__}.{name}")
        ''',
    "src/pkg/model/__init__.py": '"""Model."""\n',
    "src/pkg/model/duration/__init__.py": '''
        """Time."""

        from .calendar import measure

        __all__ = ["measure"]
        ''',
    "src/pkg/model/duration/calendar.py": '''
        """Calendar."""


        def measure(start, end):
            """Count steps."""
            return end - start


        def twice(start, end):
            """Count twice."""
            return 2 * measure(start, end)
        ''',
    "src/pkg/model/flux.py": '''
        """Streams."""

        from __future__ import annotations

        from typing import TYPE_CHECKING

        from ..calc.series import resample

        if TYPE_CHECKING:
            from pkg.calc.series import Aggregation


        class Stream:
            """A stream."""

            labels = ("a",)

            def aggregate(self) -> "Aggregation":
                """Aggregate."""
                from pkg.calc.series import Aggregation

                return Aggregation()

            def select(self, labels):
                """Select."""
                return self.labels
        ''',
    "src/pkg/model/system/__init__.py": '''
        """System."""

        from importlib import import_module

        _EXPORTS = {"Aggregation": "reduction", "to_table": "projection"}


        def __getattr__(name):
            return getattr(import_module(f".{_EXPORTS[name]}", __name__), name)
        ''',
    "src/pkg/model/system/reduction.py": '''
        """Rollups."""


        class Aggregation:
            """A rollup result."""
        ''',
    "src/pkg/model/system/projection.py": '''
        """Tables."""


        def to_table():
            """Return a table."""
            return []
        ''',
    "src/pkg/calc/__init__.py": '"""Calculations."""\n',
    "src/pkg/calc/growth.py": '"""Growth."""\n',
    "src/pkg/calc/money.py": '''
        """Money."""

        from .growth import __doc__ as growth_doc


        def calculate_pv(flow, *, rate):
            """Discount."""
            return flow / (1 + rate)
        ''',
    "src/pkg/calc/series.py": '''
        """Series."""


        class Aggregation:
            """A Flow aggregate."""


        def resample(flow):
            """Resample."""
            return flow
        ''',
    "src/pkg/spec.py": '''
        """Specifications."""


        class Specification:
            """A Specification."""

            def lock(self):
                """Lock."""
                return self

            def chain(self):
                """Lock twice."""
                return self.lock().lock()
        ''',
    "src/pkg/fingerprints.py": '''
        """Fingerprint sources."""

        SOURCES = ("model/duration/calendar.py", "calc/series.py", "spec.py")
        ''',
    "src/tests/__init__.py": "",
    "src/tests/fixtures/data.json": '{"a": 1}\n',
    "src/tests/test_use.py": """
        import pkg as rk
        import pkg.model.system
        from pkg.calc.series import Aggregation as Agg
        from pkg.model.duration import measure
        from pkg.model import flux
        from pkg.spec import Specification

        # retired: duration
        SCRIPT = '''
            from pkg.model.duration import measure
            measure(1, 2)
            '''


        def test_use(monkeypatch):
            monkeypatch.setattr("pkg.calc.series.Aggregation.x", 1, raising=False)
            assert rk.model.flux.Stream is flux.Stream
            assert measure(1, 3) == 2
            assert Specification().lock().chain()
            assert isinstance(flux.Stream().aggregate(), Agg)
            assert rk.model.system.to_table() == []
            assert rk.model.system.Aggregation.__doc__ == "A rollup result."
        """,
    "docs/guide.md": """
        # Guide

        Use `pkg.model.flux.Stream` or `rk.calc.series.Aggregation`. Run
        `pytest src/tests/test_use.py`.

        ```python
        from pkg.model.duration import measure

        measure(1, 2)
        ```

        ```text
        pkg.model.flux stays text, but it is still rewritten
        ```
        """,
    "history/old.md": (
        "`pkg.model.flux` is the old name. See [series](../src/pkg/calc/series.py#L1).\n"
    ),
    "pyproject.toml": '[tool.pytest.ini_options]\ntestpaths = ["src/tests"]\npythonpath = ["src"]\n',
}


def _write(root: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Return a small project with a package, tests and docs."""
    _write(tmp_path, FILES)
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "metadata": {},
                "source": ["from pkg.model.flux import Stream\n", "Stream"],
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["See `pkg.calc.series`."],
            },
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    (tmp_path / "docs" / "lesson.ipynb").write_text(
        json.dumps(notebook, indent=1) + "\n"
    )
    return tmp_path


def _map(**changes) -> RenameMap:
    return RenameMap.from_data({**MAP, **changes})


def _read(root: Path, name: str) -> str:
    return (root / name).read_text(encoding="utf-8")


def _pytest(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
        cwd=root,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(root / "src")},
    )


def test_map_keeps_agreed_and_draft_entries():
    rename_map = _map()
    assert [m.old for m in rename_map.modules] == [
        "pkg.model.duration",
        "pkg.model.flux",
        "pkg.calc",
        "pkg.calc.series",
        "pkg.model.system.projection",
    ]
    skipped = {
        getattr(e, "old", "") or getattr(e, "name", "") for e in rename_map.skipped
    }
    assert skipped == {"pkg.calc.growth", "calculate_pv", "start_inclusive"}
    assert rename_map.module("pkg.calc.series.x") == "pkg.flow.series.x"
    assert rename_map.module("pkg.calc.money") == "pkg.finance.money"
    assert rename_map.module("pkg.calculations") == "pkg.calculations"
    included = RenameMap.from_data(MAP, include_pending=True, allow=["schema"])
    assert {p.name for p in included.parameters} == {"start_inclusive"}
    assert "pkg.calc.growth" in {m.old for m in included.modules}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            {"modules": [{"old": "pkg.a", "new": "pkg.a.b", "status": "agreed"}]},
            "idempotent",
        ),
        ({"modules": [{"old": "pkg.a", "new": "pkg.b", "status": "maybe"}]}, "status"),
        (
            {"modules": [{"old": "pkg.a", "new": "pkg.b", "status": "pending"}]},
            "pending",
        ),
        ({"modules": [{"old": "pkg.a", "status": "agreed"}]}, "missing"),
        (
            {
                "modules": [
                    {"old": "pkg.a", "new": "pkg.b", "status": "agreed", "color": 1}
                ]
            },
            "unknown",
        ),
        ({"version": 2}, "version"),
        (
            {"fixups": [{"path": "a.py", "old": "x", "new": "xy", "status": "agreed"}]},
            "idempotent",
        ),
    ],
)
def test_map_rejects_invalid_entries(change, message):
    with pytest.raises(MapError, match=message):
        RenameMap.from_data({**MAP, **change})


def test_dry_run_writes_nothing(project: Path):
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    report = Codemod(project, _map()).run()
    assert report.changed
    after = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    assert before == after


def test_package_pass_moves_and_rewrites(project: Path):
    assert _pytest(project).returncode != 0  # no tests/ folder yet
    report = Codemod(project, _map()).run(apply=True)
    src = project / "src" / "pkg"
    assert not (src / "calc").exists()
    assert not (src / "model" / "duration").exists()
    assert not (project / "src" / "tests").exists()
    assert (project / "tests" / "fixtures" / "data.json").exists()
    assert ("src/pkg/model/flux.py", "src/pkg/flow/__init__.py") in report.moves

    calendar = _read(project, "src/pkg/duration/calendar.py")
    assert "def count_steps(start, end):" in calendar
    assert "2 * count_steps(start, end)" in calendar
    duration = _read(project, "src/pkg/duration/__init__.py")
    assert "from .calendar import count_steps" in duration
    assert '__all__ = ["count_steps"]' in duration

    flow = _read(project, "src/pkg/flow/__init__.py")
    assert "from pkg.flow.series import resample" in flow
    assert "from pkg.flow.series import FlowAggregate" in flow
    assert '-> "FlowAggregate":' in flow
    assert "labels = (" in flow  # review entries are not applied

    spec = _read(project, "src/pkg/spec.py")
    assert "def fix(self):" in spec and "self.fix().fix()" in spec

    root = _read(project, "src/pkg/__init__.py")
    assert '"finance"' in root and '"duration"' in root and '"flow"' in root
    assert '"calc"' not in root
    system = _read(project, "src/pkg/model/system/__init__.py")
    assert '"RollupResult": "reduction"' in system and '"to_table": "table"' in system

    money = _read(project, "src/pkg/finance/money.py")
    assert "from .growth import" in money  # stays relative inside finance
    assert "def calculate_pv" in money  # pending rename not applied

    fingerprints = _read(project, "src/pkg/fingerprints.py")
    assert '("duration/calendar.py", "flow/series.py", "spec.py")' in fingerprints

    test = _read(project, "tests/test_use.py")
    assert "from pkg.flow.series import FlowAggregate as Agg" in test
    assert "from pkg.duration import count_steps" in test
    assert "from pkg import flow as flux" in test
    assert '"pkg.flow.series.FlowAggregate.x"' in test
    assert "rk.flow.Stream is flux.Stream" in test
    assert "Specification().fix().chain()" in test
    assert "rk.model.system.RollupResult.__doc__" in test
    assert "retired" not in test
    script = "SCRIPT = '''\n    from pkg.duration import count_steps\n    count_steps(1, 2)\n    '''"
    assert script in test

    guide = _read(project, "docs/guide.md")
    assert "`pkg.flow.Stream`" in guide and "`rk.flow.series.FlowAggregate`" in guide
    assert "pytest tests/test_use.py" in guide
    assert "from pkg.duration import count_steps\n\ncount_steps(1, 2)" in guide
    assert "pkg.flow stays text" in guide
    assert _read(project, "history/old.md") == (
        "`pkg.model.flux` is the old name. See [series](../src/pkg/flow/series.py#L1).\n"
    )
    assert 'testpaths = ["tests"]' in _read(project, "pyproject.toml")

    notebook = json.loads(_read(project, "docs/lesson.ipynb"))
    assert notebook["cells"][0]["source"] == ["from pkg.flow import Stream\n", "Stream"]
    assert notebook["cells"][1]["source"] == ["See `pkg.flow.series`."]

    kinds = {(c.kind, c.detail.split(":")[0]) for c in report.review}
    assert ("removed", "pkg.calc.series.resample") in kinds
    assert any(c.kind == "review" and ".labels" in c.detail for c in report.review)

    result = _pytest(project)
    assert result.returncode == 0, result.stdout + result.stderr


def test_second_run_changes_nothing(project: Path):
    Codemod(project, _map()).run(apply=True)
    snapshot = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    report = Codemod(project, _map()).run(apply=True)
    assert not report.changed, report.summary(verbose=True)
    assert snapshot == {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}


def test_consumer_mode_uses_a_frozen_index(project: Path, tmp_path_factory):
    index = build_index(project / "src" / "pkg", "pkg")
    frozen = index_from_json(index_to_json(index))
    assert frozen == index
    consumer = tmp_path_factory.mktemp("consumer")
    _write(
        consumer,
        {
            "app.py": """
                import pkg as rk
                from pkg.model.system import Aggregation

                total = rk.model.system.Aggregation
                stream = rk.model.flux.Stream()
                spec.lock()
                """,
        },
    )
    report = Codemod(consumer, _map(package_root=""), consumer=True, index=frozen).run(
        apply=True
    )
    assert not report.moves
    app = _read(consumer, "app.py")
    assert "from pkg.model.system import RollupResult" in app
    assert "total = rk.model.system.RollupResult" in app
    assert "rk.flow.Stream()" in app
    assert "spec.fix()" in app


def test_cli_reports_and_checks(project: Path, tmp_path: Path, capsys):
    path = tmp_path / "map.yaml"
    path.write_text(yaml.safe_dump(MAP))
    assert main(["--root", str(project), "--map", str(path), "--check"]) == 1
    output = capsys.readouterr().out
    assert (
        "Nothing written" in output
        and "Not applied:" in output
        and "#255 D12" in output
    )
    assert (
        main(
            [
                "--root",
                str(project),
                "--map",
                str(path),
                "--apply",
                "--json",
                str(tmp_path / "r.json"),
            ]
        )
        == 0
    )
    data = json.loads((tmp_path / "r.json").read_text())
    assert data["moves"] and data["review"]
    assert main(["--root", str(project), "--map", str(path), "--check"]) == 0


def test_repository_map_is_valid_and_rendered():
    data = yaml.safe_load(render.MAP.read_text())
    rename_map = RenameMap.from_data(data)
    pending = [e for e in rename_map.skipped if e.status == "pending"]
    assert pending and all("#255" in e.pending for e in pending)
    assert all("#255" in n.pending for n in rename_map.notes)
    assert render.main(["--check"]) == 0


def test_crlf_files_get_the_same_changes(project: Path):
    """A Windows checkout can have CRLF line ends; rules and fixups still apply."""
    for path in project.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".md", ".toml"}:
            data = path.read_bytes().replace(b"\r\n", b"\n")
            path.write_bytes(data.replace(b"\n", b"\r\n"))
    Codemod(project, _map()).run(apply=True)

    def lf(name: str) -> str:
        data = (project / name).read_bytes()
        assert b"\n" not in data.replace(b"\r\n", b""), f"{name} mixes line ends"
        return data.decode().replace("\r\n", "\n")

    test = lf("tests/test_use.py")
    assert "retired" not in test
    assert "from pkg.duration import count_steps" in test
    assert "    from pkg.duration import count_steps\n    count_steps(1, 2)\n" in test
    guide = lf("docs/guide.md")
    assert "from pkg.duration import count_steps\n\ncount_steps(1, 2)" in guide
    assert "def count_steps(start, end):" in lf("src/pkg/duration/calendar.py")
    assert "from pkg.flow.series import FlowAggregate" in lf("src/pkg/flow/__init__.py")
    assert not Codemod(project, _map()).run().changed
