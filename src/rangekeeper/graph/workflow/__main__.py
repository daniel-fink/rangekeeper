"""Explicit artifact-producing command line entry point."""

import argparse
from pathlib import Path

from rangekeeper.graph.workflow import load, run
from rangekeeper.graph.workflow.review import export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    outcome = run(load(args.spec), input_root=args.inputs)
    if outcome.output is None:
        for d in outcome.diagnostics:
            print(f"{d.code}: {d.message}")
        return 1
    export(outcome.output, args.output)
    print(
        f"Built {len(outcome.output.graph.entities)} entities, {len(outcome.output.graph.relationships)} relationships, {len(outcome.output.checks)} checks: {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
