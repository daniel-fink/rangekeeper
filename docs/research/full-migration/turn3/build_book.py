"""Regenerate the walkthrough site from the accepted, freshly executed notebooks.

This does not publish. The original notebook files remain the only authoring
source. The temporary book receives execution outputs from this turn's wheel.
No old build cache or stored historical kernel state is reused.
"""

from pathlib import Path
import json, shutil, subprocess, sys, yaml
from html import escape

ROOT = Path(__file__).resolve().parents[4]
stage = Path(sys.argv[1])
executed = Path(sys.argv[2])
stage.mkdir(parents=True, exist_ok=False)
for name in ("_config.yml", "_toc.yml", "intro.md", "references.bib"):
    shutil.copy2(ROOT / "walkthrough" / name, stage / name)
for name in ("resources", "_static"):
    if (ROOT / "walkthrough" / name).is_dir():
        shutil.copytree(ROOT / "walkthrough" / name, stage / name)
for notebook in (ROOT / "walkthrough").glob("*.ipynb"):
    assert (executed / notebook.name).is_file(), notebook
    document = json.loads((executed / notebook.name).read_text())
    # Jupyter Book 1 does not render Plotly's notebook MIME type. Derive HTML
    # from the captured figure data, with one local JS asset and no network.
    for cell_index, cell in enumerate(document["cells"]):
        for output_index, output in enumerate(cell.get("outputs", [])):
            data = output.get("data", {})
            figure = data.pop("application/vnd.plotly.v1+json", None)
            if figure is not None:
                identity = f"plotly-{notebook.stem}-{cell_index}-{output_index}"
                payload = json.dumps(figure).replace("<", "\\u003c")
                data["text/html"] = (
                    f'<div id="{escape(identity)}" style="width:100%;height:600px"></div>'
                    f'<script src="_static/plotly.min.js"></script><script>'
                    f"var figure={payload};Plotly.newPlot({json.dumps(identity)},figure.data,figure.layout,figure.config);</script>"
                )
    (stage / notebook.name).write_text(json.dumps(document, indent=1))
plotly_js = Path(sys.argv[3])
(stage / "_static").mkdir(exist_ok=True)
shutil.copy2(plotly_js, stage / "_static/plotly.min.js")
config = yaml.safe_load((stage / "_config.yml").read_text())
config["execute"]["execute_notebooks"] = "off"
config["sphinx"]["config"]["html_extra_path"] = []
(stage / "_config.yml").write_text(yaml.safe_dump(config, sort_keys=False))
subprocess.run(
    [str(Path(sys.executable).parent / "jupyter-book"), "build", str(stage), "--all"],
    check=True,
)
# Keep one copy of offline notebook artifacts, at their declared relative URLs.
if (executed / "design-output").exists():
    shutil.copytree(
        executed / "design-output",
        stage / "_build/html/design-output",
        dirs_exist_ok=True,
    )
print("Built", stage / "_build/html")
