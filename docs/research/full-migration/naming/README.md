# RK naming verification — 2026-10-06

Starting HEAD: `7b8dcd46fe56a0ee0e599323020b85df1818b9eb` on
`acausal-modelling`, with the existing uncommitted Turn 2 work. This update does
not commit, push, remove old service consumers, or rewrite earlier evidence.
The unrelated `.gitignore` change and Syncthing lock conflict copy are preserved.

See [RK naming](../../../contributing/README.md) for the API and migration contract.

## Inputs and environment

- `baseline.json`: original status and schema/source/notebook fingerprints.
  Local environment, cache and notebook-checkpoint fingerprints were removed
  during checkpoint review; the excluded count is recorded in that file.
- `market-before.json`: pre-change seeded market, also retained as the regression
  fixture `src/tests/fixtures/scenarios/market-v1.json`.
- `environment-runtime.json`, `environment-schema.json`,
  `environment-typecheck.json`: interpreters, import paths and package versions.
- Each verification directory's `commands.jsonl` records exact argument lists,
  working directories, environment overrides, exit codes and timings.

Generation uses LinkML 1.11.1, linkml-runtime 1.11.1, jsonschema 4.26.0 and PyYAML
6.0.3. Runtime Python is 3.10.19, NumPy 2.2.6, SciPy 1.15.3, Pyomo 6.10.1,
HiGHS 1.15.1 and Polars 1.44.2. Static checks use mypy 1.18.2 through the recorded
separate tool path. Distribution records and Market imports load no numerical,
solver, dataframe or legacy numerical modules (`installed-api.log`).

## Completed checks

- **971 local tests passed**, with seven existing warnings. Live Speckle tests in
  `tests/test_api.py` were excluded and remain unverified. See
  `final/pytest-local.log` and its JUnit XML.
- All **seven schema suites** passed; generation freshness passed.
- Static typing passed across 142 source files and the intended rejection probes.
  `typecheck-public.log` also covers the named Market properties, shared
  Distribution type and DecisionHistory API.
- Installed package and optional-dependency checks passed (`installed/`).
- All **five walkthroughs passed** from the fresh installed wheel outside the
  checkout. Executed notebooks, HTML previews and plots are retained under
  `installed-notebooks/`; the verified outputs are also saved in `walkthrough/`.
  Representative market, cashflow, policy and paired-distribution plots were
  inspected for labels, dates, units and clipping.
- The installed temporal proof passed: forward PV `272.72727272727275`, inverse
  initial amount `110.00000000000001`, and an accepted policy-controlled Run.
- Upgrade-guide examples executed successfully outside the checkout.
- Four new regressions cover shared distribution serialization/calculation,
  component composition/conflicts, revision-pinned typed Market access, and
  migration/seeded equivalence (`naming-tests.log`).

The migration regression compares every old output Flow against fresh v2
production with the same seed. Values, dates and units agree exactly. Upgrading
preserves Value/Movement identities, magnitudes, evidence and stream identifiers;
replay checks the stored paths without drawing again. Cycle variation remains
zero-centred and the rental multiplier remains one plus that variation.

## Reproduction

From the repository root, using the recorded environments:

```sh
/private/tmp/rk-full-runtime/bin/python docs/research/full-migration/naming/verify.py checks --stage rerun-checks
/private/tmp/rk-full-runtime/bin/python docs/research/full-migration/naming/verify.py tests --stage rerun-tests
/private/tmp/rk-full-runtime/bin/python docs/research/full-migration/naming/verify.py install --stage rerun-install
/private/tmp/rk-full-runtime/bin/python docs/research/full-migration/naming/verify.py notebook --stage rerun-notebooks --wheel-dir /private/tmp/rk-naming-fresh-wheel
```

Choose a new wheel directory. The runner builds and extracts a wheel, then runs
notebooks outside the checkout with that wheel first on PYTHONPATH. The numerical
extras and notebook dependencies are supplied by the recorded runtime environment.
The routine uncertainty count is four; the original 2,000-scenario setting remains
available and is not part of this verification.

The first notebook attempt under the restricted sandbox could not open local
Jupyter sockets. It was interrupted; its log is under `notebooks/`. Verification
continued under `installed-notebooks/` with local kernel access. PyStow also
requires a writable cache; the runner records its temporary cache override.

A first focused run found one test still selecting `independent.v1`; its source
was updated to v2. A new equivalence test caught integer defaults where the flat
plan used floats; constructor defaults were corrected without changing arithmetic.
Both corrections are covered by the completed full suite.

## Checkpoint review

Before staging, the source and notebook fingerprints still matched the verified
files, and both unrelated files matched their starting hashes. The review removed
a credential literal from a commented test example and the copied dependency
inventory. The test's parsed Python syntax tree was unchanged. The inventory
writer now redacts token literals and excludes local hidden cache/environment
directories; its refreshed result has 856 occurrences across 57 files and no
runtime legacy references in the migrated consumers. The baseline retains 369
project fingerprints after excluding 12,799 local cache/environment entries.
The handoff now points to Turn 3. These review changes do not alter runtime logic.
