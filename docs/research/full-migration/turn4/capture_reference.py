"""Capture bounded numerical reference results from the accepted Turn 3 checkout.

Run this script with the historical checkpoint first on PYTHONPATH. It requires
the old numerical modules, which are deliberately absent after Turn 4. The JSON
fixture contains synthetic numbers only; canonical regression tests read it
without importing the old implementation. No random sampling or services run.
"""

from pathlib import Path
import hashlib
import inspect
import json
import sys

from rangekeeper.formula.financial import Account
from rangekeeper.dynamics.cyclicality import Enumerate

target = Path(sys.argv[1])
if target.exists():
    raise SystemExit("Reference already exists; choose an explicit new output")
sources = {}
for cls in (Account, Enumerate):
    path = Path(inspect.getfile(cls))
    sources[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
cases = []
for method in ("simple", "compound", "capitalized"):
    for timing in ("advance", "arrears"):
        for starting in (-20.0, 0.0, 100.0):
            values = Account._calculate(
                starting,
                [10.0, -200.0, 80.0, 400.0, -50.0],
                [0.01] * 5,
                method,
                timing == "arrears",
            )
            cases.append(
                {
                    "method": method,
                    "timing": timing,
                    "starting": starting,
                    "outputs": [[float(value) for value in path] for path in values],
                }
            )
cycles = [
    {
        "asymmetry": a,
        "values": [
            float(x)
            for x in Enumerate.asymmetric_sine(
                period=9,
                phase=2,
                amplitude=0.3,
                parameter=a,
                num_periods=50,
                precision=1e-11,
                bound=1,
            )
        ],
    }
    for a in (0, 0.2, 0.8)
]
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(
    json.dumps(
        {
            "checkpoint": "305f3ff6d460834ea803bae2fa6ad5c48a1627c9",
            "source_sha256": sources,
            "accounts": cases,
            "cycles": cycles,
        },
        indent=2,
    )
    + "\n"
)
print(f"Captured {len(cases)} account paths and {len(cycles)} cycle paths")
