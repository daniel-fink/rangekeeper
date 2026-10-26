"""Each lesson runs from a fresh kernel and converts to a docs page."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import nbformat
import pytest
from nbclient import NotebookClient

LESSONS = Path(__file__).resolve().parents[1]
TOOL = LESSONS.parents[1] / "tools" / "docs" / "notebooks.py"

# CI runs the routine checks: fixture design data and a few market paths.
ROUTINE = {"MPLBACKEND": "Agg", "RK_DESIGN_MODE": "fixture", "RK_PATH_COUNT": "4"}


@pytest.fixture(autouse=True)
def routine_environment(monkeypatch):
    for name, value in ROUTINE.items():
        monkeypatch.setenv(name, os.environ.get(name, value))


@pytest.mark.parametrize(
    "lesson", sorted(LESSONS.glob("*.ipynb")), ids=lambda path: path.stem
)
def test_lesson_runs_from_a_fresh_kernel(lesson, tmp_path):
    notebook = nbformat.read(lesson, as_version=4)
    # A new kernel for each lesson: no state carries over from earlier lessons.
    NotebookClient(
        notebook,
        timeout=1800,
        kernel_name="python3",
        resources={"metadata": {"path": str(LESSONS)}},
    ).execute()
    # The executed copy keeps the lesson's relative links to its resources.
    shutil.copytree(LESSONS / "resources", tmp_path / "resources")
    executed = tmp_path / lesson.name
    nbformat.write(notebook, executed)
    result = subprocess.run(
        [sys.executable, str(TOOL), str(tmp_path / "site"), str(executed)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "site" / f"{lesson.stem}.md").is_file()
