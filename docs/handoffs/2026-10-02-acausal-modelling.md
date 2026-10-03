# Rangekeeper acausal modelling handoff

Prepared 2026-10-02 for continuation on Daniel's Mac Studio.

## Resume here

**Continuation update, 2026-10-03:** Daniel decided to retain LinkML after the
independent audit and discussion of native CUE's benefits and costs. The
[schema decision](../research/current-schema-comparison/DECISION.md) closes the
comparison for this stage. Do not resume native CUE implementation. Step 1 has now
mapped replacement of the graph domain core. The minimal schema-backed core is now
implemented directly in its library packages, together with scalar execution.
Step 6A/6B now implements [Model-backed graph operations](../GRAPH_MODEL.md).
[Step 6C/6D](../CONSUMER_MIGRATION.md) now implements tables, presentation
adapters, and source workflows. Next is 6E, external consumer migration. The earlier
`schema/execution/` prototype and later promotion plan is superseded. Native CUE suitability remains untested; the decision is an accepted
trade-off rather than a completed native-language evaluation.

The [domain migration plan](../DOMAIN_MIGRATION_PLAN.md) now records the accepted
six-checkpoint sequence and retained Step 1 work queue. Step 1 is complete: read the
[interface/consumer map](../DOMAIN_MIGRATION_MAP.md) and
[initial baseline](../research/domain-migration/BASELINE.md). At that checkpoint,
seven schema suites passed; 491 local tests passed and two baseline failures reproduced. Three live API tests and
external consumer execution remain unverified.

**Implementation update:** work units 2A/2B are now implemented. Read
the [record boundary](../RECORD_BOUNDARY.md) and
[Turn 1 verification](../research/domain-migration/turn1/README.md). The generated
immutable bundle and shared bounded validators are in the library; schema checks
delegate to them. Turn 2 (3A/3B) is also implemented: read the
[Model/Specification API guide](../DOMAIN_CORE.md) and
[verification](../research/domain-migration/turn2/README.md). Public lookup, local Values,
atomic revisions, units and immutable composition now work. The subsequent
[validation refactor](../DOMAIN_CORE.md#composable-validation) is also implemented:
read its [verification](../research/domain-migration/validation-refactor/README.md).
Shared helpers no longer belong to private Model modules; Formulation naming is
shared and expression checks consume an explicit lookup scope. Turn 3 is now implemented:
[Run and storage](../RUN_AND_STORAGE.md), with [verification](../research/domain-migration/turn3/README.md).
All three public roots, strict codecs, revision stores and installed-core checks are in place.
Final Turn 3 verification: 702 tests pass, the same two baseline failures remain,
and all seven schema suites, static checks and installed-wheel checks pass.
**Step 5 is implemented:** read [scalar execution](../SCALAR_EXECUTION.md) and its
[retained evidence](../research/scalar-execution/README.md). Authentic forward,
inverse and batch Runs now publish independently accepted immutable Models.
Final verification: **745 passed, the same two baseline failures**, all seven
schema suites, static checks and installed-wheel execution checks passed.
This implementation began at `53f5d3e` on `acausal-modelling` and remains local;
no commit or push was performed. The unrelated `.gitignore` edit is preserved.
Model-backed View, Hierarchy and explicit Value reductions are now implemented;
read [graph evidence](../research/graph-migration/README.md). That historical
checkpoint precedes the [6C/6D consumer migration](../CONSUMER_MIGRATION.md).
New adapters/workflows use Model; external projects remain unverified.
Graph-slice verification: **783 passed, the same two baseline failures**; seven
schema suites, 74-file static checking and installed graph/scalar checks pass.

**Step 6C/6D verification:** [consumer evidence](../research/consumer-migration/README.md)
records **798 passed and one unchanged numerical baseline failure**, all seven
schema suites, 80-file static checks, 27 viewer bundle tests, and installed-package
source-to-Model-to-solver acceptance. `WorkflowResult.model` and workflow version 2
are intentional breaks. Source observations keep their support chains; unsupported
Feature declarations fail explicitly. No external project was migrated or run.
No commit or push was performed. Continue with 6E, then remove the remaining old
Graph domain and codec in 6F after consumer acceptance. TypeScript rebuilding and
interactive browser acceptance remain unverified; the moved viewer bundles pass.

The original source-machine, transfer, and environment sections below are a
historical snapshot. The destination has since been observed on `acausal-modelling`
at the stated HEAD, with the documented dirty files. Recheck live state before
implementation. The independent audit and decision are additional local work.

Daniel has selected **Pyomo with HiGHS** as the primary algebraic backend. This
choice is settled; Pyomo **6.10.1** and HiGHS **1.15.1** are pinned and verified.
The implemented affine checkpoint is:

```text
Model₀ + Specification → execute → finalized Run + accepted immutable output Model(s)
```

Read these repository documents in order:

1. `docs/LIBRARY_ARCHITECTURE.md` — accepted boundaries, target layout, staged migration, and scalar acceptance criteria.
2. `docs/research/current-schema-comparison/README.md` — retained evidence, accepted decision, and reproduction commands.
3. `docs/MODEL_SPECIFICATION_RUN.md` and `schema/README.md` — record meaning and current conformance contracts.
4. `docs/SCHEMA_TOOLING_EVALUATION.md` and `docs/research/schema-tooling/README.md` — older, smaller study; preserve its observations.

## Original source-machine repository and session state

Verified on the source machine at handoff preparation:

- Work repository: `/Volumes/Data/Projects/Rangekeeper`.
- Remote: `git@github.com:daniel-fink/rangekeeper.git`.
- Branch: `acausal-modelling`, with no configured upstream.
- HEAD: `c91a76c941bac0a26fa18ad5a3105ab4641f22f0`.
- HEAD subject: `Define Model Specification Run schemas and conformance checks`.
- The branch was created from `feature/graph` as `feature/model-execution`, then renamed at Daniel's request.
- Session work is uncommitted and unpushed. No schema source or library runtime implementation has changed in this session.
- Source chat: **Rangekeeper executable checkpoint**, ID `01a0f62f-8838-7dc2-afe8-9a67a935a3e7`.
- The chat's attached working directory is `/Volumes/Data/Projects/Whirlwind`, a non-Git workspace. The actual task is in the separate Rangekeeper checkout.

The connected host is **Daniel's Mac Studio**, host ID
`remote-control:env_e_6a067b397c28832ca54b3ab6a28ee817`. The app currently lists a
Mac Studio project rooted at `/Volumes/Data/Projects/Whirlwind`, but no saved
Rangekeeper project. Destination checkout contents and synchronization have not
been verified. Open Rangekeeper directly for the continuation.

The available app handoff tool cannot move its own calling chat. This document
and its companion archive prepare continuity; they do not confirm chat migration
or delivery to the destination machine.

## Original transfer contents and subsequent local work

Tracked task edits:

- `README.md` — link to architecture plan.
- `docs/MODEL_SPECIFICATION_RUN.md` — architecture/backend decisions at transfer time; its original comparison-first sequence is now superseded.
- `schema/README.md` — corresponding migration order.

New task files:

- `docs/LIBRARY_ARCHITECTURE.md`.
- `docs/research/current-schema-comparison/README.md`.
- `docs/research/current-schema-comparison/capture.py`.
- `docs/research/current-schema-comparison/compare.py`.
- `docs/research/current-schema-comparison/observed/{manifest,results,summary}.json`.
- This handoff, saved as `docs/handoffs/2026-10-02-acausal-modelling.md`.

Subsequent local work includes `docs/README.md`, the independent audit and its
evidence archive, the accepted LinkML decision, and revisions to the architecture,
semantic specification, handoff, and document status notices. The original transfer
archive does not contain these later changes. Current docs are authoritative for
continuation; do not restore old copies over them.

An existing unrelated `.gitignore` edit adds the Syncthing temporary-download
pattern `.syncthing.*.tmp`. Preserve it. Its full-file SHA1 at handoff is
`4355efd11876bd54ae9e1ed818e411f0c5c4e0d5`; it is not part of the task patch.

## Accepted architecture

The schema owns record shape. The planned Python layers are:

1. `rk.model`, `rk.specification`, and `rk.run`: canonical domain records and behavior, with `rk.Model` as the public Model concept.
2. `rk.formulations`: construction helpers and supported mathematical implementations. `model/formulation.py` represents the schema record itself.
3. Domain validation and `rk.execution`: scope resolution, additive composition, roles, units, capability checks, compilation, evaluation, solving, acceptance, and publication.
4. `rk.graph`: views and algorithms over canonical Model objects.
5. IO and revision storage, adapters, and source-building workflows supporting those layers.

The library project remains rooted at `src/pyproject.toml`. The current Graph
container and domain classes require substantial replacement to satisfy the
schema; this is not just a namespace change. Characterize reusable graph
algorithms and numerical routines rather than assuming all code must be rewritten.

Map the replacement interfaces first. Build `_schema`, `model`, `specification`,
`run`, and `io` directly under `src/rangekeeper/`, then implement `execution`
against those canonical objects. Conformance scripts remain thin callers as
shared validation moves into the library. Migrate existing graph consumers,
adapters, and workflows incrementally; maintain one canonical new Model and one
executor, without a temporary parallel object model.

Existing distributions, extrapolations, projections, durations, Flows, Streams,
and financial functions can be connected gradually. Existing pandas-based Flow
and Stream operations do not automatically represent unknown-dependent symbolic
mathematics. Flow, Stream, and Account Value payload schemas remain deferred.

The selected LinkML boundary is schema-generated shared Python record machinery
plus closed JSON Schemas, explicit structural preflight, and handwritten domain
behavior. Generated record mutability is contained by the immutable snapshot/store
boundary. Do not maintain a second handwritten authoritative Python field schema.

## Contracts to preserve

- Stable UUIDs carry native identity; readable codes are presentation fields.
- Model revisions are immutable. Recorded quantities do not implicitly become fixed assignments or estimates in a later solve.
- Specifications supply assignments, unknowns, estimates, and investigation-specific mathematics.
- Composition is additive: a repeated pinned revision in a diamond contributes once; independent authoritative contributions conflict even when their values are equal.
- Model mathematics cannot be overridden by Specification mathematics.
- Formulation ownership and reference visibility are distinct; shared UUID references can cross Formulation boundaries.
- Temporary Specification mathematics is not silently promoted into output Models.
- Runs are finalized evidence records. Batch outputs equal the unique union of accepted direct child outputs, with every direct case accounted for.
- Timeout is not infeasibility; a feasible candidate is not proof of uniqueness or optimality.
- `Study` names the broader analytical process. Existing graph `WorkflowSpec` remains a distinct source-building concept.

## Original comparison evidence and baseline

All seven existing schema suites passed in the prior session on 2026-10-01:
`validate.py`, `native_roundtrip.py`, `expressions.py`, `formulations.py`,
`models.py`, `specifications.py`, and `runs.py`. Their detailed counts are in the
comparison README. Source fingerprints still matched at handoff preparation on
2026-10-02; the suites were not rerun merely to prepare this handoff.

The capture harness observed 713 distinct schema/input pairs across 20 generated
structural schemas. The bounded CUE 0.17.1 JSON Schema import probe recorded:

| Outcome | Count |
| --- | ---: |
| Same acceptance outcome | 476 |
| Different acceptance outcome | 21 |
| Five-second validation timeout | 3 |
| Unmeasured after that schema timed out | 208 |
| Non-finite Python numerical input outside strict JSON | 5 |

Thirteen of the differences accepted inputs rejected by the current validator,
including blank/padded Entity codes, Binding names, and Constraint/Formulation
codes. Eight failed to accept currently accepted inputs: seven Query records and
one Expression. Timeouts involved Model, Formulation, and Expression schemas.
A diagnostic Model attempt also exceeded 30 seconds.

These findings concern an imported representation. They do not establish that
native CUE authoring is unsuitable. Matching rejection outcomes also do not prove
that both validators rejected an input for the same reason. The existing Python
semantic checks passed separately; they have not been reimplemented in CUE.

The retained scripts compile, evidence totals and source fingerprints were
checked, local Markdown links passed, and `git diff --check` passed. No new-schema
executor produced the synthetic Run/output fixtures.

An earlier targeted Python baseline reported 208 passes and one pre-existing
failure in `test_adapters.py::test_supported_adapter_and_table_surfaces_are_explicit`.
That result predates the comparison pass; recheck it when migration requires
those tests, and keep unrelated adapter repair outside this task.

## Immediate continuation

1. Verify the current checkout, branch, HEAD, dirty files, and applicable instructions. Preserve unrelated edits and retained evidence; do not restore the historical transfer archive over current work.
2. Read the completed `docs/DOMAIN_MIGRATION_MAP.md` and `docs/research/domain-migration/BASELINE.md`. Preserve its observed failures and external-verification limits. Start work unit 2A: reproducible shared generation, immutable runtime projections and packaged structural artifacts; do not restart Step 1.
3. Build the minimal schema-backed library core directly in `src/rangekeeper/`. Generate shared LinkML records and structural validators, reuse/evolve semantic checks, implement composition and codecs, and verify immutable snapshots, round trips, lightweight imports, and installed-package artifacts.
4. Probe Pyomo + HiGHS in isolation and pin tested versions. Implement `rangekeeper.execution` against the new core, loading actual Models and composed Specifications, preparing units/roles, lowering declared expressions, and independently checking candidates before publication.
5. Demonstrate forward/inverse output, genuine output reuse, changed-expression behavior, failures/limits, settings/provenance, and sequential batch accounting. Then migrate remaining graph operations and consumers, followed by richer numerical/temporal capabilities.

The [independent audit](../research/current-schema-comparison/audit-2026-10-02/README.md)
reproduced all seven schema suites and original bounded comparison outcomes.
Its complete five-second pass recorded 572 matching outcomes, 28 differences,
106 timeouts, and seven non-JSON numerical inputs. No cases were skipped.
Reuse this baseline where applicable; rerun checks when implementation changes
justify them. The [decision record](../research/current-schema-comparison/DECISION.md)
supersedes the original requirement to finish the native CUE comparison.

The scalar executor must solve the actual declared relations:

```text
NOI = homes * annual_rent_per_home - annual_operating_cost
capital_value * capitalization_rate = NOI
```

Forward expectations are NOI `550,000 AUD/year` and capital value `11,000,000 AUD`.
Inverse expectations are annual rent `27,500 AUD/dwelling/year` and NOI
`500,000 AUD/year`. Reuse a genuine forward output in a new inverse Specification;
verify candidates against the original expression trees; publish authentic Run
records and immutable outputs. Full acceptance details are in the architecture
plan, including changed-expression tests, batch accounting, failures, deadlines,
settings, provenance, and preservation of unrelated content.

## Historical environments and subsequent audit environment

The following are original source-machine paths, not portable dependencies or
claims that these environments exist on the destination:

- `src/.venv/bin/python`: current Rangekeeper runtime environment.
- `/private/tmp/rk-code-schema-venv/bin/python`: Python 3.10.21, LinkML 1.11.1, jsonschema 4.26.0. Temporary probing also installed SymPy 1.14.0 and Pint 0.24.4 here.
- `/private/tmp/rk-cue-full-contract-tools/cue`: CUE 0.17.1. Official macOS arm64 archive SHA256 is `64921403f012a97f89494c03605db2fbf7d9daa77dc2631819ac4406cb2e8074`.
- `PYSTOW_HOME=/private/tmp/rk-block-pystow` avoided writes to the source user's home during schema tooling.
- `/private/tmp/rk-cue-current-study/`: captured corpus, generated schemas, and exploratory variants.

The independent audit used `/private/tmp/rk-probe-audit-venv/bin/python`
(Python 3.10.19; LinkML/linkml-runtime 1.11.1; jsonschema 4.26.0) and
`/private/tmp/rk-probe-audit-tools/cue` (CUE 0.17.1). Its corpus and baseline
outcomes reproduced despite the Python patch-version difference. Temporary paths
can disappear; the audit archive retains scripts, results, and a package freeze.
Recreate required environments when necessary; do not copy virtualenvs.
Pyomo and HiGHS have not been installed or probed for this checkpoint. The
research README contains reproduction commands and the manifest identifies the
tested source files and versions.

The companion archive includes selected scratch source and a note about failed
Expression/Selection replacement experiments. These were diagnostic hybrids,
not a completed native CUE schema. Preserve the distinction from retained
import-route evidence and do not promote them into the authoritative schema.

## Historical companion archive and restoration

The transfer archive contains this brief, `task.patch`, complete copies of the
task files under `files/`, an optional `unrelated-gitignore.patch`, selected
scratch references, and `manifest.json` with SHA256 hashes.

If the destination already has these changes through synchronization, compare
hashes and continue without reapplying them. Otherwise, establish a checkout at
the exact base commit, use `acausal-modelling` when available or create that
branch from the base, and check `task.patch` with `git apply --check` before
applying it. Copy new files only after checking for destination conflicts.
The complete file copies are also available for manual reconciliation.

The archive does not contain the complete Git repository, a Git history bundle,
credentials, a runtime environment, or the full chat transcript. Do not reset an
existing checkout or overwrite divergent files to make the snapshot fit.

Commits, pushes, and releases were not performed by this session. This handoff
does not add publication authorization. No agents have been delegated work.

## Suggested continuation prompt

> Continue the Rangekeeper acausal modelling work from
> `docs/handoffs/2026-10-02-acausal-modelling.md`. Verify the Rangekeeper checkout
> and preserve existing work. LinkML and Pyomo with HiGHS are selected. Steps 1–5
> are implemented, plus Step 6A/6B: read `docs/DOMAIN_MIGRATION_MAP.md`,
> `docs/SCALAR_EXECUTION.md`, `docs/GRAPH_MODEL.md` and their retained evidence.
> Step 6C/6D is implemented: read `docs/CONSUMER_MIGRATION.md`.
> Continue with Step 6E: migrate external consumers in
> bounded slices with acceptance checks before retiring old domain code.
> Preserve genuine forward/inverse execution, independent acceptance and batch accounting.
> Do not reopen native CUE research or create a temporary `schema/execution/` core.
