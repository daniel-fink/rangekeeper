# Step 6A/6B: graph migration evidence

Implementation date: 2026-10-03 Australia/Sydney. This slice introduces canonical
Model-backed View, explicit relationship/membership Hierarchy, owner-local Value
selection, pure quantity reducers and immutable Aggregation/Coverage. See the
[API guide and remaining Step 6 slices](../../GRAPH_MODEL.md).

It began on `acausal-modelling` at `53f5d3e72f97b7099bcc7973386ba47ccb4b7784`, with
the completed Step 5 implementation already present as uncommitted work. Before
editing, all source hashes from the scalar checkpoint matched its retained
verification manifest. [Initial files/status](initial.json) include staged and
unstaged work; no Git index, commit or push commands were issued in this slice.
The unrelated `.gitignore` edit remains unchanged.

## Results

**783 passed, two known baseline failures, 785 executed.** This includes **37 new
Model-backed graph cases** and one new legacy/new-domain boundary case. No skips
or collection/runtime errors occurred in the executed suite.

The final [summary](summary.json) records counts, precise log paths and preservation
checks. The full suite is expected to retain only the two named baseline failures;
verification asserts their exact identities and rejects errors/skips.

- New graph coverage includes every selection mode, strict UUID errors, canonical
  separate Assembly storage, filtering, deterministic order, membership overlap,
  nested trees, all invalid hierarchy forms, explicit Value selection, unit conversion,
  revision isolation, missing/zero/subtotal behavior, raw-population means, callback
  errors, overflow and lightweight imports. Existing legacy tests also prove that
  new and old View constructors reject the other domain.
- Static checking passes **74 source files**, plus intended rejection checks for
  invalid record, domain, IO, execution and five new graph API calls.
- All **seven existing schema suites** pass. Generated artifacts are fresh and the
  native-record equivalence check passes; schemas and conformance expectations are
  unchanged.
- The installed wheel works outside the checkout: graph imports and singleton
  selection/hierarchy need no Pint/NetworkX/pandas/solver or old Graph imports.
  With Pint available, canonical Assembly membership, explicit Value reduction,
  units and coverage pass. Existing installed-core and actual forward/inverse
  Pyomo/HiGHS checks also pass.
- Full local tests include existing workflow, ingestion, table, viewer, persistence,
  numerical and **43 scalar execution cases**. The known adapter export mismatch
  and legacy formula residual mismatch remain the only allowed failures.

The failures are `tests.test_adapters::test_supported_adapter_and_table_surfaces_are_explicit`
and `tests.test_formulas.TestSolver::test_residual`. The latter still obtains
`239654.64258295443` against expected `241049.33`. Three live-service tests in
`tests/test_api.py` remain excluded. Remote CI and external projects/services/hosts
were not executed.

## Scope and preservation

The old View and reduction files moved to `graph/legacy` with **only relative import
adjustments**, checked against the starting HEAD. `Graph.view()`, old Table and
visualization consumers now import that View explicitly. Legacy tests were rebound
to those namespaces; namespace expectations were deliberately updated, while old
behavior assertions were retained. No permissive Graph/Model dispatch was added.

The Model-backed graph root exposes the new View, Hierarchy, Reduction, Aggregation
and Coverage. Existing old domain exports load lazily only for their remaining
consumers. The guide documents the breaking direct View/reduction imports and
retirement conditions for this temporary legacy package.

The previous execution, Model, Specification, Run, IO and generated-record sources,
authoritative LinkML YAML, fixtures/checks and scalar research evidence retain
their initial hashes. Tooling/CI were extended for graph typing, tests and installed
verification. All current tested sources are hashed in [verified-sources.json](verified-sources.json).
[summary.json](summary.json) lists changed pre-existing paths and preservation counts.

## Reproduction

Use the same retained environments as the [scalar checkpoint](../scalar-execution/README.md#environment-and-reproduction):
Python 3.10.19; LinkML/linkml-runtime 1.11.1; jsonschema 4.26.0; mypy 1.18.2;
Pint 0.24.4; Pyomo 6.10.1 and Highspy 1.15.1 for execution regressions.
The runner captures actual package versions and import paths. No new dependency
installation or lock-file changes were required for this graph slice.

From the repository root:

```sh
python3 docs/research/graph-migration/verify.py \
  --schema-python /private/tmp/rk-probe-audit-venv/bin/python \
  --runtime-python /private/tmp/rk-scalar-runtime/bin/python \
  --typecheck-path /private/tmp/rk-record-typecheck
python3 docs/research/graph-migration/capture.py
```

The runner executes Python tests from `src`, redirects caches to temporary directories,
and builds/installs the wheel in isolated temporary directories. It records exact
argv/cwd/environment, elapsed time and exit status in [commands.jsonl](commands.jsonl).
Repeat runs preserve previous logs with timestamp suffixes. `capture.py` verifies
preservation against this slice's captured starting state and creates the final
summary/archive; its baseline assertions intentionally describe this checkpoint.

[evidence.tar.gz](evidence.tar.gz) retains all logs, JUnit data, manifests and reproduction
scripts because loose `.log` files are ignored by the repository. Extract it into a
temporary directory when inspecting a checkout without those loose logs. The final
JUnit result remains available as [pytest.xml](pytest.xml).

## Development observations and remaining work

Retained development logs include a mistyped test filename, a working-directory
mistake before fixture editing, and invalid new fixtures missing required
Relationship classification / a single-root Taxonomy. Those fixture definitions
were corrected; no schema or existing semantic expectation was relaxed. The first
complete run passed with only known failures. Final review tightened empty
wrong-type selector handling and added six cases before the final verification.

This is **6A/6B only**. Table projection, adapter namespace migration, WorkflowResult.model,
source-to-Model composition, project data conversion and final old-domain retirement
remain 6C–F. Rich Feature content requires an explicit schema decision; unsupported
content is not silently converted. Tree-only operations intentionally reject
multi-parent graphs. Reduction retains raw subtree populations to preserve arbitrary
reducer semantics and means; large-tree scalability has not been benchmarked.
