import os
# Historical script extract: external paths and namespaces now require explicit inputs.
"""Run all three strict comparisons in a process separate from source construction."""

from pathlib import Path
import json
from compare_projects import compare

BASE = Path("/private/tmp/rk-turn3-private/baseline")
NEW = Path("/private/tmp/rk-turn3-complete-project-bootstrap/results")
for name, namespace in [
    ("proving-a", os.environ["RK_PROVING_A_NAMESPACE"]),
    ("december", os.environ["RK_PROVING_B_NAMESPACE"]),
    ("november-r2", os.environ["RK_PROVING_B_NAMESPACE"]),
]:
    latest = json.loads((NEW / name / "latest.json").read_text())
    print(name, latest, flush=True)
    directory = NEW / name / latest["directory"]
    result = compare(BASE / name, directory, namespace)
    (
        Path("/private/tmp/rk-turn3-private") / (name + "-wheel-comparison.json")
    ).write_text(json.dumps(result, indent=2))
    print(
        name,
        {
            k: v
            for k, v in result.items()
            if k not in ("identity_map", "retained_null_measurements")
        },
        "new_nulls",
        len(result["retained_null_measurements"]),
        flush=True,
    )
