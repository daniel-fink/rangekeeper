"""Record one bounded follow-up check without overwriting previous evidence."""

from pathlib import Path
import argparse
import importlib.util
import json
import os

ROOT = Path(__file__).resolve().parents[4]
parser = argparse.ArgumentParser()
parser.add_argument("name")
parser.add_argument("--stage", default="final-confirmed")
parser.add_argument("--cwd", type=Path, default=ROOT)
parser.add_argument("--timeout", type=int, default=600)
parser.add_argument("command", nargs=argparse.REMAINDER)
args = parser.parse_args()
spec = importlib.util.spec_from_file_location(
    "recorder", ROOT / "docs/research/domain-migration/evidence/run_baseline.py"
)
recorder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recorder)
recorder.OUT = Path(__file__).parent / args.stage
recorder.OUT.mkdir(exist_ok=True)
command = args.command[1:] if args.command and args.command[0] == "--" else args.command
assert command
keys = ("PYTHONPATH", "MPLCONFIGDIR", "RK_SCENARIO_COUNT", "RK_SCENARIO_WORKERS")
with (recorder.OUT / "supplemental-environment.jsonl").open("a") as output:
    output.write(
        json.dumps(dict(name=args.name, overrides={k: os.environ.get(k) for k in keys}))
        + "\n"
    )
raise SystemExit(recorder.run(args.name, command, args.cwd, args.timeout))
