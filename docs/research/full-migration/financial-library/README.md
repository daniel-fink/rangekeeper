# Financial-library integration

Implemented 2026-10-04 on `acausal-modelling`, HEAD `90c2e00`. The correction is
uncommitted and preserves the existing Turn 1 work and unrelated `.gitignore`.
It follows the user's instruction to reuse dedicated financial libraries.

The subsequent [Flow semantics correction](../flow-semantics/README.md) removes
Flow basis and its operation gates. The library backend and day-count conventions
remain. This report preserves the inputs and results of the earlier checkpoint.

## Ownership and behavior

`calculations.financial` remains the public RK interface. PyXIRR now performs
PV, XNPV and XIRR. `temporal.calendar.year_fraction` also delegates day-count
arithmetic to PyXIRR. RK checks dates, basis, missingness and results, preserves
units/Claims, and constructs immutable outputs. The handwritten discount formula,
day-count formulas and SciPy IRR objective/root wrapper are removed.

The earlier draft's required `bracket=` and solver `tolerance=` are removed.
`calculate_irr(flow, guess=None, ...)` uses the library's initial-guess/root
selection behavior. No observed consumer needed an interval-constrained solve.
`IrrResult` contains `rate`, `residual`, `guess` and `method="pyxirr.xirr"`.
Multiple roots remain possible; the result does not prove uniqueness or promise
the root nearest the guess. A missing/nonfinite result raises `ValueError`.
Residuals greater than 1e-8 of gross movements, with a one-unit scale floor, fail.

XNPV uses the earliest actual payment as the library's origin, then PyXIRR PV
transfers the result to RK's explicit valuation date. The same additive day-count
convention is used for both operations. Supported mappings are:

| RK name | PyXIRR convention |
|---|---|
| `actual/365` | `ACT_365F` |
| `actual/360` | `ACT_360` |
| `actual/actual` | `ACT_ACT_ISDA` |
| `30/360` | `THIRTY_E_360` (European) |

Flow timing remains explicit. Recorded dates take precedence over period-boundary
conventions. XNPV accepts single payments and all-positive/all-negative amounts;
IRR requires both signs and distinct dates. Empty movement Flows return zero
XNPV before the library call: PyXIRR 0.10.7's empty-date path panics. Empty Flows
and same-date payments do not determine an IRR.

The [upstream function documentation](https://anexen.github.io/pyxirr/functions.html)
describes the library API. Its older XNPV sign restriction differs from the tested
0.10.7 behavior. The upstream [scheduled calculation source](https://github.com/Anexen/pyxirr/blob/master/src/core/scheduled/xirr.rs)
explains its earliest-date origin. Tests against the installed **0.10.7** are the
evidence for this integration; a moving source branch does not pin the dependency.

`pyxirr>=0.10.7,<0.11` is declared in base dependencies while legacy consumers
remain, and in the `calculations` extra for the intended optional package boundary.
The refreshed lock retains PyXIRR 0.10.7 and existing package versions, and adds
Polars/runtime 1.44.2 for the already-declared calculations extra. Broad base
dependency retirement remains Turn 4. Importing core/date construction does not
import PyXIRR; financial/day-count calls load it when needed.

## Observed verification

| Check | Result | Evidence |
|---|---|---|
| Focused finance, date, calculation and model checks | 103 passed | [Log](focused.log) |
| Full local regression | **930 passed**, seven existing legacy pandas frequency warnings | [Log](pytest-local.log), [XML](pytest-local.xml), [commands](commands.jsonl) |
| Static checks | 105 source files pass; intended negative cases rejected | [Log](typecheck.log) |
| Isolated installed wheel | PV/XNPV/IRR work with PyXIRR and without SciPy, NumPy, pandas, Polars or legacy imports | [Log](installed.log) |
| Installed core/execution/workflow regression | Lightweight imports, stores, genuine forward/inverse solves and workflow acceptance pass | [Same installed log](installed.log) |
| DCF notebook from built wheel | 23 code cells, no errors, independent PV oracle remains **1000** | [Notebook](basic_dcf.ipynb), [HTML](basic_dcf.html), [inspection](notebook-inspection.json) |
| Upgrade guide from built wheel | Passed | [Executable blocks](guide_example.py), [log](guide-installed.log) |
| Dependency lock check | Passed | [Log](lock-check.log) |

The focused and full counts overlap. New tests use independent discount and
day-count examples, including leap years, valuation before/between/after payments,
negative rates, duplicate payment dates, non-currency units, no-root and multiple-root
IRRs, and failed/nonfinite/inaccurate backend outputs. No tests claim all possible
IRRs are enumerated. Three live-service tests in `tests/test_api.py` remain excluded
and unverified. Schemas and generated artifacts are unchanged, as checked by
[fingerprints](final-state.json); the seven schema suites were not rerun for this
library-only correction. Their preceding results remain in the
[date-only report](../date-only/README.md).

## Reproduction and limits

Runtime is Python 3.10.19 with PyXIRR 0.10.7. Complete selected versions and input
hashes are in [final-state.json](final-state.json), with the [starting state](before.json).
The [wheel build](wheel.log) records the artifact hash. Python files in the built
wheel match the final source. [API signatures](api.json) reflect the corrected API.

From repository root:

```sh
PYTHONPATH=/private/tmp/rk-record-typecheck PYTHONDONTWRITEBYTECODE=1 \
  /private/tmp/rk-full-runtime/bin/python tools/schema/typecheck.py
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/private/tmp/rk-mpl-cache \
  /private/tmp/rk-full-runtime/bin/python \
  docs/research/domain-migration/evidence/run_baseline.py tests \
  --runtime-python /private/tmp/rk-full-runtime/bin/python \
  --output-dir docs/research/full-migration/financial-library
PYTHONDONTWRITEBYTECODE=1 PYSTOW_HOME=/private/tmp/rk-domain-migration-pystow \
  /private/tmp/rk-probe-audit-venv/bin/python tools/schema/verify_install.py \
  --runtime-python /private/tmp/rk-full-runtime/bin/python \
  --financial-python /private/tmp/rk-full-runtime/bin/python \
  --execution-python /private/tmp/rk-full-runtime/bin/python \
  --workflow-python /private/tmp/rk-full-runtime/bin/python
```

For notebook acceptance, build with
`docs/research/full-migration/turn1/build_notebook_environment.py --output /private/tmp/rk-financial-library-wheel`
using the schema interpreter. Choose a fresh directory when repeating. Then use
the existing `turn1/run_notebook.py` with runtime Python, source
`walkthrough/basic_dcf.ipynb`, output `financial-library/basic_dcf.ipynb`, and
`--cwd /private/tmp/rk-financial-library-wheel`. Set
`PYTHONPATH=/private/tmp/rk-financial-library-wheel/site`, `MPLBACKEND=Agg`,
`MPLCONFIGDIR=/private/tmp/rk-mpl-cache`, and `PYTHONDONTWRITEBYTECODE=1`.
Run `guide_example.py` under the same environment from `/private/tmp`.
Run [capture.py](capture.py) from the repository root to inspect outputs and copy
the executed notebook back to the walkthrough; update its `SITE` if using a new path.

The offline lock attempt lacked cached HiGHS metadata for other supported Python
versions. The subsequent metadata-only online resolution and offline lock check
passed. No existing environment was synchronized or replaced.

Notebook execution used an approved local kernel. Values, output counts, table
markup and import path were inspected programmatically. Visual browser inspection
remains unverified after the earlier file-URL policy block. No alternate browser
route was used. No commit, push or release occurred.
