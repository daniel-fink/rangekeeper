"""Quantity coverage and optional import boundaries."""

import subprocess
import sys
from uuid import uuid4

import pytest

from rangekeeper.model.system import View

from .test_graph import fixture


def test_quantity_population_preserves_zero_missing_and_scope():
    model, root, a, b, c, *_ = fixture(missing=True)
    population = View(model, entities=(a.id, b.id, c.id)).quantities(
        "net", units="meter ** 2"
    )
    assert any(q.magnitude == 0 for q in population.quantities)
    assert population.coverage.missing
    assert set(population.coverage.selected) == {a.id, b.id, c.id}
    assert root.id not in population.coverage.selected
    with pytest.raises(TypeError):
        population.value_ids[a.id] = uuid4()


def test_core_imports_do_not_load_optional_dependencies():
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import rangekeeper; from rangekeeper import io; "
            "assert not any(n.split('.')[0] in "
            "{'matplotlib', 'plotly', 'specklepy', 'openpyxl'} for n in sys.modules)",
        ],
        check=True,
    )
