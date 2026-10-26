"""Optional dependencies load on demand and name the extra that installs them."""

import subprocess
import sys
import textwrap

import pytest

from rangekeeper.shared.optional import requires

OPTIONAL = (
    "duckdb",
    "highspy",
    "numpy",
    "polars",
    "pyarrow",
    "pyomo",
    "pyxirr",
    "scipy",
    "yaml",
)


def test_requires_names_the_extra():
    with pytest.raises(ImportError, match=r"rangekeeper\[bundle\]") as caught:
        with requires("bundle"):
            import rangekeeper_missing_module  # noqa: F401
    assert caught.value.name == "rangekeeper_missing_module"
    assert isinstance(caught.value.__cause__, ImportError)


def test_core_needs_no_optional_extra():
    script = textwrap.dedent(
        f"""
        import importlib.abc, sys
        from datetime import date

        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                if name.partition(".")[0] in {OPTIONAL!r}:
                    raise ModuleNotFoundError(f"No module named {{name!r}}", name=name)

        sys.meta_path.insert(0, Block())
        import rangekeeper
        from rangekeeper import Model, Run, Specification
        from rangekeeper.model.duration import DayCount, year_fraction

        assert year_fraction(
            date(2020, 1, 1), date(2021, 1, 1), convention=DayCount.ACTUAL_ACTUAL
        ) == 1.0
        for module, extra in (("rangekeeper.io.bundle", "bundle"),):
            try:
                __import__(module)
            except ImportError as error:
                assert f"rangekeeper[{{extra}}]" in str(error), error
            else:
                raise AssertionError(module + " imported without its extra")
        from rangekeeper.io import yaml
        try:
            yaml.loads("a: 1", kind=Model)
        except ImportError as error:
            assert "rangekeeper[yaml]" in str(error), error
        else:
            raise AssertionError("YAML decoded without its extra")
        """
    )
    subprocess.run([sys.executable, "-c", script], check=True)
