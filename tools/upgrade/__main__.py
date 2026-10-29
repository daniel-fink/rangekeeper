"""Convert documents and Bundles of earlier releases: `python -m tools.upgrade`."""

import argparse
import json
import sys
from pathlib import Path

import yaml

from rangekeeper.io import json as json_codec
from rangekeeper.io import yaml as yaml_codec

from .bundle import KINDS, upgrade
from .convert import RELEASES, ConversionError, convert, kind_of


def documents(paths: list[Path], output: Path, *, release: str) -> None:
    """Write each converted document to ``output`` with its file name and format."""
    output.mkdir(parents=True, exist_ok=True)
    for path in paths:
        text = path.read_text(encoding="utf-8")
        is_yaml = path.suffix in (".yaml", ".yml")
        data = yaml.safe_load(text) if is_yaml else json.loads(text)
        kind = kind_of(data)
        document = KINDS[kind].from_data(data=convert(data, kind, release=release))
        codec = yaml_codec if is_yaml else json_codec
        codec.write(document=document, path=output / path.name)
        print(f"{path} -> {output / path.name} ({kind} {document.id})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.upgrade", description=__doc__
    )
    commands = parser.add_subparsers(dest="command", required=True)
    files = commands.add_parser("documents", help="convert JSON or YAML documents")
    files.add_argument("paths", type=Path, nargs="+")
    files.add_argument("--output", type=Path, required=True)
    bundle = commands.add_parser("bundle", help="convert a Bundle to a new Bundle")
    bundle.add_argument("source", type=Path)
    bundle.add_argument("destination", type=Path)
    for command in (files, bundle):
        command.add_argument(
            "--from",
            dest="release",
            choices=sorted(RELEASES),
            default="0.x",
            help="the release that wrote the input (default: 0.x)",
        )
    args = parser.parse_args(argv)
    try:
        if args.command == "documents":
            documents(args.paths, args.output, release=args.release)
        else:
            manifest = upgrade(args.source, args.destination, release=args.release)
            print(f"{args.source} -> {args.destination} (Bundle {manifest['id']})")
    except (ConversionError, FileExistsError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
