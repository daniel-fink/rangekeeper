# Step 6C/6D verification

Observed 2026-10-03 on `acausal-modelling`, starting at
`53f5d3e72f97b7099bcc7973386ba47ccb4b7784`. This slice implements
[Model tables, adapters, and source workflows](../../CONSUMER_MIGRATION.md).
No commit, push, release, or external project migration was performed.

## Results

| Check | Observed result |
| --- | --- |
| Complete available Python suite | **798 passed, 1 known failure**, 799 executed; no collection errors or skipped cases |
| Live API tests | 3 excluded, unverified |
| Seven existing schema suites | All pass in LinkML 1.11.1 / linkml-runtime 1.11.1 / jsonschema 4.26.0 |
| Generated artifacts and native round trips | Pass; authoritative schema and fixtures unchanged |
| Python type checks | 80 source files pass; all intended invalid-call checks pass, including 3 new consumer API rejections |
| Installed wheel outside the checkout | Core, Model graph, table projection, offline viewer assets, workflow, codecs/stores, and real execution pass |
| New Model consumer tests | 14 pass, including actual XLSX-to-Model-to-solver execution |
| Viewer bundle tests | 27 pass; shared memberships, collapse summaries, original IDs, and routing remain intact |
| Real workflow execution example | XLSX net 10 m² → gross 20 m²; reuse that output and assign gross 50 m² → net 25 m² |
| Preservation | 57 existing core/execution files and 56 schema/generated/fixture inputs retain their prior fingerprints |

The remaining failure is `tests.test_formulas.TestSolver::test_residual`, already
recorded before this migration. The old adapter export-list failure no longer
applies: its test now checks the deliberately migrated `rangekeeper.adapters`
contract. The numerical implementation and its expectations were not repaired.
Seven existing pandas duration warnings remain.

Tests retain old Graph characterizations where the old implementation remains.
Six table projection tests moved to `test_legacy_table.py`; their assertions still
exercise the old Graph contract. Source-workflow tests now assert the Model
contract: separate Assemblies, explicit Value keys, unresolved quantities, UUID
references, canonical codecs, source traceability, and no implicit execution.

## Reproduction and evidence

Run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-scalar-runtime/bin/python \
  docs/research/consumer-migration/verify.py
/private/tmp/rk-scalar-runtime/bin/python \
  docs/research/consumer-migration/capture.py
```

`verify.py` accepts `--schema-python`, `--runtime-python`, and `--typecheck-path`.
Use equivalent environments when the temporary paths no longer exist. The schema
interpreter needs the pinned schema tools and setuptools; the runtime needs the
library's local numerical/test dependencies, workflow extra, and Pyomo 6.10.1 /
highspy 1.15.1. The static environment uses mypy 1.18.2. Node/npm run the existing
committed viewer bundles and tests without a dependency install. The installed
check builds a fresh wheel and copies only the dependencies required by each
isolated acceptance stage.

Python tests run from `src`; schema/build commands run from the repository root.
The standalone source example sets `PYTHONPATH` explicitly. Each run creates a
fresh `scalar-<timestamp>` evidence directory. `--only` permits selected checks
after an earlier recorded pass; final acceptance still requires the full pytest
XML to contain exactly the known numerical failure.

- [Initial working state and Python input hashes](initial.json).
- [Final summary and latest command results](summary.json).
- [Exact commands, working directories, environment overrides, exits, and times](commands.jsonl).
- [Verified source and artifact fingerprints](verified-sources.json).
- [Retained raw logs, XML, source workbook, actual Models/Runs, and revision store](evidence.tar.gz).

The archive retains ignored logs without changing `.gitignore`. It also retains
intermediate failed checks: moved-import and changed-contract test expectations
were corrected before the final pass. An initial standalone-example invocation
needed an explicit source path; the reproduction runner now supplies it. See the
latest entries in `summary.json` for acceptance, not an earlier failed log.

## Limits

Mandarin, East Whisman, notebooks, Speckle/Grasshopper, Hypar, and live services
were not executed. They remain Step 6E. Workflow version 1, old import paths,
Feature declarations, and Graph JSON need explicit consumer migration.

Browser interaction was not exercised. Python export, installed assets, and 27
existing viewer bundle tests passed. TypeScript rebuilding remains unverified:
`tsc` was absent, and offline npm installation could not retrieve the uncached
Prettier/type dependencies. The TypeScript and bundled viewer code were moved
without changes; this slice did not add browser behaviour.

The real scalar example is a bounded affine feasibility check. It does not prove
support for rich Features, temporal values, nonlinear equations, optimization,
or external project data.
