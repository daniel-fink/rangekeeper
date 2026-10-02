"""Compare captured current-schema structural cases using CUE 0.17.1.

The CUE schemas are projections of LinkML-generated JSON Schema, deliberately
not a second maintained authority. This tests the complete existing structural
corpus and interoperability, not CUE-first authoring or native semantic parity.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import statistics
import subprocess
import time


def run(command):
    started = time.perf_counter()
    try:
        process = subprocess.run(command, text=True, capture_output=True, timeout=5)
    except subprocess.TimeoutExpired:
        return None, time.perf_counter() - started
    return process, time.perf_counter() - started


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("captured", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cue", required=True)
    parser.add_argument("--bounded-raw", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    schemas, cases, suites = {}, {}, {}
    for file in sorted(args.captured.glob("*.json")):
        captured = json.loads(file.read_text())
        schemas.update(captured["schemas"])
        suites[captured["suite"]] = dict(
            cases=len(captured["cases"]),
            accepted=sum(row["accepted"] for row in captured["cases"].values()),
        )
        for identity, row in captured["cases"].items():
            if identity in cases:
                assert {k: cases[identity][k] for k in row} == row
                cases[identity]["suites"].append(captured["suite"])
            else:
                cases[identity] = dict(row, suites=[captured["suite"]])
    imports = {}
    for identity, schema in schemas.items():
        path = args.output / (identity + ".schema.json")
        path.write_text(json.dumps(schema, indent=2) + "\n")
        cue = args.output / (identity + ".cue")
        result, elapsed = run(
            [args.cue, "import", "jsonschema", str(path), "-p", "comparison", "-o", str(cue)]
        )
        imports[identity] = dict(accepted=result is not None and result.returncode == 0, seconds=elapsed,
                                 stderr=result.stderr[:3000] if result is not None else "import timeout")

    def compare(item):
        identity, row = item
        result = dict(identity=identity, schema=row["schema"], suites=row["suites"],
                      baseline=row["accepted"])
        try:
            encoded = json.dumps(row["document"], allow_nan=False)
        except ValueError:
            return dict(result, outcome="non_json_numeric_input")
        if not imports[row["schema"]]["accepted"]:
            return dict(result, outcome="import_failed")
        path = args.output / (identity + ".case.json")
        path.write_text(encoded + "\n")
        process, elapsed = run(
            [args.cue, "vet", "-c", str(args.output / (row["schema"] + ".cue")), str(path)]
        )
        if process is None:
            return dict(result, outcome="timeout", seconds=elapsed)
        accepted = process.returncode == 0
        result.update(cue=accepted, seconds=elapsed,
                      outcome="match" if accepted == row["accepted"] else "difference")
        if result["outcome"] == "difference":
            result.update(document=row["document"], stderr=process.stderr[:5000])
        return result

    if args.bounded_raw:
        rows, timed_out = [], set()
        for identity, row in sorted(cases.items()):
            if row["schema"] in timed_out:
                rows.append(dict(identity=identity, schema=row["schema"], suites=row["suites"],
                                 baseline=row["accepted"], outcome="unmeasured_after_schema_timeout"))
            else:
                result = compare((identity, row))
                rows.append(result)
                if result["outcome"] == "timeout":
                    timed_out.add(row["schema"])
    else:
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows = list(pool.map(compare, sorted(cases.items())))
    timings = [row["seconds"] for row in rows if "seconds" in row]
    outcomes = {name: sum(row["outcome"] == name for row in rows)
                for name in sorted({row["outcome"] for row in rows})}
    summary = dict(
        cue_version=subprocess.check_output([args.cue, "version"], text=True),
        schema_count=len(schemas), case_count=len(cases), suites=suites,
        bounded_raw=args.bounded_raw,
        outcomes=outcomes, imports=imports,
        process_validation_seconds=dict(median=statistics.median(timings),
                                        maximum=max(timings), total=sum(timings)),
    )
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.output / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k not in ["imports", "cue_version"]}, indent=2))


if __name__ == "__main__":
    main()
