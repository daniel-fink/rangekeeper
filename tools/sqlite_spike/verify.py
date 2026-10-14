"""Build a reviewable package and collect bounded local evidence.

The child-process inspection blocks network access and original capture reads.
Use --inspect FILE to verify an existing package without building it again.
"""

import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time

from package import build, capture_inputs, Reader, schema_sql, sha
from render_probe import area, triangulate


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "examples/data/mixed_use_property"


def inspect(path):
    def restrict(event, arguments):
        if event in ("socket.connect", "socket.getaddrinfo"):
            raise RuntimeError("network access forbidden by the portability check")
        if event == "open" and isinstance(arguments[0], (str, bytes)):
            filename = Path(
                arguments[0].decode()
                if isinstance(arguments[0], bytes)
                else arguments[0]
            ).resolve()
            if filename.is_relative_to(SOURCE):
                raise RuntimeError(
                    "original capture access forbidden by the portability check"
                )

    sys.addaudithook(restrict)
    with Reader(path) as reader:
        result = reader.verify()
        first = reader.objects(limit=1)[0]
        reader.object(first["canonical_id"])
        result["original_capture_access"] = "blocked"
        result["network_access"] = "blocked"
        return result


def measured(operation, iterations=25):
    timings = []
    for _ in range(iterations):
        start = time.perf_counter()
        operation()
        timings.append((time.perf_counter() - start) * 1000)
    return {"median_ms": round(statistics.median(timings), 3), "iterations": iterations}


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    target = output / "mixed-use.rk.sqlite"
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="rk-sqlite-capture-") as directory:
        staging = Path(directory) / "capture"
        staging.mkdir()
        for name in (
            "model.json",
            "transport.json.gz",
            "associations.json",
            "manifest.json",
        ):
            shutil.copyfile(SOURCE / name, staging / name)
        args = capture_inputs(staging)
        build(Path(directory) / "model.sqlite", *args)
        shutil.copyfile(Path(directory) / "model.sqlite", target)
    # The private source copy and build location have now been removed.
    build_ms = (time.perf_counter() - start) * 1000
    child = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--inspect",
            str(target.resolve()),
        ],
        cwd=output,
        text=True,
        capture_output=True,
        check=True,
    )
    result = json.loads(child.stdout)
    with Reader(target) as reader:
        first = reader.objects(limit=1)[0]["canonical_id"]
        assembly = reader.db.execute(
            "SELECT canonical_id FROM records WHERE kind='Assembly' ORDER BY canonical_id LIMIT 1"
        ).fetchone()[0]
        geometry = reader.db.execute(
            "SELECT id,raw_bytes FROM geometry ORDER BY raw_bytes DESC LIMIT 1"
        ).fetchone()
        reads = []

        def authorizer(action, table, column, database, trigger):
            if action == sqlite3.SQLITE_READ:
                reads.append((table, column))
                if table in ("geometry", "documents"):
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        reader.db.set_authorizer(authorizer)
        queries = {
            "objects_25": measured(lambda: reader.objects(limit=25)),
            "members_25": measured(lambda: reader.members(assembly, limit=25)),
            "one_object_with_values": measured(lambda: reader.object(first)),
        }
        reader.db.set_authorizer(lambda *arguments: sqlite3.SQLITE_OK)
        queries["largest_geometry_record"] = {
            **measured(lambda: reader.geometry_object(geometry["id"])),
            "id": geometry["id"],
            "raw_bytes": geometry["raw_bytes"],
        }
        queries["full_model_reconstruction_and_validation"] = measured(
            reader.model, iterations=3
        )
        result["queries"] = queries
        result["query_geometry_and_document_reads"] = len(
            [r for r in reads if r[0] in ("geometry", "documents")]
        )
        result["record_kinds"] = dict(
            reader.db.execute("SELECT kind,count(*) FROM records GROUP BY kind")
        )
        result["canonical_records"] = reader.db.execute(
            "SELECT count(*) FROM records WHERE canonical_id IS NOT NULL"
        ).fetchone()[0]
        result["tables"] = reader.db.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        result["page_breakdown"] = [
            dict(row)
            for row in reader.db.execute(
                "SELECT name,sum(pgsize) bytes FROM dbstat GROUP BY name ORDER BY bytes DESC LIMIT 12"
            )
        ]
    # This is a geometry-conversion check, not browser or iOS acceptance.
    from fixtures import fixture

    render_path = output / "planar-quad.rk.sqlite"
    build(render_path, *fixture())
    before = sha(render_path.read_bytes())
    with Reader(render_path) as reader:
        mesh = json.loads(reader.geometry_object("quad"))
        renderings = [triangulate(mesh, diagonal) for diagonal in ("02", "13")]
        result["rendering"] = {
            "model_id": reader.metadata["model_id"],
            "content_digest": reader.metadata["content_digest"],
            "areas": [area(r) for r in renderings],
            "cache_keys": [r["cache_key"] for r in renderings],
            "different_triangles": renderings[0]["triangles"]
            != renderings[1]["triangles"],
        }
    result["rendering"]["database_bytes_unchanged"] = before == sha(
        render_path.read_bytes()
    )
    assert result["rendering"]["areas"] == [4.0, 4.0]
    assert (
        result["rendering"]["different_triangles"]
        and result["rendering"]["database_bytes_unchanged"]
    )
    result.update(
        {
            "date": "2026-10-13",
            "rk_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "python": sys.version,
            "sqlite": sqlite3.sqlite_version,
            "rangekeeper": importlib.metadata.version("rangekeeper"),
            "package_bytes": target.stat().st_size,
            "package_sha256": sha(target.read_bytes()),
            "build_and_copy_ms": round(build_ms, 3),
            "input_bytes": {
                name: (SOURCE / name).stat().st_size
                for name in ("model.json", "transport.json.gz", "associations.json")
            },
            "source_hashes": {
                p.name: sha(p.read_bytes())
                for p in sorted(Path(__file__).parent.glob("*.py"))
            },
            "limits": [
                "experimental storage mapping",
                "current Speckle object transport only",
                "no external blob assets",
                "headless quad conversion only",
                "no Payload, ChatGPT or native iOS execution",
                "no public geometry schema or revision enforcement yet",
            ],
        }
    )
    (output / "schema.sql").write_text(schema_sql())
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    panels = []
    for index, rendering in enumerate(renderings):
        vertices = [rendering["vertices"][i : i + 3] for i in range(0, 12, 3)]
        polygons = []
        for triangle in rendering["triangles"]:
            points = " ".join(
                f"{20+vertices[i][0]*90},{200-vertices[i][1]*90}" for i in triangle
            )
            polygons.append(
                f'<polygon points="{points}" fill="#dcebe9" stroke="#28685f" stroke-width="2"/>'
            )
        panels.append(
            f'<section><h2>Display conversion {index+1}</h2><svg viewBox="0 0 220 220" width="260">{"".join(polygons)}</svg><p>Area: {area(rendering):g} m² · 2 triangles</p></section>'
        )
    (output / "review.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>RK SQLite experiment</title>'
        "<style>body{font:17px system-ui;max-width:900px;margin:48px auto;padding:20px;color:#21332f}"
        "main{display:flex;gap:50px}section{flex:1}h2{font-size:20px}a{color:#24665c}</style>"
        "<h1>One Model, two display conversions</h1><p>The same stored planar quad produces two triangulations. "
        "The Model ID, package content digest and database bytes stay unchanged.</p>"
        f'<main>{"".join(panels)}</main><p>This is a headless conversion probe. Browser and native iOS viewers have not been tested.</p>'
        f'<p>The separate mixed-use package retains {result["geometry_records"]:,} geometry records in one {result["package_bytes"]:,}-byte database.</p>'
        '<p><a href="result.json">Verification results</a> · <a href="schema.sql">Generated schema</a> · '
        '<a href="mixed-use.rk.sqlite">Mixed-use database</a></p></html>'
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--inspect", type=Path)
    options = parser.parse_args()
    if options.inspect:
        print(json.dumps(inspect(options.inspect)))
    else:
        run(options.output.resolve())
