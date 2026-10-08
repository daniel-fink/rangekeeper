"""Check local Markdown links, heading anchors and current documentation reachability.

Run from any directory with Python's standard library. Captured research, notebook
outputs and generated sites are not linted. Their linked files must still exist.
External URLs are not fetched. Markdown uses inline links or reference definitions;
HTML image/link attributes are also checked.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
LINK = re.compile(
    r"!?\[[^\]\n]*\]\(\s*(?:<([^>]+)>|([^\s)]+))"
    r"|^\s{0,3}\[[^\]\n]+\]:\s*(?:<([^>]+)>|(\S+))"
    r"|(?:href|src)=[\"']([^\"']+)[\"']",
    re.MULTILINE,
)


def prose(
    content: str,
) -> str:
    """Mask fenced blocks without changing line numbers."""
    result = []
    fence = ""
    for line in content.splitlines(keepends=True):
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match and not fence:
            fence = match[1]
        elif match and match[1][0] == fence[:1] and len(match[1]) >= len(fence):
            fence = ""
            result.append("\n")
            continue
        result.append("\n" if fence else line)
    return "".join(result)


def anchors(
    path: Path,
) -> set[str]:
    content = prose(path.read_text())
    found = set(re.findall(r"(?:id|name)=[\"\']([^\"\']+)[\"\']", content))
    counts: Counter[str] = Counter()
    for match in re.finditer(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", content, re.MULTILINE):
        heading = re.sub(r"<[^>]*>", "", match[1])
        heading = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", heading)
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        index = counts[slug]
        counts[slug] += 1
        found.add(f"{slug}-{index}" if index else slug)
    return found


def check() -> list[str]:
    current = {DOCS / "README.md"}
    for name in ("concepts", "reference", "guides", "contributing", "decisions"):
        current.update((DOCS / name).rglob("*.md"))
    sources = (
        current
        | set((DOCS / "history").rglob("*.md"))
        | {
            ROOT / "README.md",
            ROOT / "CONTRIBUTING.md",
            ROOT / "examples/README.md",
            ROOT / "examples/walkthrough/intro.md",
            DOCS / "research/README.md",
        }
    )
    errors = []
    edges: dict[Path, set[Path]] = {}
    headings: dict[Path, set[str]] = {}
    for source in sorted(sources):
        content = prose(source.read_text())
        edges[source] = set()
        for match in LINK.finditer(content):
            url = next(item for item in match.groups() if item is not None)
            parts = urlsplit(url)
            if parts.scheme or parts.netloc:
                continue
            location = f"{source.relative_to(ROOT)}:{content.count(chr(10), 0, match.start()) + 1}"
            path = unquote(parts.path)
            target = (source.parent / path).resolve() if path else source
            if not target.is_relative_to(ROOT):
                errors.append(f"{location}: link outside repository: {url}")
            elif not target.exists():
                errors.append(f"{location}: missing file: {url}")
            else:
                edges[source].add(target)
                if parts.fragment and target.suffix == ".md":
                    if target not in headings:
                        headings[target] = anchors(target)
                    if unquote(parts.fragment) not in headings[target]:
                        errors.append(f"{location}: missing heading: {url}")
    reached = set()
    pending = [DOCS / "README.md"]
    while pending:
        path = pending.pop()
        if path not in reached:
            reached.add(path)
            pending.extend(edges.get(path, ()))
    errors.extend(
        f"{path.relative_to(ROOT)}: not reachable from docs/README.md"
        for path in sorted(current - reached)
    )
    print(
        f"Checked {len(sources)} pages and navigation to {len(current)} current pages."
    )
    return errors


if __name__ == "__main__":
    problems = check()
    for problem in problems:
        print(problem)
    raise SystemExit(bool(problems))
