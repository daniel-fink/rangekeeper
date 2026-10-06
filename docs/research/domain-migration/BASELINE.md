# Step 1 observed baseline — 2026-10-02

Status: completed local baseline and bounded record-boundary feasibility review.
No production Python, authoritative schema, existing test expectation, or consumer
implementation was changed. This is not certification of the future runtime.
The [migration map](../../history/DOMAIN_MIGRATION_MAP.md) contains the resulting design.
This is the preserved pre-implementation baseline; subsequent production changes
and verification are recorded separately in [Turn 1](turn1/README.md),
[Turn 2](turn2/README.md), and [Turn 3](turn3/README.md).

## Checkout, environments and protection

- Repository: `/Volumes/Data/Projects/Rangekeeper`, branch `acausal-modelling`,
  HEAD `c91a76c941bac0a26fa18ad5a3105ab4641f22f0`.
- Existing changes included documentation/research, the schema/root README updates,
  and an unrelated `.gitignore` edit. The initial state and hashes of every tracked
  file are in [initial-state.json](evidence/initial-state.json). No AGENTS.md was
  found in the repository or inspected ancestor locations.
- Runtime Python: 3.10.19, `src/.venv/bin/python`. From the `src/` project it imports
  this checkout's `src/rangekeeper/__init__.py`. From the repository root the initial
  direct import failed with ModuleNotFoundError: this environment is not evidence
  of installed-package usability. New installed-wheel acceptance remains required.
- Pinned schema environment: `/private/tmp/rk-probe-audit-venv/bin/python`, Python
  3.10.19, LinkML 1.11.1, linkml-runtime 1.11.1, jsonschema 4.26.0.
- The existing runtime lacked PyYAML, so complete pytest collection initially failed.
  An isolated `/private/tmp/rk-domain-runtime` environment inherited the existing
  runtime packages and added already-installed PyYAML 6.0.3, openpyxl 3.1.5 and
  et_xmlfile from the audit environment. No runtime environment or lockfile in the
  repository was changed. This supplemental environment is recorded explicitly;
  its success is not attributed to the original environment.
- All package versions are retained in [runtime-environment.log](evidence/runtime-environment.log),
  [runtime-with-extras.log](evidence/runtime-with-extras.log), and
  [schema-environment.log](evidence/schema-environment.log). No dependency installation
  or external service call was needed.
- LinkML initially failed because PyStow attempted to create `/Users/daniel/.data`.
  Corrected runs use `PYSTOW_HOME=/private/tmp/rk-domain-migration-pystow`;
  Matplotlib uses Agg and Python bytecode writing is disabled. Initial failure logs
  remain alongside successful second attempts. No schema modification fixed them.

Exact argv, cwd, relevant environment overrides, duration, exit code and log filename
are retained in [commands.jsonl](evidence/commands.jsonl). First attempts predate the
runner's cache override and therefore have no override field. Schema scripts create
their generated outputs in temporary directories. Adapter/workflow tests use pytest
temporary paths; plots are suppressed by existing conftest behavior. The tracked-file
comparison immediately after baseline checks found zero changes. The final
[preservation report](evidence/preservation.json) checks all 488 initially tracked
files and confirms zero changes outside the intended Markdown documentation.

## Results

| Check | Observed result | Evidence |
| --- | --- | --- |
| Original runtime collection | 439 collected; 3 collection errors from missing PyYAML in workflow modules. Execution also stopped at collection. | [collection](evidence/pytest-collection.log), [attempt](evidence/pytest-local.log) |
| Supplemental runtime collection | 493 tests collected; live API module excluded. | [collection](evidence/pytest-collection-extras.log) |
| Supplemental runtime execution | **491 passed, 2 failed**, 7 warnings; no skipped tests. | [log](evidence/pytest-local-extras.log), [JUnit](evidence/pytest-local-extras.xml) |
| Narrow reproduction | Both failures reproduced unchanged, 2 failed. | [reproduction](evidence/pytest-failure-reproduction.log) |
| Record-boundary feasibility | **14 assertions passed**, 50 generated classes, 14 structurally valid document fixture round trips. | [results](evidence/record-boundary-results.json), [log](evidence/record-boundary-attempt2.log) |

The three excluded live tests are `TestApi.test_connection`, `test_model`, and
`test_conversion` in `src/tests/test_api.py`. They use Speckle authentication or
receive live objects and are **unverified**, not passed/skipped pytest outcomes.

### Seven schema suites

All seven passed after the cache-location correction, with their existing code and
fixtures unchanged:

| Suite | Reported coverage | Log |
| --- | --- | --- |
| validate | 13 generated schemas, both examples, 80 rejection cases | [log](evidence/schema-validate-attempt2.log) |
| native_roundtrip | Native identifiers, typed references, both example round trips | [log](evidence/schema-native_roundtrip-attempt2.log) |
| expressions | 9 schemas; 71 valid, 103 structural and 31 semantic rejections; native round trips | [log](evidence/schema-expressions-attempt2.log) |
| formulations | 6 schemas; 10 valid scopes, 32 structural and 20 semantic rejections; 10 round trips | [log](evidence/schema-formulations-attempt2.log) |
| models | 3 schemas; 6 valid, 26 structural and 24 semantic rejections; 6 round trips | [log](evidence/schema-models-attempt2.log) |
| specifications | 6 schemas; 17 valid, 46 structural and 37 semantic rejections; 17 round trips, plus composition checks reported in log | [log](evidence/schema-specifications-attempt2.log) |
| runs | 10 schemas; 18 valid Run/tree cases, 28 structural and 45 semantic rejections; 31 round trips | [log](evidence/schema-runs-attempt2.log) |

Counts overlap by responsibility and are not added into a claimed unique corpus.
These remain bounded validators with synthetic Run/output fixtures. No equation
executor, numerical acceptance evaluator, or authentic new-schema Run was produced.

### Failure classification

1. **Adapter export contract mismatch — current code/test disagreement.**
   `test_supported_adapter_and_table_surfaces_are_explicit` expects `ingestion` and
   `operation` in the adapter `__all__`; the implementation exports neither there.
   This assertion fails before later assertions are evaluated. The mismatch is
   directly visible in the inspected source and reproduces in isolation. Do not
   silently bless either side by changing the expected list during migration.
2. **Residual-solver expectation — existing numerical discrepancy, cause unresolved.**
   `TestSolver.test_residual` obtains `239654.64258295443` where the test expects
   `241049.33 ± 0.241049`. The identical value reproduced in isolation. This confirms
   a pre-migration baseline failure, not whether the routine or expectation is right
   or whether dependency versions explain it. Diagnosis/repair is separate work.
3. **Missing PyYAML — environment deficiency.** Resolved for this baseline through
   isolated declared workflow extras, without editing production or tests.
4. **PyStow cache permission — environment configuration.** All schema failures in
   the initial attempt stop at the same cache setup. All pass with an allowed cache.

## Record-boundary experiment and limits

[record_boundary_probe.py](evidence/record_boundary_probe.py) combines the three
schema imports, exercises stock native generation, and generates explicit read-only
properties/constructors from induced slots. [readonly-probe-generated.py](evidence/readonly-probe-generated.py)
is retained generated research output, not library implementation.

The experiment confirmed native-record mutability, protected nested mappings and
sequences, detached input/export data, typed UUID access, explicit constructor
signatures, resolvable type annotations, nested authoring, absence/null/zero
preservation, false/zero in opaque content, and exact fixture data round trips.
It accessed all declared fields in the 14 loaded fixtures. The original failure
([log](evidence/record-boundary.log)) revealed that LinkML Any content needs an opaque
JSON mapping path rather than a structured-record wrapper; the corrected projection
handles it using schema metadata.

This does **not** establish semantic constructor validation, static type-checker
acceptance, store correctness, package installation, complete generated union typing,
or full public ergonomics. The prototype permits omission in all constructor
signatures; production generation must enforce unconditional required arguments and
correct unions/enums. These implementation obligations are specified in the map.
The approach is feasible; its implementation and packaging remain Steps 2–4.

## Inventory and acceptance coverage

[inventory.json](evidence/inventory.json) records 93 module inventories, seven
notebook source inspections and available external references. The inspected shared
projects repository was on branch `feature/mandarin-assembly-layout` at
`5725cc02748ace15e390c8dcea2c5d69185d67c9`; its current commit is recorded in the artifact.
Mandarin and East Whisman tests were inspected, not executed. Their Python/data
requirements and expected migration acceptance are in the map. Grasshopper C# and
its Speckle 2.18.0 references were inspected; no Rhino/.NET runtime acceptance ran.
`git ls-files hypar` returned no source files; ignored artifacts are not a usable
source baseline. Archived Mandarin code is not an active migration obligation.

[Test summary](evidence/test-summary.json) reports counts per Python module and the
three live exclusions. Existing tests characterize old Graph semantics; passing
those tests does not prove the new Model contract is implemented.

| Future invariant | Existing evidence | Required implementation acceptance |
| --- | --- | --- |
| Several Values per Measure | Model/schema fixtures; old Graph keys Measurement by Measure | Local keys and UUID lookup distinguish Values with shared Measure. |
| Assembly canonical occurrence | Model semantic cases; current Graph stores Assembly among Entities | Stored once under assemblies; accepted by Entity references without duplication. |
| Formulation-local Values and cross-scope references | Formulation/Model suites | Model indexes all canonical declarations; composition adds eligible local scope without shadowing. |
| Revision-scoped identity | Model/Specification/Run suites and old revision tests | Same declaration UUID can differ across revisions; lookups never leak another revision's instance. |
| Deep immutability | 71 old graph cases plus boundary probe | Nested and opaque data, source dictionaries, exported dictionaries and repeated store reads cannot mutate snapshots. |
| Additive composition | Existing composition checks | Diamond deduplication, duplicate contributor conflicts, no overriding, preserved requirement sources. |
| Presence and mathematical order | Existing native checks plus 14 exact probe round trips | Constructor/load/export/store all preserve required distinctions and ordered expressions/objectives/trace. |
| Revision storage | No production implementation | Same-ID conflicts, typed resolution, idempotence, concurrent puts, interruption before atomic publication. |
| Unit meaning | Old unit tests, bounded schema checks | Physical conversion, distinct currencies/count dimensions, unresolved quantities, bool/nonfinite rejection. |
| Packaged artifacts and imports | Existing lazy-import tests; root import failed outside source project | Clean installed-wheel verification outside checkout; core imports without optional backends/integrations or LinkML generator. |

## Reproduction

The retained runner supports a fresh output directory; do not overwrite this evidence.
Validate interpreter locations and versions first because temporary environments may
be removed. To reproduce the recorded supplemental runtime, the preparation script
uses the existing runtime packages and copies only the already available workflow
extras into an isolated venv. It does not resolve/update dependencies.

```sh
# From the repository root; creates only an isolated /private/tmp environment.
python3 docs/research/domain-migration/evidence/prepare_runtime.py
python3 docs/research/domain-migration/evidence/run_baseline.py capture --output-dir /private/tmp/rk-domain-rerun
python3 docs/research/domain-migration/evidence/run_baseline.py schema --output-dir /private/tmp/rk-domain-rerun
python3 docs/research/domain-migration/evidence/run_baseline.py tests --runtime-python /private/tmp/rk-domain-runtime/bin/python --output-dir /private/tmp/rk-domain-rerun
```

For a fresh record probe use `RK_RECORD_PROBE_OUTPUT=/private/tmp/rk-record-rerun`
and `PYSTOW_HOME=/private/tmp/rk-domain-migration-pystow` with the pinned schema
Python and `record_boundary_probe.py`. Its exact observed invocation is in
commands.jsonl. No external service tests, project
exports, notebooks, C# builds, commits, pushes, or releases were performed.
