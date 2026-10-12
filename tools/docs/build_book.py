"""Build the accepted Jupyter Book 2 chapters from fresh notebook outputs.

The table of contents in myst.yml is the chapter acceptance list. This command
stages one copy of those sources and does not execute notebooks or publish them.
"""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import nbformat
import yaml

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "examples/walkthrough"


def chapter_files(entries):
    for entry in entries:
        if "file" in entry:
            yield entry["file"]
        yield from chapter_files(entry.get("children", []))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", type=Path, help="New directory for the staged book")
    parser.add_argument("executed", type=Path, help="Freshly executed notebooks")
    parser.add_argument(
        "--preview-chapter",
        action="append",
        default=[],
        help="Review a candidate chapter without adding it to the accepted TOC",
    )
    args = parser.parse_args()
    config = yaml.safe_load((SOURCE / "myst.yml").read_text())
    for name in args.preview_chapter:
        path = Path(name)
        if path.name != name or path.suffix != ".ipynb":
            raise ValueError("Preview chapters must be notebook filenames")
        if name not in chapter_files(config["project"]["toc"]):
            config["project"]["toc"].append({"file": name})
    files = list(chapter_files(config["project"]["toc"]))
    # Notebook source equality is not sufficient once cells import local helpers.
    # Compare the code copied into the execution directory before staging it.
    helpers = SOURCE / "helpers"
    expected_helpers = {
        p.relative_to(helpers): p.read_bytes()
        for p in helpers.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    executed_helpers = args.executed / "helpers"
    actual_helpers = {
        p.relative_to(executed_helpers): p.read_bytes()
        for p in executed_helpers.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    if actual_helpers != expected_helpers:
        raise ValueError(
            "Executed walkthrough helpers do not match source; copy them and re-execute"
        )
    notebooks = {}
    # Validate before creating the stage or invoking the renderer.
    for name in files:
        if Path(name).suffix != ".ipynb":
            continue
        authored = nbformat.read(SOURCE / name, as_version=4)
        executed = nbformat.read(args.executed / name, as_version=4)
        nbformat.validate(executed)
        if [(c.cell_type, c.source) for c in authored.cells] != [
            (c.cell_type, c.source) for c in executed.cells
        ]:
            raise ValueError(f"Executed notebook does not match source: {name}")
        code = [c for c in executed.cells if c.cell_type == "code" and c.source.strip()]
        if [c.execution_count for c in code] != list(range(1, len(code) + 1)):
            raise ValueError(f"Notebook needs a complete fresh execution: {name}")
        if any(o.output_type == "error" for c in code for o in c.outputs):
            raise ValueError(f"Notebook contains an execution error: {name}")
        notebooks[name] = executed

    stage = args.stage.resolve()
    stage.mkdir(parents=True, exist_ok=False)
    (stage / "myst.yml").write_text(yaml.safe_dump(config, sort_keys=False))
    shutil.copy2(SOURCE / "references.bib", stage / "references.bib")
    for name in ("resources", "_static", "data", "helpers"):
        if (SOURCE / name).is_dir():
            shutil.copytree(
                SOURCE / name,
                stage / name,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
    for name in files:
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if name in notebooks:
            # Book routes have a chapter directory; notebook servers do not.
            # Rewrite only our local output iframe paths in the staged copy.
            for cell in notebooks[name].cells:
                for output in cell.get("outputs", []):
                    data = output.get("data", {})
                    if "text/html" in data:
                        data["text/html"] = re.sub(
                            r'(src=")(resources/|design-output/)',
                            r"\1../\2",
                            data["text/html"],
                        )
            nbformat.write(notebooks[name], target)
        else:
            shutil.copy2(SOURCE / name, target)
    if (args.executed / "design-output").exists():
        shutil.copytree(args.executed / "design-output", stage / "design-output")
    subprocess.run(
        [
            str(Path(sys.executable).parent / "jupyter-book"),
            "build",
            "--html",
            "--strict",
        ],
        cwd=stage,
        check=True,
    )
    # Raw HTML iframes are not discovered as MyST image dependencies. Keep their
    # relative assets together, including the offline viewer's source archive.
    for name in ("resources", "design-output", "data", "helpers"):
        if (stage / name).is_dir():
            shutil.copytree(
                stage / name, stage / "_build/html" / name, dirs_exist_ok=True
            )
    print("Built", stage / "_build/html")
    print("Chapters:", json.dumps(files))


if __name__ == "__main__":
    main()
