"""Convert supported rk.graph/v1 JSON into a new directory, with a review report."""

import argparse
import json
from pathlib import Path

from .graph import convert_graph
from ..io import json as codec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument(
        "output", type=Path, help="new output directory; never overwritten"
    )
    parser.add_argument(
        "--value-keys", type=Path, help="JSON mapping of Value UUID to reviewed key"
    )
    args = parser.parse_args()
    keys = json.loads(args.value_keys.read_text()) if args.value_keys else None
    result = convert_graph(args.source.read_text(encoding="utf-8"), value_keys=keys)
    args.output.mkdir(parents=True, exist_ok=False)
    report = {
        "source": str(args.source.resolve()),
        "source_sha256": result.source_sha256,
        "identity_map": dict(result.identity_map),
        "issues": result.issues,
        "model": "model.json" if result.model is not None else None,
    }
    if result.model is not None:
        codec.write(result.model, args.output / "model.json")
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if result.model is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
