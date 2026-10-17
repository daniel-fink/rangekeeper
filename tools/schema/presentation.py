"""Build the offline schema presentation from LinkML and curated view layouts.

Use tools/schema/requirements.txt. --check compares without writing the output.
The view file owns layout and short captions; LinkML owns schema semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import tempfile

import yaml
from linkml_runtime.dumpers import json_dumper
from linkml_runtime.utils.schemaview import SchemaView

ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).with_name("presentation")
DEFAULT_OUTPUT = ROOT / "docs/schema-presentation.html"


def plain(record):
    return json.loads(json_dumper.dumps(record))


def build_data():
    if importlib.metadata.version("linkml-runtime") != "1.11.1":
        raise RuntimeError("Use the pinned tools/schema/requirements.txt environment")
    source_files = sorted((ROOT / "schema").glob("*.yaml"))
    digest = hashlib.sha256()
    definitions = {}
    modules = []
    for path in source_files:
        content = path.read_text()
        relative = str(path.relative_to(ROOT))
        digest.update(relative.encode() + b"\0" + content.encode() + b"\0")
        raw = yaml.safe_load(content)
        modules.append(
            {
                "file": relative,
                "name": raw["name"],
                "version": str(raw.get("version", "")),
            }
        )
        document = yaml.compose(content)
        for group_key, group in document.value:
            if group_key.value not in ("classes", "enums", "types"):
                continue
            for key, node in group.value:
                definitions[key.value] = {
                    "name": key.value,
                    "category": {"classes": "record", "enums": "enum", "types": "type"}[
                        group_key.value
                    ],
                    "source": relative,
                    "line": key.start_mark.line + 1,
                    "module_version": str(raw.get("version", "")),
                    "raw": raw[group_key.value][key.value],
                    "yaml": content[
                        key.start_mark.index : node.end_mark.index
                    ].rstrip(),
                }
    with tempfile.TemporaryDirectory(prefix="rk-presentation-") as temporary:
        bundle_dir = Path(temporary)
        for path in source_files:
            (bundle_dir / path.name).write_bytes(path.read_bytes())
        bundle_content = (ROOT / "tools/schema/bundle.yaml").read_bytes()
        digest.update(b"bundle\0" + bundle_content)
        bundle = bundle_dir / "bundle.yaml"
        bundle.write_bytes(bundle_content)
        view = SchemaView(str(bundle))
        for name, item in definitions.items():
            if item["category"] != "record":
                item["description"] = item["raw"].get("description", "")
                continue
            cls = view.get_class(name)
            item.update(
                {
                    "description": str(cls.description or ""),
                    "notes": list(cls.notes),
                    "parent": str(cls.is_a) if cls.is_a else None,
                    "fields": [plain(slot) for slot in view.class_induced_slots(name)],
                }
            )
    scenes = json.loads((ASSETS / "views.json").read_text())
    for scene in scenes:
        ids = {node["id"]: node for node in scene["nodes"]}
        assert len(ids) == len(scene["nodes"]), scene["id"]
        for node in scene["nodes"]:
            assert node["type"] in definitions, node
            if node.get("via"):
                owner, field = node["via"].split(".")
                assert any(
                    s["name"] == field for s in definitions[owner]["fields"]
                ), node
        for edge in scene["edges"]:
            assert edge["from"] in ids and edge["to"] in ids, edge
            if edge.get("field"):
                source = definitions[ids[edge["from"]]["type"]]
                assert any(s["name"] == edge["field"] for s in source["fields"]), edge
    return {
        "title": "Rangekeeper schema",
        "model_version": yaml.safe_load((ROOT / "schema/model.yaml").read_text())[
            "version"
        ],
        "schema_hash": digest.hexdigest(),
        "modules": modules,
        "definitions": definitions,
        "scenes": scenes,
    }


def generate():
    data = build_data()
    encoded = (
        json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    html = (ASSETS / "index.html").read_text()
    for key, content in {
        "STYLE": (ASSETS / "style.css").read_text(),
        "DATA": encoded,
        "SCRIPT": (ASSETS / "app.js").read_text(),
    }.items():
        marker = "<!-- " + key + " -->"
        assert html.count(marker) == 1, marker
        html = html.replace(marker, content)
    return html


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    html = generate()
    if args.check:
        if not args.output.exists() or args.output.read_text() != html:
            raise SystemExit(f"Presentation is out of date: {args.output}")
        print("Presentation matches the LinkML source and view templates.")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(html)
        print(f"Wrote {args.output} ({len(html.encode()):,} bytes)")


if __name__ == "__main__":
    main()
