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
- ``api/``: one mkdocstrings page for each public ``rangekeeper`` module: the
  packages of the API snapshot, without ``market``, and each other module with
  its own ``__all__`` that exports a name that no package page shows.

A link from ``docs/`` to a lesson notebook goes to its page. A link to another
repository file outside ``docs/`` goes to the file on GitHub at ``REF``. The
files in ``docs/`` do not change. ``build`` runs a strict Zensical build to
``_build/site``; ``serve`` serves the staged pages on http://localhost:8000.
Neither publishes the site.
"""

from __future__ import annotations

import json
import os
import pkgutil
import re
import shutil
import subprocess
import sys
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
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


# The packages that the API reference leaves out: `market` is internal until
# #298; `schema` and `shared` are internal.
INTERNAL = frozenset({"market", "schema", "shared"})


def internal(name: str) -> bool:
    """Return whether the module ``name`` is internal or private."""
    parts = name.split(".")[1:]
    return bool(parts) and (
        parts[0] in INTERNAL or any(part.startswith("_") for part in parts)
    )


def exports(module: ModuleType) -> dict[str, object]:
    """Return the public names of ``module`` with their values.

    As in the API snapshot, a module with ``__all__`` exports those names, and
    a module without one exports the names that it defines.
    """
    names = getattr(module, "__all__", None)
    if names is None:
        return {
            name: value
            for name, value in vars(module).items()
            if not name.startswith("_")
            and getattr(value, "__module__", None) == module.__name__
        }
    return {name: getattr(module, name) for name in names if not name.startswith("_")}


def snapshot_packages() -> tuple[str, ...]:
    """Return the public packages of the API snapshot, ``tests/contracts/api.py``."""
    spec = spec_from_file_location("api_snapshot", ROOT / "tests/contracts/api.py")
    if spec is None or spec.loader is None:
        raise ImportError("cannot read tests/contracts/api.py")
    snapshot = module_from_spec(spec)
    spec.loader.exec_module(snapshot)
    return tuple(snapshot.PACKAGES)


def named_modules(module: ModuleType) -> set[str]:
    """Return the names of the modules that ``module`` exports."""
    return {
        value.__name__
        for value in exports(module).values()
        if isinstance(value, ModuleType)
    }


def public_modules(packages: list[ModuleType]) -> list[ModuleType]:
    """Return the public modules that are not in ``packages``, parents first.

    A module is public when it has its own ``__all__``, or when a public module
    exports it.
    """
    import rangekeeper

    known = {module.__name__ for module in packages}
    named = set().union(*map(named_modules, packages))
    found = []
    for info in pkgutil.walk_packages(rangekeeper.__path__, "rangekeeper."):
        if internal(info.name) or info.name in known:
            continue
        module = import_module(info.name)
        if hasattr(module, "__all__") or info.name in named:
            found.append(module)
            named |= named_modules(module)
    return found


def pages() -> list[ModuleType]:
    """Return the modules that get an API reference page, in name order.

    Each public package of the API snapshot gets a page, without ``market``.
    Each other public module gets a page when it exports an object that no
    earlier page shows; the page of its package shows the others.
    """
    packages = [
        import_module(name) for name in snapshot_packages() if not internal(name)
    ]
    shown = {id(value) for module in packages for value in exports(module).values()}
    found = list(packages)
    for module in public_modules(packages):
        members = {id(value) for value in exports(module).values()}
        if members - shown:
            found.append(module)
            shown |= members
    return sorted(found, key=lambda module: module.__name__)


def directive(module: ModuleType) -> str:
    """Return the mkdocstrings block for the public names of ``module``.

    Some ``__all__`` lists are built at import time, so mkdocstrings cannot read
    them from the source; the block names the members. A module without
    ``__all__`` shows the names that it defines. Submodules have their own pages.
    """
    if not hasattr(module, "__all__"):
        return f"::: {module.__name__}\n"
    members = [
        f"\n        - {name}"
        for name, value in exports(module).items()
        if not isinstance(value, ModuleType)
    ]
    listed = "".join(members) if members else " []"
    return f"::: {module.__name__}\n    options:\n      members:{listed}\n"


def page(name: str) -> str:
    """Return the file name of the API reference page of the module ``name``."""
    return f"{name.removeprefix('rangekeeper.')}.md"


def links(names: list[str]) -> str:
    """Return a Markdown list of links to the pages of the modules ``names``."""
    return "".join(f"- [`{name}`]({page(name)})\n" for name in names)


def api(output: Path) -> None:
    """Write the API reference: the root package, then one page for each module."""
    import rangekeeper

    modules = [module.__name__ for module in pages() if module is not rangekeeper]
    output.mkdir(parents=True)
    (output / "index.md").write_text(
        "# API reference\n\n"
        "Generated from the docstrings of the public `rangekeeper` package. "
        "The [contract reference](../README.md#look-up-a-contract) gives the "
        "rules that the records follow.\n\n"
        f"{directive(rangekeeper)}\n## Modules\n\n{links(modules)}"
    )
    for name in modules:
        children = [
            child
            for child in modules
            if child.startswith(f"{name}.") and "." not in child[len(name) + 1 :]
        ]
        submodules = f"\n## Modules\n\n{links(children)}" if children else ""
        (output / page(name)).write_text(
            f"# {name}\n\n{directive(import_module(name))}{submodules}"
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
