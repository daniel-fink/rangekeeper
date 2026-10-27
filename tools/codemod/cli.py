"""Command line for the rename pass."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import Codemod, build_index, index_from_json, index_to_json
from .renamemap import REQUIREMENTS, MapError, RenameMap

DEFAULT_MAP = Path(__file__).with_name("rename_map.yaml")


def parser() -> argparse.ArgumentParser:
    """Return the argument parser."""
    result = argparse.ArgumentParser(
        prog="python -m tools.codemod",
        description=(
            "Apply the 1.0 rename map. Without --apply, report the changes and write nothing."
        ),
    )
    result.add_argument(
        "--root", type=Path, default=Path.cwd(), help="Repository or project folder."
    )
    result.add_argument(
        "--map", type=Path, default=DEFAULT_MAP, help="Rename map (YAML)."
    )
    result.add_argument(
        "--apply", action="store_true", help="Write the changes and moves."
    )
    result.add_argument(
        "--consumer",
        action="store_true",
        help="Rewrite references only; move no files. For code that uses the package.",
    )
    result.add_argument(
        "--index",
        type=Path,
        help="Frozen index of the old package (from --write-index); needed in consumer mode "
        "when the old package source is not under --root.",
    )
    result.add_argument(
        "--write-index", type=Path, help="Write the index of the old package and stop."
    )
    result.add_argument(
        "--include-pending",
        action="store_true",
        help="Also apply entries that wait for a decision. For trials only.",
    )
    result.add_argument(
        "--with",
        dest="allow",
        action="append",
        default=[],
        choices=sorted(REQUIREMENTS),
        help="Also apply entries that need this follow-up work.",
    )
    result.add_argument(
        "--format", action="store_true", help="Run ruff on the changed Python files."
    )
    result.add_argument(
        "--check",
        action="store_true",
        help="Exit with status 1 when a change is needed.",
    )
    result.add_argument("--json", type=Path, help="Write the report as JSON.")
    result.add_argument(
        "-v", "--verbose", action="store_true", help="List every change."
    )
    result.add_argument(
        "paths", nargs="*", help="Limit the run to these paths under --root."
    )
    return result


def main(argv: list[str] | None = None) -> int:
    """Run the codemod and return the exit status."""
    args = parser().parse_args(argv)
    try:
        rename_map = RenameMap.load(
            args.map, include_pending=args.include_pending, allow=args.allow
        )
    except MapError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.write_index:
        source = args.root / rename_map.package_root
        args.write_index.write_text(
            index_to_json(build_index(source, rename_map.package))
        )
        return 0
    index = index_from_json(args.index.read_text()) if args.index else None
    try:
        codemod = Codemod(
            args.root,
            rename_map,
            consumer=args.consumer,
            index=index,
            targets=args.paths,
        )
        report = codemod.run(apply=args.apply, format_code=args.format)
    except MapError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(report.summary(verbose=args.verbose))
    if not args.apply and report.changed:
        print("\nNothing written. Use --apply to write the changes.")
    if args.json:
        args.json.write_text(report.to_json())
    if report.errors:
        return 2
    return 1 if args.check and report.changed else 0
