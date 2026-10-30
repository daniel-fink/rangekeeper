"""Lesson names and the notebook-to-Markdown conversion for the docs site."""

import base64
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from rangekeeper.shared.table import Table

LESSONS = Path(__file__).resolve().parents[1]
TOOL = LESSONS.parents[1] / "tools" / "docs" / "notebooks.py"
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()


def run(*arguments):
    return subprocess.run(
        [sys.executable, str(TOOL), *map(str, arguments)],
        capture_output=True,
        text=True,
    )


def notebook(path, cells):
    path.write_text(json.dumps({"nbformat": 4, "nbformat_minor": 5, "cells": cells}))
    return path


def code(source, outputs=(), count=1, tags=()):
    return {
        "cell_type": "code",
        "source": source,
        "execution_count": count,
        "metadata": {"tags": list(tags)},
        "outputs": list(outputs),
    }


def test_lessons_are_numbered_and_have_no_outputs():
    lessons = sorted(LESSONS.glob("*.ipynb"))
    assert [path.name[:2] for path in lessons] == [f"{n:02}" for n in range(1, 8)]
    for path in lessons:
        assert re.fullmatch(r"\d{2}_[a-z0-9_]+\.ipynb", path.name)
        for cell in json.loads(path.read_text())["cells"]:
            assert not cell.get("outputs"), path.name
            assert cell.get("execution_count") is None, path.name


def test_conversion_writes_markdown_outputs_and_linked_files(tmp_path):
    source = tmp_path / "lessons"
    (source / "resources").mkdir(parents=True)
    (source / "resources" / "figure.png").write_bytes(b"png")
    cells = [
        {
            "cell_type": "markdown",
            "source": "# Title\n\n![Figure](resources/figure.png)",
        },
        code("x = 1\nprint(x)", [{"output_type": "stream", "text": "1\n"}]),
        code(
            "table",
            [
                {
                    "output_type": "execute_result",
                    "data": {"text/html": "<table>\n\n<tr></tr>\n</table>"},
                }
            ],
        ),
        code("hidden", tags=["remove-cell"]),
        code("chart", [{"output_type": "display_data", "data": {"image/png": PNG}}]),
        code("answer = 2", tags=["solution"]),
    ]
    notebook(source / "01_first_lesson.ipynb", cells)
    result = run(tmp_path / "site", source / "01_first_lesson.ipynb")
    assert result.returncode == 0, result.stderr
    page = (tmp_path / "site" / "01_first_lesson.md").read_text()
    assert page.startswith("# Title")
    assert "```python\nx = 1\nprint(x)\n```" in page
    assert "```text\n1\n```" in page
    assert '<div class="rk-output" markdown="0">\n<table>\n<tr></tr>' in page
    assert "hidden" not in page
    assert "![](01_first_lesson_files/output_1.png)" in page
    assert '??? success "Solution"\n\n    ```python\n    answer = 2' in page
    assert (tmp_path / "site" / "01_first_lesson_files" / "output_1.png").is_file()
    assert (tmp_path / "site" / "resources" / "figure.png").read_bytes() == b"png"


def test_conversion_keeps_the_html_display_of_a_table(tmp_path):
    table = Table(
        ("key", "quantity"),
        ({"key": f"value_{index}", "quantity": None} for index in range(52)),
    )
    output = {
        "output_type": "execute_result",
        "data": {"text/html": table._repr_html_(), "text/plain": repr(table)},
    }
    source = notebook(tmp_path / "01_table.ipynb", [code("table", [output])])
    result = run(tmp_path / "site", source)
    assert result.returncode == 0, result.stderr
    page = (tmp_path / "site" / "01_table.md").read_text()
    assert f'<div class="rk-output" markdown="0">\n{table._repr_html_()}' in page
    assert "<th>key</th>" in page
    assert "… 2 more rows" in page
    assert repr(table) not in page


@pytest.mark.parametrize(
    ("name", "cells", "message"),
    [
        ("lesson.ipynb", [], "NN_slug.ipynb"),
        ("01_lesson.ipynb", [code("x", count=None)], "not executed"),
        (
            "01_lesson.ipynb",
            [code("x", [{"output_type": "error", "ename": "KeyError"}])],
            "KeyError",
        ),
        (
            "01_lesson.ipynb",
            [{"cell_type": "markdown", "source": "![x](missing.png)"}],
            "missing file",
        ),
        (
            "01_lesson.ipynb",
            [{"cell_type": "markdown", "source": "![x](../outside.png)"}],
            "outside lessons",
        ),
    ],
)
def test_conversion_rejects_invalid_lessons(tmp_path, name, cells, message):
    (tmp_path / "outside.png").write_bytes(b"")
    (tmp_path / "lessons").mkdir()
    result = run(tmp_path / "site", notebook(tmp_path / "lessons" / name, cells))
    assert result.returncode == 1
    assert message in result.stderr


def test_skeleton_lessons_convert_without_execution(tmp_path):
    result = run(tmp_path, *sorted(LESSONS.glob("*.ipynb")), "--allow-unexecuted")
    assert result.returncode == 0, result.stderr
    assert len(list(tmp_path.glob("*.md"))) == 7
