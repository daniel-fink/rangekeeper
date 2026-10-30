"""The docs site build shows each lesson display from a copy published with it."""

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import plotly.graph_objects as go
import pytest
from helpers import plot

TOOLS = Path(__file__).resolve().parents[3] / "tools" / "docs"
sys.path.insert(0, str(TOOLS))
_spec = spec_from_file_location("docs_site", TOOLS / "site.py")
site = module_from_spec(_spec)
_spec.loader.exec_module(site)


def executed(path, frame):
    """Write an executed lesson whose one output is the iframe of ``frame``."""
    output = {
        "output_type": "execute_result",
        "data": {"text/html": frame._repr_html_(), "text/plain": repr(frame)},
        "metadata": {},
        "execution_count": 1,
    }
    cell = {"cell_type": "code", "source": "", "outputs": [output]}
    path.write_text(json.dumps({"nbformat": 4, "cells": [cell]}))
    return path


def html(path):
    return json.loads(path.read_text())["cells"][0]["outputs"][0]["data"]["text/html"]


def test_geometry_display_points_at_a_copy_with_its_data(workdir):
    lesson = executed(workdir / "02_lesson.ipynb", plot.show_geometry("floors"))
    stage = workdir / "site"
    site.publish_displays(
        lesson, page=stage / "walkthrough" / "02_lesson.md", site=stage
    )
    # The link is relative to the page file; Zensical adjusts it for the URL.
    assert 'src="output/geometry/viewer.html?view=floors"' in html(lesson)
    assert "127.0.0.1" not in html(lesson)
    viewer = stage / "walkthrough" / "output" / "geometry"
    assert {"viewer.html", "viewer.js", "geometry.json"} <= {
        path.name for path in viewer.iterdir()
    }
    settings = json.loads((viewer / "geometry.json").read_text())
    data = (viewer / settings["data"]).resolve()
    assert data == (stage / "data" / "mixed_use_property").resolve()
    for name in settings["files"]:
        assert (data / name).read_bytes() == (plot.DATA / name).read_bytes()


def test_a_display_outside_examples_stops_the_build(workdir):
    frame = plot.show_plot(go.Figure(go.Scatter(x=[1], y=[2])), path="chart.html")
    lesson = executed(workdir / "01_lesson.ipynb", frame)
    stage = workdir / "site"
    with pytest.raises(site.ConversionError, match="not in examples"):
        site.publish_displays(
            lesson, page=stage / "walkthrough" / "01_lesson.md", site=stage
        )
