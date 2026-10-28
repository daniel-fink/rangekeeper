"""Guard physical removal and keep optional capabilities outside core imports."""

import importlib.util
import subprocess
import sys

import pytest

import rangekeeper

RETIRED = (
    "adapters",
    "workflow",
    "migration",
    "legacy",
    "_schema",
    "_records",
    "_record_index",
    "_revision",
    "_behaviors",
    "_coordinates",
    "_implementation",
    "_validation",
    "_encoding",
    "_structured",
    "_yaml",
    "account",
    "table",
    "units",
    "references",
    "diagnostics",
    "validate",
    "metadata",
    "graph",
    "formulations",
    "scenarios",
    "policies",
    "evidence",
    "operation",
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
from rangekeeper import finance as calculations
from rangekeeper import duration
from rangekeeper.model import formulation
from rangekeeper import market, profile
from rangekeeper.specification import rule
from rangekeeper.model.system import View
for name in ('rangekeeper.api', 'rangekeeper.measure', 'rangekeeper.model.system.graph',
             'rangekeeper.legacy', 'specklepy', 'matplotlib', 'plotly',
             'pandas', 'numpy', 'scipy', 'pyomo', 'highspy', 'numba', 'multiprocess'):
    assert not any(m == name or m.startswith(name + '.') for m in sys.modules), name
"""
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True)


@pytest.mark.parametrize(
    "name",
    [
        "rangekeeper.flow.series",
        "rangekeeper.calculations",
        "rangekeeper.model.measure",
        "rangekeeper.model.distribution",
        "rangekeeper.model.characteristics",
        "rangekeeper.io.migration",
    ],
)
def test_removed_1_0_modules_are_absent(name):
    assert importlib.util.find_spec(name) is None
