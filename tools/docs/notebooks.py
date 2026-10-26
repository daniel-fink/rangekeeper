"""Convert executed walkthrough lessons to Markdown pages for the docs site.

Usage: python tools/docs/notebooks.py OUTPUT NOTEBOOK... [--allow-unexecuted]

Each ``NN_slug.ipynb`` becomes ``OUTPUT/NN_slug.md``. Images from outputs and
cell attachments go to ``OUTPUT/NN_slug_files/``. Local files that a Markdown
cell links to, for example ``resources/...``, are copied with the same relative
path. The tool uses only Python's standard library. It does not execute
notebooks: execute them first, from a fresh kernel. A code cell without an
execution count or with an error output stops the conversion.

Cell tags change the page:

- ``remove-cell``: leave out the cell.
- ``remove-input``: show only the outputs.
- ``remove-output``: show only the source.
- ``solution``: put the source and outputs in a collapsed "Solution" block.
"""

from __future__ import annotations

import base64
import json
import re
import shutil
import sys
from pathlib import Path

NAME = re.compile(r"^\d{2}_[a-z0-9]+(?:_[a-z0-9]+)*$")
IMAGES = {"image/png": ".png", "image/jpeg": ".jpg", "image/svg+xml": ".svg"}
LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*<?([^\s)>]+)>?|(?:href|src)=[\"']([^\"']+)[\"']")


class ConversionError(ValueError):
    """A notebook cannot become a page."""


def text(value: str | list[str]) -> str:
    return value if isinstance(value, str) else "".join(value)


def fence(body: str, language: str = "") -> str:
    longest = max((len(run) for run in re.findall(r"`{3,}", body)), default=2)
    ticks = "`" * (longest + 1)
    return f"{ticks}{language}\n{body.rstrip(chr(10))}\n{ticks}"


def html_block(body: str) -> str:
    # Python-Markdown ends a raw HTML block at a blank line.
    lines = [line for line in body.strip().splitlines() if line.strip()]
    return '<div class="rk-output" markdown="0">\n' + "\n".join(lines) + "\n</div>"


class Page:
    def __init__(self, source: Path, output: Path):
        self.source = source
        self.output = output
        self.files = output / f"{source.stem}_files"
        self.copied: set[Path] = set()
        self.count = 0

    def write(self, data: bytes, suffix: str) -> str:
        self.count += 1
        self.files.mkdir(parents=True, exist_ok=True)
        name = f"output_{self.count}{suffix}"
        (self.files / name).write_bytes(data)
        return f"{self.files.name}/{name}"

    def markdown(self, cell: dict) -> str:
        body = text(cell["source"])
        for name, bundle in (cell.get("attachments") or {}).items():
            mime = next((m for m in IMAGES if m in bundle), None)
            if mime is None:
                raise ConversionError(f"{self.source.name}: attachment {name}")
            data = text(bundle[mime])
            raw = data.encode() if mime == "image/svg+xml" else base64.b64decode(data)
            body = body.replace(f"attachment:{name}", self.write(raw, IMAGES[mime]))
        for match in LINK.finditer(body):
            target = match[1] or match[2]
            if re.match(r"^[a-z][a-z0-9+.-]*:|^#|^/", target):
                continue
            self.copy(target.split("#")[0].split("?")[0])
        return body

    def copy(self, relative: str) -> None:
        if not relative or relative.startswith(f"{self.files.name}/"):
            return
        root = self.source.parent.resolve()
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ConversionError(
                f"{self.source.name}: link outside lessons: {relative}"
            )
        if not path.is_file():
            raise ConversionError(f"{self.source.name}: missing file: {relative}")
        if path not in self.copied:
            self.copied.add(path)
            target = self.output / path.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)

    def outputs(self, cell: dict, index: int) -> list[str]:
        parts = []
        for output in cell.get("outputs", ()):
            kind = output["output_type"]
            if kind == "error":
                raise ConversionError(
                    f"{self.source.name}: cell {index}: {output['ename']}"
                )
            if kind == "stream":
                parts.append(fence(text(output["text"]), "text"))
                continue
            data = output.get("data", {})
            mime = next((m for m in IMAGES if m in data), None)
            if mime is not None:
                raw = text(data[mime])
                content = (
                    raw.encode() if mime == "image/svg+xml" else base64.b64decode(raw)
                )
                parts.append(f"![]({self.write(content, IMAGES[mime])})")
            elif "text/html" in data:
                parts.append(html_block(text(data["text/html"])))
            elif "text/markdown" in data:
                parts.append(text(data["text/markdown"]))
            elif "text/plain" in data:
                parts.append(fence(text(data["text/plain"]), "text"))
        return parts

    def code(self, cell: dict, index: int, allow_unexecuted: bool) -> str:
        tags = set(cell.get("metadata", {}).get("tags", ()))
        if "remove-cell" in tags:
            return ""
        source = text(cell["source"])
        if cell.get("execution_count") is None and source.strip():
            if not allow_unexecuted:
                raise ConversionError(f"{self.source.name}: cell {index} not executed")
        parts = [] if "remove-input" in tags else [fence(source, "python")]
        if "remove-output" not in tags:
            parts.extend(self.outputs(cell, index))
        body = "\n\n".join(part for part in parts if part)
        if "solution" in tags and body:
            indented = "\n".join(
                f"    {line}" if line else "" for line in body.splitlines()
            )
            return f'??? success "Solution"\n\n{indented}'
        return body


def convert(source: Path, output: Path, *, allow_unexecuted: bool = False) -> Path:
    """Write one lesson page and its files; return the page path."""
    if source.suffix != ".ipynb" or not NAME.match(source.stem):
        raise ConversionError(f"{source.name}: lesson names are NN_slug.ipynb")
    notebook = json.loads(source.read_text())
    if notebook.get("nbformat") != 4:
        raise ConversionError(f"{source.name}: nbformat 4 is required")
    output.mkdir(parents=True, exist_ok=True)
    page = Page(source, output)
    shutil.rmtree(page.files, ignore_errors=True)
    blocks = []
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "markdown":
            blocks.append(page.markdown(cell))
        elif cell["cell_type"] == "code":
            blocks.append(page.code(cell, index, allow_unexecuted))
    path = output / f"{source.stem}.md"
    path.write_text("\n\n".join(block for block in blocks if block.strip()) + "\n")
    return path


def main(arguments: list[str]) -> int:
    allow = "--allow-unexecuted" in arguments
    paths = [argument for argument in arguments if argument != "--allow-unexecuted"]
    if len(paths) < 2:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    output, sources = Path(paths[0]), [Path(path) for path in paths[1:]]
    try:
        for source in sorted(sources, key=lambda path: path.name):
            print(convert(source, output, allow_unexecuted=allow))
    except ConversionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
