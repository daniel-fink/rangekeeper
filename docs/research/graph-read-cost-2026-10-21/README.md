# Graph read cost and exact record lookup

Status: reviewed A+B repair cleared for scoped integration. This page records the
implementation and verification checkpoint. Git delivery is recorded separately
in `.runtime/graph-read-cost-2026-10-21/delivery.json` and the coordinator handoff.
C was measured and omitted because it showed no material gain.
This work supports a legacy consumer's 1,024-node/1,024-Relationship target.
The primary checkout started from clean `develop`
`0c0d25521a717c5ea6f487ae3cebfdd859b2f9b5` and uses
`feature/graph-read-cost`. The coordinator released two separate scopes from
the consumer interface's proposal SHA-256
`bf9ba38e91f46ee98706dcda06a7c59a0e7022bc5c2276ccff155401e3a2c877`.
Activation retains 1,823 tracked hashes, 1,870 protected evidence files and the
existing walkthrough and `gh-pages` refs. No publication is included.

## A. Schema preparation

The runtime prepares local reference validators using supported jsonschema
`extend` and `evolve` APIs. Stock keyword and date/date-time validation remains.
Only immutable schema preparation is reused; every document is validated in full.
Unknown scopes, reference forms or root assertions use the original validator.
Explicit Draft 2020-12 behaviour is retained despite the packaged root's 2019
schema declaration. No generated schema, dependency or canonical rule changes.

The corrected independent-oracle suite passes 174 tests. It compares all 104
packaged definitions, ordered diagnostics and nested contexts, positive examples,
recursive records, presence, non-JSON failures, public semantic/identity failures,
a real derived-Claim cycle and explicit dialect behaviour. The first 173-test
log remains, with the pre-correction test file; it did not correctly exercise
cycle detection. Production source did not change during that correction.

Serial fresh-process public JSON codec reads used the unchanged dense fixtures
and the same isolated locked Python 3.12.3 environment:

| Fixture and read | Original | Prepared schema |
| --- | ---: | ---: |
| Primary, first read | 3.704 s | 2.978 s |
| Primary, repeated read | 3.363 s | 2.611 s |
| Growth, first read | 9.491 s | 7.577 s |
| Growth, repeated read | 9.232 s | 7.207 s |

The growth fixture retains 1,024 nodes, 1,024 Relationships, 10,240 Values and
30,720 Claims. Export equality and canonical digests pass. The primary is the
representative 377-node/376-Relationship synthetic topology. Neither fixture is
reduced. The first read occurs after imports in a fresh process; repeats still
perform full validation. These are direct RK measurements, not the primary consumer or browser
results. The growth read remains above the primary consumer's unchanged five-second deadline
before the primary consumer adds authorization, digest and projection work. A is insufficient
for the target and needs a further reviewed scope. The
[further generator review](further-validation-proposal.md) identifies limited
redundancies and their diagnostic tradeoffs; it does not establish a solution.

Separate phase diagnostics and a separate cProfile run retain their own results.
Their nested cumulative times overlap and must not be added. The profile adds
overhead and does not replace the unprofiled timings.

## B. Exact record lookup

The separately released scope adds public immutable locations through
`Model.record_at` and `Model.record_by_id`. It must match the existing schema
walk's original paths and nearest owners, including anonymous records. UUID
lookup uses the existing index; path lookup follows only the selected embedded
chain. It does not make unrestricted enumeration unbounded. The [Model reference](../../reference/model.md) owns the API contract.
The exhaustive walker oracle and prohibited-work tests cover exact types, owner
identity, paths, opaque content, immutability and error boundaries. Dense fixture
checks select seven record kinds from 34,334 primary and 93,212 growth records.
The late growth Value lookup has a 0.010 ms median; its late Claim has a 0.005 ms
median. These calls occur after full Model validation and are not the primary consumer transport
or browser measurements.

The original test guard patched the base record allocator. Its restoration left
CPython allocation state changed and caused 97 later constructor failures in the
first full test run (1,010 passed). Two isolated reproductions preserve the cause
and replacement behavior. The corrected guard uses temporary registry proxies;
it leaves generated classes unchanged and checks normal construction after
restoration. Independent review cleared that test correction and typing-only
annotations. The next full run passes all 1,108 tests.

## C. Strict-copy experiment

The [runtime cost proposal](runtime-validation-proposal.md) separates measured
exclusive costs from overlapping cumulative costs. The coordinator released only
exact-builtin fast paths in `copy_json`, with a frozen original-function oracle.
All key, cycle, nonfinite-number and custom-container behavior must remain, as
must both strict copy passes. No schema, semantic validator or public codec change
is included. The reviewed A+B source was frozen before the experiment. The first candidate
passed 74 tests, but review found that equality-based type checks could select the
wrong branch for a Mapping subclass with custom metaclass equality. That candidate
and its interrupted measurement are retained. The corrected identity-only guard
passes 75 tests and independent review.

Three serial paired fresh-process comparisons used the full unchanged fixtures:

| Median public codec time | Frozen A+B | Corrected C |
| --- | ---: | ---: |
| Primary cold | 2.960 s | 2.936 s |
| Primary warm | 2.579 s | 2.582 s |
| Growth cold | 7.459 s | 7.417 s |
| Growth warm | 7.171 s | 7.139 s |

Cold growth improves only 0.57%; primary warm is slightly slower. This is not a
material repair of the target. C production and its proposed checked-in test were
omitted. All 218 files in the package/test snapshot now match the passing A+B checkpoint exactly.
Both C source snapshots, test versions, error correction, raw pairs, fixture
hashes, exact export digests and RSS values remain in `runtime-experiments`.
Its `disposition.json` has SHA-256
`d3c3a1c752a898b23475ea54d284055c1aacb4ce571140f60f303cde7953296b`.
Other proposed runtime changes and the generator experiment are not activated.

## Evidence and remaining gates

Ignored `.runtime/graph-read-cost-2026-10-21/` contains activation/environment
receipts, the complete original package source, both equivalence logs,
`validation-measure-1` raw timings/source hashes, the separate profile and
`a-checkpoint/manifest.json`. The A checkpoint SHA-256 is
`3d55b9171d291c539827be594fa5d867f36ae22c89bdafb34b14bf1af15d54d2`.
The original primary consumer dev3 dependency and all failed evidence remain unchanged.

Runtime dependencies come from the unchanged lock in a new environment. Offline
setup lacked one locked Python 3.12 wheel; the network retry retained exact lock
versions. A separate schema environment uses the pinned requirements and mypy
1.18.2, plus packaging tools; it can read the isolated locked runtime dependencies.
No shared environment or the primary consumer dependency was changed.

The candidate has the distinct development version `0.10.0.dev4`; only its own
local package lock entry changes. Its wheel SHA-256 is
`72cc3e1ba516ab3f4f4a67585bcda8a98d560625f8d34f7ae9aeed461e6011ce`,
1,044,018 bytes, with all 145 tracked package files verified byte-for-byte.
The initial post-build verifier also expected an ignored macOS `.DS_Store` that
setuptools correctly omitted. The build log and 151-input source inventory remain;
`verify-built-wheel.py` verifies the same wheel against all tracked package files
and explicitly records that sole non-package omission. No wheel was rebuilt or
replaced. The exact wheel passes `verify_install.py` minimal records/codecs/stores,
Model/unit/composition, financial, process-isolated solver, Polars/CSV and example
checks. Its selected regression suite passes 424 tests; all parent-process RK
imports are verified inside the extracted wheel. Tests with explicit subprocess
source overrides retain their source-only scope. These results are in
`artifact-checks` and `wheel-tests.json`.
Independent final review and coordinator packet readback passed. Only the 13
reviewed paths are released for scoped integration. The original frozen packet
remains unchanged; a separate delivery manifest records this administrative note.
The reviewed A+B checkpoint is `ab-checkpoint/manifest.json`, SHA-256
`25c704393cc5a695c6a657622fe91bdb135710a0c7b822aeb08160464dfdd82d`.
`verification-1` retains the original test/typing failures. Its seven conformance
suites, both generation checks, native and documentation checks passed.
`verification-2` passes the corrected full Python suite, typing and diff checks.
`verification-dotnet8` passes a portable Model/Tests build and complete Python →
C# → Python content/presence/ordered-mathematics round trip. These checks use the
official .NET 8.0.426 SDK with its downloaded SHA-512 verified, in the ignored
runtime. The earlier .NET 10 build and missing-.NET-8-runtime failure remain.
No Rhino component loading or Windows acceptance is established.

Primary consumer dependency and exact Inspect consumption need a separate reviewed window.
Matched consumer interface browser/state checks, the remaining layout target, supported
capacity, actual hosts and release are separate gates.
