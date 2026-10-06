"""Run one explicit acceptance command and retain its output and environment.

This runner writes only to this evidence directory. The child command owns its
other side effects; use isolated build and notebook directories. Credentials and
the complete process environment are never copied into the command record.
"""

from pathlib import Path
import argparse
from datetime import datetime, timezone
import json
import os
import subprocess
import time

OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("name")
parser.add_argument("--cwd", type=Path, required=True)
parser.add_argument("command", nargs=argparse.REMAINDER)
args = parser.parse_args()
command = args.command
if command and command[0] == "--":
    command = command[1:]
if not command or Path(args.name).name != args.name:
    parser.error("provide a simple report name and an explicit command")
started = time.monotonic()
record = {
    "name": args.name,
    "started_at": datetime.now(timezone.utc).isoformat(),
    "command": command,
    "cwd": str(args.cwd.resolve()),
    "environment": {
        key: os.environ[key]
        for key in (
            "PYTHONPATH",
            "PYTHONDONTWRITEBYTECODE",
            "MPLCONFIGDIR",
            "MPLBACKEND",
            "PYSTOW_HOME",
            "UV_CACHE_DIR",
            "DOTNET_CLI_HOME",
            "NUGET_PACKAGES",
        )
        if key in os.environ
    },
}
with (OUT / f"{args.name}.txt").open("w") as output:
    result = subprocess.run(
        command, cwd=args.cwd, stdout=output, stderr=subprocess.STDOUT
    )
record.update(exit_code=result.returncode, seconds=round(time.monotonic() - started, 3))
with (OUT / "commands.jsonl").open("a") as log:
    log.write(json.dumps(record) + "\n")
print(json.dumps(record))
raise SystemExit(result.returncode)
