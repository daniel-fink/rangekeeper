# Schema tooling probes

**Historical evidence:** this smaller study is preserved for reproduction.
The [accepted LinkML decision](../current-schema-comparison/DECISION.md) and
[current library plan](../../LIBRARY_ARCHITECTURE.md) govern continuation; rerunning
or extending this study is not a prerequisite for the next implementation stage.

Companion evidence for [the schema tooling review](../../SCHEMA_TOOLING_EVALUATION.md),
run on 2026-09-24. These files describe a synthetic test vocabulary. They are not
an adopted RK schema, numerical engine, or production dependency configuration.

## Contents and limits

- `probe.py`: creates fixtures, generates LinkML JSON Schema/Pydantic code, and
  compares those validators with explicit strict Pydantic models and graph checks.
- `probe.cue` and `cue_probe.py`: structural and explicitly authored semantic
  checks over the same documents; a separate recursive expression-tree check.
- `typespec/`: the corresponding TypeSpec definition and pinned npm dependencies.
- `export_probe.py`: checks TypeSpec/CUE JSON Schema exports and a CUE inverse
  arithmetic example that remains unresolved.
- `documentation_probe.py`: records LinkML documentation/cardinality differences.
- `check_results.py`: verifies the review's recorded observations.
- `observed/`: fixtures, generated representations, and results from this run.

The 20 fixtures contain two valid examples, thirteen structural errors, and five
graph-semantic errors. The graph checks were deliberately implemented; the tools
did not infer them. Unit checking here means matching strings, not dimensional
analysis. No solver, CRM, full Model/Specification/Run, performance, migration, or
Python-to-TypeScript round trip is tested.

`check_results.py` is an assertion about observed behaviour at the pinned
versions, including known differences. An upstream fix may intentionally change
those results. Evaluate such a change rather than treating this as a permanent
compatibility requirement for RK.

The Python dependency file pins direct dependencies. It is not a complete
transitive lock or a guarantee of byte-for-byte reproduction on future platforms.
The TypeSpec lockfile includes transitive versions/integrity metadata. Recorded
results are evidence of the actual environment, not a claim that every dependency
combination gives the same outcomes.

## Reproduce in a disposable directory

Requirements: Python 3.11, Node/npm compatible with the pinned TypeSpec packages,
and CUE 0.17.1. The recorded run used Python 3.11.16 and Node 24.19.0. Install CUE
from its [official release](https://github.com/cue-lang/cue/releases/tag/v0.17.1)
for your platform, verifying the published digest. The tested macOS arm64 archive
had SHA256 `64921403f012a97f89494c03605db2fbf7d9daa77dc2631819ac4406cb2e8074`.

Copy this folder to a disposable directory first. The scripts write generated
schemas, fixtures, results, and documentation next to themselves. Do not run them
over the checked-in evidence when the intention is to retain the original run.

From the copied folder:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export PYSTOW_HOME="$PWD/.pystow"
export CUE="/absolute/path/to/cue"
.venv/bin/python probe.py
.venv/bin/python cue_probe.py
"$CUE" def probe.cue -e '#Model' --out jsonschema -o cue.schema.json
"$CUE" def probe.cue -e '#SemanticModel' --out jsonschema -o cue-semantic.schema.json
```

In the copied `typespec/` directory:

```sh
npm ci
./node_modules/.bin/tsp compile .
```

Back in the copied probe directory:

```sh
.venv/bin/python export_probe.py
.venv/bin/python documentation_probe.py
.venv/bin/python check_results.py
```

To check only the retained results, with no third-party Python dependencies:

```sh
python3 check_results.py observed
```

The local implementation uses CUE subprocess validation. LinkML structural
generation uses `--closed --include-range-class-descendants --top-class Model`;
Pydantic generation uses `--extra-fields forbid`. TypeSpec enables
`seal-object-schemas`. These settings are part of the comparison, not incidental
details. JSON Schema validation uses the Python `jsonschema` package; no browser
validator is exercised.
