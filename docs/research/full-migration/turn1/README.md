# Full migration Turn 1: baseline and verification

This report retains the original Turn 1 verification. Its TimePoint/57-class
contract is superseded by the [date-only correction](../date-only/README.md).
The original logs and counts below are preserved as historical evidence.

Date: 2026-10-04. Branch: `acausal-modelling`. Starting and final HEAD:
`90c2e00ba7b942a8830960e3df3f3ff616f30fa1`. The implementation is uncommitted.
The [contract and ledger](../../../history/FULL_MIGRATION_TURN1.md) describes delivered
scope and remaining work. The [upgrade guide](../../../guides/upgrading.md)
contains runnable examples and intentional changes.

## Observed results

| Check | Result | Retained evidence |
|---|---|---|
| Original local suite, live API module excluded | **798 passed, 1 failed**, 799 collected | [Baseline log](baseline/pytest-local.log), [collection](baseline/pytest-collection.log), [XML](baseline/pytest-local.xml) |
| Original seven schema suites | All passed in the pinned schema environment | [Baseline commands](baseline/commands.jsonl), `baseline/schema-*.log` |
| Full local regression after implementation | **883 passed**, 7 existing pandas frequency warnings | [Regression log](verification/pytest-local-attempt2.log), [XML](verification/pytest-local.xml) |
| Final focused content/conversion/equivalence checks | **84 passed**, including the added invalid-timezone case after the full run | [Focused log](verification/final-content.log) |
| Final seven schema suites | All passed | [Commands](verification/commands.jsonl), `verification/final-schema-*.log` |
| Reproducible schema generation | Five artifacts / **57 classes** match | [Generation check](verification/generation-check.log) |
| Static API checks | **105 source files** pass; all intended negative cases rejected | [Type checks](verification/typecheck-final2.log) |
| Isolated installed wheel | Lightweight imports, records, optional dependencies, codecs/stores, workflows, actual forward/inverse execution pass | [Installed log](verification/installed.log) |
| Final built-wheel DCF notebook | Fresh kernel; **23 code cells**, no errors; independent PV **1000** | [Notebook](verification/basic_dcf_final.ipynb), [HTML](verification/basic_dcf_final.html), [inspection](verification/notebook-inspection.json), [execution](verification/notebook-release-check.log) |
| Upgrade guide examples | Pass from the built wheel outside the checkout | [Guide log](verification/guide-installed.log), [script](guide_example.py) |
| Legacy numerical comparison | All 18 account cases and 3 cycle cases pass | [Equivalence and converter log](verification/equivalence.log); also included in final focused run |
| Discovery coverage | 41 modules, 671 symbols, 95 consumers, 18 parallel-feature files assigned | [Ledger](ledger.json), [builder](build_ledger.py), [API signatures](api.json) |

The full regression and the focused run overlap; do not add their counts.
The final focused run includes one new timezone validation test that was not in
the 883-test full run. Subsequent edits were type annotations, docstrings and
formatting; the final notebook wheel includes those edits. Existing private API
imports appear only in legacy comparison tests, not the new calculation runtime.

The baseline failure was `tests/test_formulas.py::TestSolver::test_residual`.
An independent scalar cash/debt recurrence gives land **239654.64260783806** and
finance **10345.35739216196**. The old expected land value **241049.33** leaves
an equation residual of **1454.1535992423**. The migrated test checks the independent
root and that rejected expectation. This is a documented test correction, not a
suppressed failure. The migrated linear test helper also corrects terminal
proceeds discounting to use the whole holding period. The original basic DCF
notebook was independently executed first and already returned **1000**:
[original notebook](baseline/basic_dcf.ipynb), [original HTML](baseline/basic_dcf.html).

## Environment and inputs

Runtime: Python **3.10.19**, Polars **1.44.2**, pandas **2.3.2**, NumPy **2.2.6**,
SciPy **1.15.3**, Pint **0.24.4**, Pyomo **6.10.1**, HiGHS **1.15.1**,
jsonschema **4.26.0**. Schema tools: LinkML **1.11.1**, linkml-runtime **1.11.1**,
jsonschema **4.26.0**. Type checks: mypy **1.18.2**. Fresh notebook tooling:
nbformat **5.11.1**, nbclient **0.11.0**, ipykernel **7.3.0**.

- [Initial state](baseline/initial-state.json) retains original branch, HEAD,
  dirty files and hashes of tracked inputs. The pre-existing documentation and
  unrelated `.gitignore` were preserved.
- [Baseline runtime environment](baseline/runtime-environment.log) and
  [schema environment](baseline/schema-environment.log) retain interpreter and
  dependency records.
- [Final state](verification/final-state.json) records selected dependency versions,
  actual import path, `sys.path`, and hashes for 314 code/schema/test/tool inputs.
  It verifies an empty Git index and the unchanged `.gitignore` hash.
- [Runtime package snapshot](verification/runtime-requirements.txt) records the
  inherited verification environment, including legacy test dependencies. It is
  evidence, not a new set of base package requirements.
- [Wheel build](verification/notebook-wheel-release-check.log) retains the actual
  wheel path and SHA256. The wheel was unpacked into an isolated directory;
  notebook/guide imports resolve there. The separate installed-artifact check
  performs installation into a fresh venv with copied declared dependencies.

The runtime interpreter `/private/tmp/rk-full-runtime/bin/python` is an isolated
venv with read-only `.pth` entries to existing runtime caches plus the cached Polars
wheel. The complete paths are in `final-state.json`. Notebook packages were
installed into this temporary environment. No repository lockfile was changed.
The original Python environments remain intact. A copied venv launcher initially
failed on macOS `dyld`; its interpreter was linked to the existing uv Python binary.

No repository AGENTS file was discovered. The supplied AGENTS instruction was
ASD-STE100 writing principles. Python tooling ran from `src`; Git ran from the
repository root. Generated build products, caches and input workbooks used temporary
directories. The full test baseline excludes `tests/test_api.py` (three live-service
tests); these are **unverified**, not skipped successes.

## Reproduction

Use the recorded versions in separate runtime and schema environments. The active
paths below are exact session paths; recreate equivalent environments when those
temporary directories no longer exist. The baseline reproduction must use the
starting source fingerprints, not the changed working tree.

From the repository root:

```sh
/private/tmp/rk-probe-audit-venv/bin/python tools/schema/generate.py --check
/private/tmp/rk-full-runtime/bin/python docs/research/full-migration/turn1/verify_final.py
/private/tmp/rk-probe-audit-venv/bin/python tools/schema/verify_install.py \
  --runtime-python /private/tmp/rk-full-runtime/bin/python \
  --execution-python /private/tmp/rk-full-runtime/bin/python \
  --workflow-python /private/tmp/rk-full-runtime/bin/python
```

From `src`, full local tests and static checks:

```sh
MPLCONFIGDIR=/private/tmp/rk-mpl-cache PYTHONDONTWRITEBYTECODE=1 \
  /private/tmp/rk-full-runtime/bin/python \
  ../docs/research/domain-migration/evidence/run_baseline.py tests \
  --runtime-python /private/tmp/rk-full-runtime/bin/python \
  --output-dir ../docs/research/full-migration/turn1/verification
PYTHONPATH=/private/tmp/rk-record-typecheck PYTHONDONTWRITEBYTECODE=1 \
  /private/tmp/rk-full-runtime/bin/python ../tools/schema/typecheck.py
```

For notebook/guide acceptance, first build a wheel into a **new** directory:

```sh
/private/tmp/rk-probe-audit-venv/bin/python \
  docs/research/full-migration/turn1/build_notebook_environment.py \
  --output /private/tmp/rk-foundations-release-check
```

Then, from `/private/tmp`, use that wheel first on the import path:

```sh
PYTHONPATH=/private/tmp/rk-foundations-release-check/site \
  PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/private/tmp/rk-mpl-cache MPLBACKEND=Agg \
  /private/tmp/rk-full-runtime/bin/python \
  /Volumes/Data/Projects/Rangekeeper/docs/research/full-migration/turn1/run_notebook.py \
  /Volumes/Data/Projects/Rangekeeper/walkthrough/basic_dcf.ipynb \
  /Volumes/Data/Projects/Rangekeeper/docs/research/full-migration/turn1/verification/basic_dcf_final.ipynb \
  --cwd /private/tmp/rk-foundations-release-check
PYTHONPATH=/private/tmp/rk-foundations-release-check/site \
  /private/tmp/rk-full-runtime/bin/python \
  /Volumes/Data/Projects/Rangekeeper/docs/research/full-migration/turn1/guide_example.py
```

`run_notebook.py` writes an explicit kernel specification using its own interpreter.
The original attempt was blocked by the sandbox's local socket restriction;
the approved local-kernel retry completed. The commands logs retain failures and
later passes. The guide's first run correctly rejected a no-op revision; the guide
now makes a real descriptive change and passes. Earlier type-check failures were
fixed; their logs remain evidence rather than current failures.

## Limits and remaining acceptance

The browser URL policy blocked `file:` HTML preview. Execution counts, errors,
import locations, table markup and final values were inspected programmatically;
**visual browser review was not completed**. No alternate browser route was used.
MyST citations/directives remain for the walkthrough build. Old tracked book build
outputs were not silently replaced; rebuilding the complete walkthrough is Turn 4.

This turn did not execute external Projects, Speckle, Rhino/Grasshopper, Hypar,
parallel workbench/layout features, or the remaining six source notebooks.
Scenario/policy consumers, temporal solve roles and indexed formulations remain
Turn 2. Segmentation domain/presentation and other consumers remain Turn 3.
Final export/dependency cleanup and legacy removal remain Turn 4. The converter
is a bounded v1 reader and rejects unsupported content with a report; it does not
establish universal downstream compatibility.

No commit, push or release occurred. The working tree intentionally contains the
new implementation and retained evidence for review.
