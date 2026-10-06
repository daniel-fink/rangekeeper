# Turn 2 verification

Verification date: 2026-10-06. Start: `acausal-modelling` at
`7b8dcd46fe56a0ee0e599323020b85df1818b9eb`. No commit, push or release was performed.
[Closing state](final-state.json) records 368 verification-input hashes, confirms
230 installed code/artifact files match the working tree, and verifies both
protected files are unchanged and the Git index is empty.
[Complete environment inventories](environments.json) retain installed versions.
The contract and implementation map are in [FULL_MIGRATION_TURN2.md](../../../FULL_MIGRATION_TURN2.md).

## Baseline and environment

The fresh baseline was **946 passed**. [Starting state](baseline/state.json)
retains 1,125 input hashes, runtime versions and the original dirty-file list.
[Baseline commands](baseline/commands.jsonl) record exact invocations and logs.
The unrelated `.gitignore` edit and `src/uv.sync-conflict-20261005-170953-H3RQGJU.lock`
are protected inputs; the closing fingerprint check compares their original hashes.
No repository `AGENTS.md` file was found. The supplied instruction is to use
ASD-STE100 principles in replies; implementation follows the approved Turn 2 plan.

| Environment | Interpreter and relevant versions |
|---|---|
| Runtime | `/private/tmp/rk-full-runtime/bin/python`, Python 3.10.19; NumPy 2.2.6, SciPy 1.15.3, Polars 1.44.2, pandas 2.3.2, PyXIRR 0.10.7, Pint 0.24.4, Pyomo 6.10.1, HiGHS 1.15.1 |
| Schema generation | `/private/tmp/rk-probe-audit-venv/bin/python`; LinkML 1.11.1, linkml-runtime 1.11.1, jsonschema 4.26.0 |
| Typing | Runtime interpreter with `PYTHONPATH=/private/tmp/rk-record-typecheck`; mypy 1.18.2 |
| Notebook package | Fresh wheel unpacked at `/private/tmp/rk-turn2-final-wheel/site`; source imports asserted/printed in notebook outputs; wheel SHA256 in [build log](final-notebooks/wheel.log) |

Python test commands run from `src`; Git and schema commands run from repository
root. Notebook kernels run outside the checkout. Tests use `MPLBACKEND=Agg`,
`MPLCONFIGDIR=/private/tmp/rk-mpl-cache`, `PYTHONDONTWRITEBYTECODE=1`, and isolated
cache/output paths. Schema tools use `PYSTOW_HOME=/private/tmp/rk-domain-migration-pystow`.
The notebook explicitly selects inline plotting so exported plots are inspectable.
Only local Jupyter kernel socket access needed a sandbox escalation; no remote
service was invoked by notebook acceptance.

## Results

Final local-suite result: **967 passed, 7 warnings**, with the three live-service tests excluded.
The final run used the new fixture revision identities and all added tests.

| Check | Evidence |
|---|---|
| Seven schema suites | [acceptance commands](acceptance/commands.jsonl), `schema-*.log`: all pass |
| Generation freshness | [generation.log](acceptance/generation.log): pass, 73 generated classes |
| Static typing | [typecheck.log](acceptance/typecheck.log): 139 source files pass plus intended negative-call rejections |
| Fresh installed package | [installed.log](acceptance/installed.log): pass; records, codecs, stores, lightweight imports, scalar forward/inverse reuse, PyXIRR, source workflow |
| New temporal/scenario/policy behavior | [local suite](acceptance/pytest-local.log) and [JUnit](acceptance/pytest-local.xml) |
| Temporal forward/inverse and policy publication | [authentic documents](final-notebooks/temporal-proof/summary.json), including retained input Models, Specifications, Runs and accepted outputs |
| Upgrade guide examples | [guide.log](final-notebooks/guide.log), executed outside checkout against the wheel |
| Legacy source inventory | [legacy-dependencies.json](legacy-dependencies.json): no runtime dependencies in the five numerical walkthroughs or three migrated test-model modules; every retained hit has a retirement gate |

The local suite excludes `tests/test_api.py`: `TestApi.test_connection`,
`test_model`, and `test_conversion` depend on the live Speckle connection/model.
They remain unverified. The seven retained warnings are pandas frequency aliases
in `_legacy_duration.py`; their removal belongs to the remaining legacy gates.
No unresolved production test failure is accepted as passing evidence. The additional
stock LinkML loader probe has the tooling limitation recorded below.

### Executed notebooks

All five run from the installed wheel. The executed notebook, HTML and extracted
PNG plots are retained together. Source notebooks remain in `walkthrough/`.

| Notebook | Executed artifact | HTML |
|---|---|---|
| Basic DCF | [notebook](final-notebooks/basic_dcf.ipynb) | [HTML](final-notebooks/basic_dcf.html) |
| Deterministic scenarios | [notebook](final-notebooks/deterministic_scenarios.ipynb) | [HTML](final-notebooks/deterministic_scenarios.html) |
| Market dynamics | [notebook](final-notebooks/market_dynamics.ipynb) | [HTML](final-notebooks/market_dynamics.html) |
| Flexibility introduction | [notebook](final-notebooks/flexibility_intro.ipynb) | [HTML](final-notebooks/flexibility_intro.html) |
| Flexibility under uncertainty | [notebook](final-notebooks/flexibility_under_uncertainty.ipynb) | [HTML](final-notebooks/flexibility_under_uncertainty.html) |

Routine uncertainty acceptance uses **4 paired scenarios**, `workers=1`, shown in
its output. The original 2,000-scenario setting remains available but was not run.
Parallel/reordered generation is tested separately with identical captured content.
The small sample verifies mechanics; it is not a convergence study or performance
claim for the full study size. First-run basic DCF failure was a stale `0.4.0`
string. Its corrected `0.5.0` run passes in [basic-dcf-recheck.log](final-notebooks/basic-dcf-recheck.log).

### Additional native-loader probe

The [native boundary probe](final-notebooks/native-boundary.json) checks ten actual
published/input documents. The generated **immutable records round-trip 10/10**
with exact detached data. Stock LinkML classes round-trip **9/10**. The stock
LinkML 1.11.1 loader fails on the policy Specification's single-field terminal
Action with `Slot: actions - attribute kind value (terminate) does not match key
(terminate)`. The probe deliberately exits nonzero; its
[log](acceptance/native-boundary-probe.log) is not a pass.

This is an additional private tooling limit, not a public-codec failure. Production
Model/Specification/Run loading and execution use the generated immutable boundary
and JSON Schema, without importing the stock LinkML loader. No schema field or
policy effect was changed to work around that loader. Raw stock-native policy
loading needs a separate upstream/generator fix if a consumer later requires it.
Existing seven-suite acceptance does not certify every stock-native record shape.

### Plot inspection

Inspected the exported deterministic PV curve, true/noisy/historical market path,
fixed-versus-policy investment cashflow and paired empirical IRR CDF. Date axes,
amount units, percent labels, legends and the distinct sale horizons are visible.
Base PV remains 1,000; optimistic/pessimistic curves reach about 1,294/706. The
policy cashflow ends at its sale while the fixed case continues. The four-scenario
CDF is explicitly a small empirical sample, not a smooth fitted distribution.

## Acceptance coverage

- Forward temporal PV `3000/11`, then inverse initial amount `110` using the real
  forward output. Original scalar $11 million/$27,500 results remain accepted.
- Mixed assigned/unknown/unrelated Movements, stable keys after insertion,
  missing/null versus zero, wrong keys, unit conflicts, no recorded-value fallback,
  duplicate contributor roles, detached exports and nested immutability.
- Account balance `[110,90,95]`, interest `[11,9,9.5]`, explicit percentage
  conversion, scaling/sums and lagged reversion mapping against independent values.
- Rejected candidates publish no output. Symbol/constraint limits prevent backend
  invocation; exhausted preparation budgets record `limited/not_assessed`.
- Fixed innovations and independently calculated market paths, shock amplitude
  once, deterministic parallel/reordered streams, replay without random draws,
  finite/complete captured input shapes and delayed forward-derived observations.
- Strict threshold equality, minimum holding, first/final/no-trigger cases, one
  sale, no post-sale investment amounts, immutable full scenario paths, missing
  observations, future-data isolation, role conflicts and endogenous observation
  rejection. Forged decision timing, actions, rule choice and termination fail.
- Explicit draft upgrades create new revisions and require new external pins.
  [Synthetic fixture mapping](fixture-revisions.json) identifies new current
  fixture UUIDs. Historical Runs/research are not relabelled as new executions.

## Intermediate findings and corrections

Earlier directories are retained, not overwritten. They are not current pass counts.

1. The namespace-only gate in [duration](duration/) passed 147 focused tests,
   seven schema suites, generation, typing, installed checks and the basic DCF.
   [duration-transition.json](duration-transition.json) is the caller list at that
   earlier gate; the final inventory supersedes it after consumer migration.
2. Generated recursive JSON Schema contained redundant conjunction/disjunction
   branches. They caused repeated validation of the same expression tree. The
   generator now removes only `A AND (A OR B)` redundancy. The differential probe
   recorded **765 matching outcomes, zero differences** in
   [schema-simplification.json](integration-fifth/schema-simplification.json).
   A nine-level unary tree fell from about 0.187 s to 0.00159 s in that probe.
3. Initial schema/static checks exposed old scalar reference assumptions, missing
   UUID patterns and nullable expression targets. Current shared-reference rules
   and active checks were corrected together.
4. The first complete integration run had **958 passes and three failures**:
   one direct candidate test used old UUID keys; the source-workflow example used
   old assignment/reference shapes; a parallel check ran while its parent/worker
   implementations differed due to in-progress source edits. Fresh-process checks
   passed after the callers were corrected and source was held stable.
5. Explicit scenario input/output access resolves overlapping names such as
   `volatility`. Captured input validation now checks complete inventories and
   coordinates. A new Run status case records deadline expiry before assessment.
6. A later run had **965 passes and one obsolete deadline expectation**. It expected
   `unknown` before any numerical assessment; the revised contract correctly uses
   `not_assessed`. The next complete run passed **966**. A final independent builder
   check and new fixture revision IDs were then included in the final suite.

## Reproduce

Use the recorded interpreter environments, or recreate their listed package
versions. These commands retain separate logs and never overwrite earlier stages:

```sh
/private/tmp/rk-full-runtime/bin/python docs/research/full-migration/turn2/verify.py checks --stage rerun
/private/tmp/rk-full-runtime/bin/python docs/research/full-migration/turn2/verify.py tests --stage rerun
/private/tmp/rk-full-runtime/bin/python docs/research/full-migration/turn2/verify.py install --stage rerun
/private/tmp/rk-full-runtime/bin/python docs/research/full-migration/turn2/verify.py notebook --stage rerun-notebooks --wheel-dir /private/tmp/rk-turn2-new-wheel
```

Choose a new wheel directory. `check.py` records targeted follow-up checks.
`scan_legacy.py` refreshes the lexical inventory. `verify_simplification.py` under
`tools/schema/` compares raw and simplified generated schemas. The broad dependency
cleanup, remaining service/design consumers, full 2,000-scenario execution and
old-module removal are not certified by this turn.
