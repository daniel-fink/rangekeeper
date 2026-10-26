"""Print the changelog section for one release version.

Usage: python .github/scripts/release_notes.py VERSION

The release workflow uses the output as the GitHub Release notes. The script
looks for the first changelog file that exists and prints the body of the first
heading that contains VERSION as a separate token, up to the next heading of the
same or a higher level. It prints nothing when no file or section matches; the
workflow then uses GitHub's generated notes. It needs only the standard library.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHANGELOGS = ("CHANGELOG.md", "docs/changelog.md", "CHANGES.md")
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def section(
    text: str,
    version: str,
) -> str:
    """Return the body under the heading for `version`, or an empty string."""
    token = re.compile(rf"(?<![\w.])v?{re.escape(version)}(?![\w.])")
    level = 0
    body: list[str] = []
    for line in text.splitlines():
        match = HEADING.match(line)
        if level:
            if match and len(match[1]) <= level:
                break
            body.append(line)
        elif match and token.search(match[2]):
            level = len(match[1])
    return "\n".join(body).strip()


def main(
    argv: list[str],
) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    for name in CHANGELOGS:
        path = ROOT / name
        if path.is_file():
            notes = section(path.read_text(encoding="utf-8"), argv[1])
            if notes:
                print(notes)
                return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
