"""Stage, build or serve the docs site with Zensical (ADR-018).

Usage, from the repository root:

    uv run --locked --all-extras --group docs python tools/docs/site.py serve
    uv run --locked --all-extras --group docs python tools/docs/site.py build
    uv run --locked --all-extras --group docs python tools/docs/site.py stage

Options: ``--no-lessons`` skips the lessons; ``--ref REF`` sets the git ref of
source links (default ``develop``).

``stage`` copies ``docs/`` to ``_build/docs`` and adds the generated pages:

- ``walkthrough/``: each lesson, executed from a fresh kernel in the locked
  walkthrough environment and converted by ``notebooks.py``;
- ``api/``: one mkdocstrings page for each public ``rangekeeper`` module.

A link from ``docs/`` to a lesson notebook goes to its page. A link to another
repository file outside ``docs/`` goes to the file on GitHub at ``REF``. The
files in ``docs/`` do not change. ``build`` runs a strict Zensical build to
``_build/site``; ``serve`` serves the staged pages on http://localhost:8000.
Neither publishes the site.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from types import ModuleType
from urllib.parse import unquote, urlsplit

from notebooks import NAME, convert

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
LESSONS = ROOT / "examples" / "walkthrough"
BUILD = ROOT / "_build"
STAGE = BUILD / "docs"
EXECUTED = BUILD / "lessons"
CONFIG = ROOT / "zensical.toml"
REPOSITORY = "https://github.com/daniel-fink/rangekeeper"

# Inline links and images, reference definitions, and HTML href/src attributes.
LINK = re.compile(
    r"(?P<lead>\]\(\s*<?|^\s{0,3}\[[^\]\n]+\]:\s*<?|(?:href|src)=[\"'])"
    r"(?P<url>[^\s)>\"']+)",
    re.MULTILINE,
)
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


def location(source: Path, page: Path, url: str, *, ref: str, lessons: bool) -> str:
    """Return the site link for a link in ``source``, staged as ``page``."""
    parts = urlsplit(url)
    if parts.scheme or parts.netloc or not parts.path:
        return url
    path = (source.parent / unquote(parts.path)).resolve()
    if path.is_relative_to(DOCS) or not path.is_relative_to(ROOT):
        return url
    fragment = f"#{parts.fragment}" if parts.fragment else ""
    if lessons and path.parent == LESSONS and NAME.match(path.stem):
        lesson = STAGE / "walkthrough" / f"{path.stem}.md"
        return Path(os.path.relpath(lesson, page.parent)).as_posix() + fragment
    kind = "tree" if path.is_dir() else "blob"
    return f"{REPOSITORY}/{kind}/{ref}/{path.relative_to(ROOT).as_posix()}{fragment}"


def rewrite(source: Path, page: Path, *, ref: str, lessons: bool) -> None:
    """Write ``source`` to ``page`` with links outside ``docs/`` resolved."""
    lines = []
    fence = ""
    for line in source.read_text().splitlines(keepends=True):
        match = FENCE.match(line)
        if match and not fence:
            fence = match[1]
        elif match and match[1][0] == fence[:1] and len(match[1]) >= len(fence):
            fence = ""
        elif not fence:
            line = LINK.sub(
                lambda link: (
                    link["lead"]
                    + location(source, page, link["url"], ref=ref, lessons=lessons)
                ),
                line,
            )
        lines.append(line)
    page.write_text("".join(lines))


def execute(output: Path) -> None:
    """Run each lesson from a fresh kernel and write the executed copies."""
    import nbformat
    from nbclient import NotebookClient

    shutil.rmtree(output, ignore_errors=True)
    # The executed copies keep the lessons' relative links to their resources.
    shutil.copytree(LESSONS / "resources", output / "resources")
    for lesson in sorted(LESSONS.glob("*.ipynb")):
        notebook = nbformat.read(lesson, as_version=4)
        NotebookClient(
            notebook,
            timeout=1800,
            kernel_name="python3",
            resources={"metadata": {"path": str(LESSONS)}},
        ).execute()
        nbformat.write(notebook, output / lesson.name)
        print(output / lesson.name)


def title(lesson: Path) -> str:
    """Return the first heading of a lesson."""
    for cell in json.loads(lesson.read_text())["cells"]:
        source = "".join(cell["source"])
        match = re.search(r"^# (.+)$", source, re.MULTILINE)
        if cell["cell_type"] == "markdown" and match:
            return match[1].strip()
    return lesson.stem


def walkthrough(output: Path, *, ref: str, lessons: bool) -> None:
    """Write the lesson pages and their index."""
    output.mkdir(parents=True)
    if lessons:
        environment = {**os.environ}
        # The walkthrough has its own locked environment, not the docs one.
        environment.pop("VIRTUAL_ENV", None)
        command = [
            *("uv", "run", "--project", str(LESSONS), "--locked"),
            *("--no-default-groups", "--group", "test"),
            *("python", __file__, "execute", str(EXECUTED)),
        ]
        subprocess.run(command, check=True, cwd=ROOT, env=environment)
        for executed in sorted(EXECUTED.glob("*.ipynb")):
            convert(executed, output)
    entries = []
    for lesson in sorted(LESSONS.glob("*.ipynb")):
        link = (
            f"{lesson.stem}.md"
            if lessons
            else f"{REPOSITORY}/blob/{ref}/examples/walkthrough/{lesson.name}"
        )
        entries.append(f"- [{title(lesson)}]({link})")
    note = (
        "Each page shows a lesson after a run from a fresh kernel."
        if lessons
        else "This build leaves out the lessons; the links go to the notebooks."
    )
    (output / "index.md").write_text(
        "# Walkthrough\n\n"
        "The walkthrough teaches the library in seven lessons. "
        f"{note} To run the lessons yourself, see "
        "[Run the walkthroughs](../guides/walkthroughs.md).\n\n"
        + "\n".join(entries)
        + "\n"
    )


def directive(module: ModuleType, *, heading: bool = False) -> str:
    """Return the mkdocstrings blocks for the names in ``module.__all__``.

    Some ``__all__`` lists are built at import time, so mkdocstrings cannot read
    them from the source; the block names the members. A module without
    ``__all__`` shows its public names. A public submodule of a page's module
    gets its own block, under its own heading.
    """
    names = getattr(module, "__all__", None)
    public = {name: getattr(module, name) for name in names or ()}
    options = ["show_root_heading: true"] if heading else []
    if names is not None:
        options.append("members:")
        options.extend(
            f"  - {name}"
            for name, value in public.items()
            if not name.startswith("_") and not isinstance(value, ModuleType)
        )
    lines = "".join(f"\n      {option}" for option in options)
    blocks = [f"::: {module.__name__}" + (f"\n    options:{lines}" if lines else "")]
    blocks.extend(
        directive(value, heading=True)
        for value in public.values()
        if isinstance(value, ModuleType)
        and value.__name__.startswith(f"{module.__name__}.")
        and module.__name__ != "rangekeeper"
    )
    return "\n\n".join(block.rstrip("\n") for block in blocks) + "\n"


# Public modules that their package does not import, because each needs an
# optional dependency. Their blocks follow the package's own blocks.
OPTIONAL_MODULES = {"io": ("rangekeeper.io.bundle", "rangekeeper.io.polars")}


def api(output: Path) -> None:
    """Write one API reference page for each public module."""
    import rangekeeper

    public = [name for name in rangekeeper.__all__ if not name.startswith("_")]
    modules = [name for name in public if find_spec(f"rangekeeper.{name}")]
    output.mkdir(parents=True)
    links = "".join(f"- [`rangekeeper.{name}`]({name}.md)\n" for name in modules)
    (output / "index.md").write_text(
        "# API reference\n\n"
        "Generated from the docstrings of the public `rangekeeper` package. "
        "The [contract reference](../README.md#look-up-a-contract) gives the "
        "rules that the records follow.\n\n"
        f"{directive(rangekeeper)}\n## Modules\n\n{links}"
    )
    for name in modules:
        module = import_module(f"rangekeeper.{name}")
        blocks = [directive(module)] + [
            directive(import_module(optional), heading=True)
            for optional in OPTIONAL_MODULES.get(name, ())
        ]
        (output / f"{name}.md").write_text(
            f"# rangekeeper.{name}\n\n" + "\n".join(blocks)
        )


def stage(*, ref: str, lessons: bool) -> None:
    """Copy docs/ to the staging folder and add the generated pages."""
    shutil.rmtree(STAGE, ignore_errors=True)
    shutil.copytree(DOCS, STAGE)
    for page in STAGE.rglob("*.md"):
        rewrite(DOCS / page.relative_to(STAGE), page, ref=ref, lessons=lessons)
    walkthrough(STAGE / "walkthrough", ref=ref, lessons=lessons)
    api(STAGE / "api")
    print(f"Staged {STAGE.relative_to(ROOT)}", flush=True)


def main(arguments: list[str]) -> int:
    lessons = "--no-lessons" not in arguments
    arguments = [argument for argument in arguments if argument != "--no-lessons"]
    ref = "develop"
    if "--ref" in arguments:
        index = arguments.index("--ref")
        ref = arguments[index + 1]
        del arguments[index : index + 2]
    if len(arguments) == 2 and arguments[0] == "execute":
        execute(Path(arguments[1]))
        return 0
    if len(arguments) != 1 or arguments[0] not in ("stage", "build", "serve"):
        print("\n\n".join(__doc__.split("\n\n")[1:4]), file=sys.stderr)
        return 2
    stage(ref=ref, lessons=lessons)
    zensical = [sys.executable, "-m", "zensical"]
    if arguments[0] == "build":
        command = [*zensical, "build", "--strict", "--config-file", str(CONFIG)]
    elif arguments[0] == "serve":
        command = [*zensical, "serve", "--config-file", str(CONFIG)]
    else:
        return 0
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
