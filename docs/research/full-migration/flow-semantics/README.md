# Flows without semantic kinds

Implemented 2026-10-06 on `acausal-modelling`, HEAD `90c2e00`. The user's decision
is to preserve RK's original division of responsibility: Flows carry quantities;
the overall model logic determines their meaning and selects calculations.
This correction is uncommitted and does not advance the planned duration namespace
move or Turns 2–4. Model schema version remains the unreleased **0.4.0**.

The subsequent [Movement naming change](../movement-naming/README.md) replaces
`FlowSample`/`samples` with `Movement`/`movements`, including the wire field.
This report and its evidence preserve the earlier checkpoint's names and inputs.

## Contract and changes

- Removed `Flow.basis`, `FlowBasis`, constructor/adapter/projection `basis=`
  arguments and multiplication's `result_basis=` argument. There is no replacement
  Flow kind. `Value.kind="flow"` remains the content-shape discriminator.
- Regenerated all five shared artifacts from LinkML. A Flow has units and ordered
  samples. Closed-schema validation rejects the removed field and a proposed
  `kind` field. Prior draft documents need an explicit revision; no automatic
  field removal is hidden in loading.
- Removed semantic gates from sums, products, totals, extrema, differences,
  resampling, integration and financial/account preconditions. Same-day entries
  require unique keys; period overlap and ordering checks remain.
- Multiplication uses dimensional algebra and normalizes scaled dimensionless
  units such as percent. It retains time dimensions. Integration uses explicit
  exposure Quantities or period day-count fractions.
- Resampling accepts the caller's sum/first/last/min/max/mean selection. Every mean
  requires a weighting choice. Explicit zero filling applies to empty groups;
  an unresolved entry in a populated group remains unresolved.
- Financial calls interpret their inputs as amounts. Accounts interpret the named
  arguments as transactions, starting balance and per-period interest rates.
  Interest-rate Flows must convert to dimensionless ratios. Finite-value, date,
  alignment, unit, IRR-domain and residual checks remain.
- Updated public docstrings, dataframe adapters, tests, the DCF source notebook,
  upgrade examples, architecture/contract documents and handoff. `FlowSample`
  remains the current entry name; renaming it was not part of this instruction.

The [current contract](../../../FULL_MIGRATION_TURN1.md#flow-semantics-and-explicit-operations)
and [API catalog](api.json) define the resulting interfaces. Historical evidence
retains the inputs and results of each prior checkpoint.

## Observed verification

| Check | Result | Evidence |
|---|---|---|
| Focused Flow/date/calculation/financial/model checks, including legacy account comparisons | **145 passed** | [Log](focused-attempt2.log) |
| Full local regression | **944 passed**, seven existing legacy pandas frequency warnings | [Log](pytest-local.log), [XML](pytest-local.xml) |
| All seven schema suites | Passed | `schema-*.log`, [commands](commands.jsonl) |
| Reproducible generation | Five artifacts, 56 schema classes match | [Log](generation.log) |
| Native/public Flow round trips | Date, period and combined coordinate forms pass; basis/kind rejected | [Probe](native_flow.py), [log](native-flow.log) |
| Static typing | 105 source files pass; intended invalid examples rejected | [Log](typecheck.log) |
| Isolated installed wheel | Records, lightweight imports, units, JSON/YAML stores, finance, workflows and actual forward/inverse scalar solves pass | [Log](installed.log) |
| Built-wheel DCF notebook | 23 code cells pass; independent PV oracle remains **1000** | [Notebook](basic_dcf.ipynb), [HTML](basic_dcf.html), [inspection](notebook-inspection.json) |
| Upgrade-guide examples against the same wheel | Passed outside the checkout | [Script](guide_example.py), [log](guide.log) |
| Source/artifact comparison and preservation | Wheel Python matches source; `.gitignore`, lock and sync-conflict lock untouched; Git index empty | [Final state](final-state.json) |

The focused and full test totals overlap. The new tests show that one Flow can
support different explicitly chosen reductions, dimensionless data still needs
an explicit mean weighting, multiplication retains squared time dimensions,
percent scales are handled correctly, exposure calculations need no classification,
account rates retain unit checks, and zero filling does not resolve unknowns.
Existing tests retain immutable Model/storage, missing/null/zero, date coverage,
unit compatibility, adapter round-trip and financial-library acceptance.

The first focused run had 143 passes and two failures in a new test which called
a nonexistent `Flow.to_json()` convenience method. Correcting the test to serialize
the detached export resolved both failures; no runtime fix was needed.

The first notebook run could not bind local kernel ports under sandbox permissions.
Its stalled child was stopped; [that log](notebook.log) and exit status remain.
The separate run with local-kernel permission passed, as recorded in
[notebook-local-kernel.log](notebook-local-kernel.log). The initial runner therefore
has a failed notebook phase despite its passing guide check. Source code cells,
output counts, import path, table markup and numerical assertions were inspected.
No visual browser review is claimed.

Three live-service tests in `tests/test_api.py` remain excluded and unverified.
External Projects, host integrations, indexed formulations, scenario/policy work
and final legacy retirement retain their existing acceptance gates. No commit,
push, release or dependency update occurred.

## Reproduction

[Environment](environment.json) records Python **3.10.19**, LinkML and
linkml-runtime **1.11.1**, jsonschema **4.26.0**, PyXIRR **0.10.7** and runtime
dependency versions. [Before](before.json) and [final state](final-state.json)
retain input fingerprints. The [wheel log](wheel.log) records the artifact hash.
[Commands](commands.jsonl) records subprocess arguments, working directories,
exit codes and elapsed times. The runner also sets `MPLCONFIGDIR` to
`/private/tmp/rk-mpl-cache`; type checking uses
`PYTHONPATH=/private/tmp/rk-record-typecheck` and notebook/guide execution uses the
selected wheel's `site` directory as `PYTHONPATH`.

From repository root, with those interpreters available:

```sh
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python \
  docs/research/full-migration/flow-semantics/verify.py focused
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python \
  docs/research/full-migration/flow-semantics/verify.py checks
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python \
  docs/research/full-migration/flow-semantics/verify.py tests
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python \
  docs/research/full-migration/flow-semantics/verify.py install
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python \
  docs/research/full-migration/flow-semantics/verify.py notebook \
  --wheel-dir /private/tmp/rk-flow-semantics-repeat
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python \
  docs/research/full-migration/flow-semantics/capture.py \
  --wheel-dir /private/tmp/rk-flow-semantics-repeat
```

Use a fresh wheel directory when repeating the notebook phase and permit local
kernel sockets. The capture command checks the notebook source and outputs,
refreshes the walkthrough's executed copy, verifies the wheel against source,
and refreshes final fingerprints and the API catalog. The runner retains earlier
logs by giving repeated attempts distinct names.
