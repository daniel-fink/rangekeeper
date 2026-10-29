"""Check an installed Rangekeeper with no extra, or with exactly one extra.

Usage: python tools/ci/check_extra.py core|bundle|calculations|execution|yaml

Run it outside the checkout's `src` folder, against an installed distribution.
It imports every module of the package. A module that fails must fail with the
installation hint for its extra. The modules of the selected extra must import,
and a small operation must work.
"""

import importlib
import json
import pkgutil
import subprocess
import sys
from datetime import date

import rangekeeper

EXTRAS = ("core", "bundle", "calculations", "execution", "yaml")


def import_all() -> dict[str, str]:
    """Import each module; return the hinted failures by module name."""
    hinted = {}
    for module in pkgutil.walk_packages(rangekeeper.__path__, "rangekeeper."):
        try:
            importlib.import_module(module.name)
        except ImportError as error:
            if "pip install 'rangekeeper[" not in str(error):
                raise AssertionError(
                    f"{module.name}: no install hint: {error}"
                ) from error
            hinted[module.name] = str(error)
    return hinted


def check_core() -> None:
    """Check core operations that need no extra."""
    from rangekeeper.duration import DayCount, year_fraction

    fraction = year_fraction(
        date(2020, 1, 1), date(2021, 1, 1), convention=DayCount.ACTUAL_ACTUAL
    )
    assert fraction == 1.0, fraction


def check_bundle() -> None:
    """Check the PyArrow and DuckDB imports of Bundle IO."""
    import duckdb

    import rangekeeper.io.bundle  # noqa: F401

    assert duckdb.connect().execute("select 1").fetchone() == (1,)


def check_calculations() -> None:
    """Check a PyXIRR valuation and a Polars projection."""
    from uuid import uuid4

    from rangekeeper.finance.financial import calculate_xnpv
    from rangekeeper.flow import Flow, Movement
    from rangekeeper.io.polars import to_frame

    flow = Flow(
        units="AUD",
        movements=(
            Movement(id=uuid4(), date=date(2021, 1, 1), magnitude=-100.0),
            Movement(id=uuid4(), date=date(2022, 1, 1), magnitude=110.0),
        ),
    )
    value = calculate_xnpv(flow=flow, rate=0.1, valuation_date=date(2021, 1, 1))
    assert abs(value.magnitude) < 1e-6, value
    assert to_frame(flow).height == 2


def check_execution() -> None:
    """Solve one equation in the isolated Pyomo/HiGHS worker."""
    request = {
        "unknowns": ["x"],
        "rows": [{"coefficients": [1.0], "constant": -2.0, "relation": "equal"}],
        "iteration_limit": 100,
        "remaining": 30.0,
    }
    output = subprocess.run(
        [sys.executable, "-m", "rangekeeper.execution.backends._worker"],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    response = json.loads(output)
    assert response.get("candidate") == {"x": 2.0}, response


def check_yaml() -> None:
    """Check strict YAML decoding."""
    from rangekeeper.shared.yaml import decode

    assert decode("a: 1") == {"a": 1}


def main() -> int:
    """Run the checks for the extra named on the command line."""
    if len(sys.argv) != 2 or sys.argv[1] not in EXTRAS:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    extra = sys.argv[1]
    hinted = import_all()
    for name, message in sorted(hinted.items()):
        print(f"{name}: {message}")
    check_core()
    if extra != "core":
        globals()[f"check_{extra}"]()
    print(f"{extra}: {len(hinted)} modules need another extra; checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
