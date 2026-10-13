"""Measure stock LinkML SQL generation against the actual RK schema.

Run in the isolated environment from tools/schema/requirements.txt.
"""

import argparse
from contextlib import redirect_stderr
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import traceback


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[2]
    report = {
        "versions": {
            p: importlib.metadata.version(p)
            for p in ("linkml", "linkml-runtime", "sqlalchemy")
        },
        "schema_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((root / "schema").glob("*.yaml"))
        },
        "probes": [],
    }
    with tempfile.TemporaryDirectory(prefix="rk-linkml-cache-") as cache:
        os.environ["PYSTOW_HOME"] = cache
        from linkml.generators.sqltablegen import SQLTableGenerator

        for direct in (False, True):
            name = "direct" if direct else "relational"
            result = {"mapping": name}
            stderr = io.StringIO()
            try:
                with redirect_stderr(stderr):
                    ddl = SQLTableGenerator(
                        str(root / "schema/model.yaml"),
                        dialect="sqlite",
                        direct_mapping=direct,
                    ).serialize()
                (args.output / f"{name}.sql").write_text(ddl)
                result["generated"] = True
                result["ddl_bytes"] = len(ddl.encode())
                with sqlite3.connect(":memory:") as db:
                    db.executescript(ddl)
                    result["sqlite_accepts_ddl"] = True
                    result["tables"] = [
                        r[0]
                        for r in db.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                        )
                    ]
                    result["sample_columns"] = {
                        table: [
                            list(r) for r in db.execute(f'PRAGMA table_info("{table}")')
                        ]
                        for table in (
                            "Model",
                            "Entity",
                            "Assembly",
                            "Value",
                            "PropertyContent",
                            "Expression",
                        )
                    }
            except Exception as error:
                result["error"] = f"{type(error).__name__}: {error}"
                (args.output / f"{name}-error.txt").write_text(traceback.format_exc())
            (args.output / f"{name}-stderr.txt").write_text(stderr.getvalue())
            report["probes"].append(result)
    (args.output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
