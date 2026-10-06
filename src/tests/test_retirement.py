"""Guard physical removal and keep optional capabilities outside core imports."""

import importlib.util
import subprocess
import sys
import pytest
import rangekeeper


RETIRED = (
    "flux",
    "_legacy_duration",
    "distribution",
    "extrapolation",
    "projection",
    "formula",
    "dynamics",
    "segmentation",
    "policy",
    "format",
    "space",
)


@pytest.mark.parametrize("name", RETIRED)
def test_retired_module_is_absent_without_an_alias(name):
    assert name not in rangekeeper.__all__
    assert name not in dir(rangekeeper)
    with pytest.raises(AttributeError):
        getattr(rangekeeper, name)
    assert importlib.util.find_spec(f"rangekeeper.{name}") is None


@pytest.mark.parametrize("name", ("rgba_from_cmap", "update_class"))
def test_removed_presentation_helper_is_not_exported(name):
    assert name not in rangekeeper.__all__
    assert not hasattr(rangekeeper, name)


def test_canonical_imports_leave_held_domain_and_optional_libraries_unloaded():
    script = """
import sys
import rangekeeper
from rangekeeper import duration, calculations, formulations, scenarios, policies
from rangekeeper.graph import View
from rangekeeper.workflow import load, run
from rangekeeper.adapters.speckle import decode_model
from rangekeeper.migration import convert_graph
for name in ('rangekeeper.api', 'rangekeeper.measure', 'rangekeeper.graph.graph',
             'rangekeeper.legacy', 'specklepy', 'matplotlib', 'plotly',
             'pandas', 'numpy', 'scipy', 'pyomo', 'highspy', 'numba', 'multiprocess'):
    assert not any(m == name or m.startswith(name + '.') for m in sys.modules), name
"""
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True)
