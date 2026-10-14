"""Execute all seven walkthroughs against one already built wheel, outside checkout."""

from pathlib import Path
import os, subprocess, sys, json

ROOT = Path(__file__).resolve().parents[4]
SITE = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
env = {
    **os.environ,
    "PYTHONPATH": str(SITE),
    "RK_SCENARIO_COUNT": "4",
    "RK_SCENARIO_WORKERS": "1",
    "RK_DESIGN_MODE": "fixture",
    "MPLCONFIGDIR": "/private/tmp/rk-turn3-mpl",
    "XDG_CACHE_HOME": "/private/tmp/rk-turn3-cache",
}
assert (SITE / "rangekeeper").is_dir()
for name in (
    "basic_dcf",
    "deterministic_scenarios",
    "market_dynamics",
    "flexibility_intro",
    "flexibility_under_uncertainty",
    "load_design",
    "drive_model_from_design",
):
    command = [
        sys.executable,
        str(ROOT / "docs/research/full-migration/turn2/run_notebook.py"),
        str(ROOT / "walkthrough" / f"{name}.ipynb"),
        str(OUT / f"{name}.ipynb"),
        "--cwd",
        str(OUT),
    ]
    with (OUT / f"{name}.log").open("w") as log:
        result = subprocess.run(
            command,
            cwd=OUT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=1800,
        )
    print(
        json.dumps(
            {
                "notebook": name,
                "exit_code": result.returncode,
                "command": command,
                "cwd": str(OUT),
                "site": str(SITE),
            }
        ),
        flush=True,
    )
    if result.returncode:
        raise SystemExit(result.returncode)
