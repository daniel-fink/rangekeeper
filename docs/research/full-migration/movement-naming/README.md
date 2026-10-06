# Movement naming verification — 2026-10-06

The approved rename is implemented on `acausal-modelling`, based on
`90c2e00ba7b942a8830960e3df3f3ff616f30fa1`, with the existing uncommitted migration
work preserved. LinkML remains authoritative. This checkpoint changes names in
the unreleased Model 0.4.0 draft; it does not change Flow semantics or perform the
planned `temporal` → `duration` namespace migration.

## Contract

| Previous name | Current name |
|---|---|
| `FlowSample` | `Movement` |
| `Flow.samples`, constructor `samples=`, JSON/YAML `samples` | `Flow.movements`, constructor `movements=`, JSON/YAML `movements` |
| `sample_coordinate` | `movement_coordinate` |
| `resolve_date(sample=...)` | `resolve_date(movement=...)` |
| Private `replace_sample` / `replace_samples` | `replace_movement` / `replace_movements` |

A Movement is one numerical entry in a Flow. Its fields remain `key`, `date`,
`period`, `magnitude` and `claims`. Units belong to the containing Flow. The
overall model logic supplies meaning; no semantic Flow kind or basis is added.
Dates, half-open periods, alignment, missingness, immutability, evidence references
and arithmetic retain their behavior. Statistical sampling and `resample()` keep
their existing names.

The schema, generated records, validation, calculations, dataframe adapters,
local consumers and DCF walkthrough use the new names. There are no compatibility
aliases. Old `samples` payloads are rejected, including payloads containing both
field names. Upgrade saved draft data explicitly, preserve entry order and every
entry field, and save a new Model revision. Do not overwrite historical snapshots.
See the [contract](../../../history/FULL_MIGRATION_TURN1.md#movement-naming) and
[upgrade guide](../../../LEGACY_UPGRADE_GUIDE.md).

## Results

| Check | Result | Evidence |
|---|---|---|
| Focused Flow, date, finance and consumer tests | 147 passed | [Log](focused.log) |
| Full local Python suite | 946 passed; seven existing legacy-duration deprecation warnings | [Log](pytest-local.log), [XML](pytest-local.xml) |
| Seven schema suites | All passed | `schema-*.log`; [exact commands](commands.jsonl) |
| Generated artifact freshness | Passed; 56 classes, five artifacts | [Log](generation.log) |
| Native/public Flow round trips | Passed for date, period and combined coordinates | [Probe](native_flow.py), [log](native-flow.log) |
| Static types | 105 source files passed; intended invalid examples rejected | [Log](typecheck.log) |
| Installed wheel | Records, lightweight imports, stores, graph, finance, scalar execution and workflow checks passed | [Log](installed.log) |
| Installed DCF notebook | 23 code cells executed; no errors; independent oracle and $1,000 PV passed | [Notebook](basic_dcf.ipynb), [HTML](basic_dcf.html), [inspection](notebook-inspection.json) |
| Upgrade-guide Python examples | Passed against the installed wheel outside the checkout | [Source](guide_example.py), [log](guide.log) |
| Exact rename audit | Eight runtime modules and generated slot contracts differ from the previous checkpoint only by the approved naming substitution | [Audit](rename-audit.json), [script](audit_rename.py) |

The focused tests include rejection of the old and mixed serialized field names,
and an unknown Claim under `movements`. Existing tests cover dates, units,
omission/null/zero, nested immutability, detached exports, serialization and
calculation results. The exact rename audit compares full Python syntax trees,
including docstrings and error strings, after applying only the approved name
substitutions to the previous installed source. It also compares generated slot
contracts. The previous bytes must match the starting fingerprints before the
comparison can pass.

Three live-service tests in `tests/test_api.py` were excluded. This checkpoint does
not claim external-service or downstream-repository compatibility. Notebook
outputs, execution order and table markup were checked programmatically; a visual
browser review was not performed.

## Reproduction and retained inputs

[Starting state](before.json) records the branch, HEAD, dirty files and 344 input
hashes. [Environment](environment.json) records the interpreters and package
versions. [Commands](commands.jsonl) records each verification command, working
directory, environment overrides, timeout, duration, exit code and log.
[Final state](final-state.json) records input hashes, changed inputs, test totals
and source-to-wheel equality. The [API catalog](api.json) records current handwritten
signatures and docstrings.

Run from `/Volumes/Data/Projects/Rangekeeper`, using the recorded environments:

```sh
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python docs/research/full-migration/movement-naming/verify.py focused
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python docs/research/full-migration/movement-naming/verify.py checks
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python docs/research/full-migration/movement-naming/verify.py tests
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python docs/research/full-migration/movement-naming/verify.py install
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python docs/research/full-migration/movement-naming/verify.py notebook --wheel-dir /private/tmp/rk-movement-naming-recheck
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python docs/research/full-migration/movement-naming/audit_rename.py
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python docs/research/full-migration/movement-naming/capture.py --wheel-dir /private/tmp/rk-movement-naming-recheck
```

Use a fresh wheel directory for each notebook run. The original run used
`/private/tmp/rk-movement-naming-wheel`. Jupyter requires permission to bind local
kernel sockets. The capture script copies the verified executed notebook back to
the walkthrough after confirming that its source cells match. Verification logs
from earlier attempts are retained.

The schema environment uses LinkML 1.11.1, linkml-runtime 1.11.1 and jsonschema
4.26.0. Both interpreters use Python 3.10.19. The audit additionally requires the
previous installed source at `/private/tmp/rk-flow-semantics-wheel/site`, or an
equivalent copy selected with `--previous-site`; its bytes are verified against
`before.json`. Temporary environments and wheels are not repository artifacts.

The capture checks that `.gitignore`, `src/uv.lock` and the pre-existing
`src/uv.sync-conflict-20261005-170953-H3RQGJU.lock` are unchanged from this turn's
starting state. It checks that all runtime Python files match the installed wheel
and that the Git index is empty. No commit or push is included.
