"""Rebuild reviewed sources as canonical Models, without reading prior outputs."""

from pathlib import Path
from collections import Counter
import json
from rangekeeper.workflow.workbench import build

P = Path("/Volumes/Data/Projects/Whirlwind/projects")
O = Path("/private/tmp/rk-turn3-private/candidate")
for project, spec, name in [
    ("mandarin", "spec", "mandarin"),
    ("east-whisman", "spec/december", "december"),
    ("east-whisman", "spec/november-r2", "november-r2"),
]:
    result = build(
        P / project / spec,
        input_root=P / project / "inputs",
        output_root=O / name,
        on_progress=lambda e: print(name, e, flush=True),
    )
    if result.result is None:
        raise RuntimeError(result.diagnostics)
    print(
        json.dumps(
            {
                "name": name,
                "directory": str(result.directory),
                "entities": len(result.result.model.find_entities()),
                "relationships": len(result.result.model.system.relationships or ()),
                "checks": dict(Counter(c.status for c in result.result.checks)),
            }
        ),
        flush=True,
    )
