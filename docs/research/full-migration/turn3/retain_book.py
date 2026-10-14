"""Replace generated walkthrough outputs from an accepted temporary build.

Back up the previous generated trees outside Git first. This does not edit source
notebooks, publish a site, or remove historical research evidence.
"""

from pathlib import Path
import argparse
import json
import shutil

ROOT = Path(__file__).resolve().parents[4]
p = argparse.ArgumentParser()
p.add_argument("book", type=Path)
p.add_argument("executed", type=Path)
p.add_argument("backup", type=Path)
a = p.parse_args()
a.backup.mkdir(parents=True, exist_ok=False)
target = ROOT / "walkthrough/_build"
for name in ("html", "jupyter_execute"):
    previous = target / name
    if previous.exists():
        shutil.copytree(previous, a.backup / name)
        shutil.rmtree(previous)
shutil.copytree(a.book / "_build/html", target / "html")
(target / "jupyter_execute").mkdir()
for source in (ROOT / "walkthrough").glob("*.ipynb"):
    accepted = a.executed / source.name
    document = json.loads(accepted.read_text())
    assert not any(
        output.get("output_type") == "error"
        for cell in document["cells"]
        for output in cell.get("outputs", [])
    )
    shutil.copy2(accepted, target / "jupyter_execute" / source.name)
# Normalize empty generated lines only; preserve visible text and script data.
for generated in (target / "html").rglob("*"):
    if generated.suffix in (".html", ".js", ".css"):
        text = generated.read_text()
        normalized = "".join(
            "\n" if not line.strip() else line
            for line in text.splitlines(keepends=True)
        )
        if normalized != text:
            generated.write_text(normalized)
print("Retained generated site and seven executed notebooks; previous trees backed up")
