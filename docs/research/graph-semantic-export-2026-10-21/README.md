# Guarded internal semantic export experiment

Status: experiment retained; dev5 wheel built and locally verified. Final artifact
review and coordinator readback precede Git delivery. Core adoption remains separate.
Base: RK develop 8c50e06bd045b1298da15be5be296a1150d2d339.
Owner: WW-51. Branch: feature/semantic-validation-read-cost.

## Original experiment scope

These two sections record the original experiment. The later packaging amendment
and Daniel's longer-opening decision below supersede its version and initial-load
deadline restrictions. The production guard and frozen experiment remain unchanged.

Only change `_validate` data selection in `src/rangekeeper/model/validation.py`:
borrow `record._data` only when `type(record) is ModelRecord` and `"geometry" not
in record._data`. Every other case retains `record.to_data()`, including subclasses
and any present Geometry field. Generated construction still copies, structurally
validates, normalizes and freezes inputs. Semantic check order, first-error
diagnostics, history, indexing, units and public detached exports remain unchanged.
Geometry needs plain JSON for digest checks, so it must retain the export path.

Add only `src/tests/test_model_validation_equivalence.py`, this evidence page and
the research index. No semantic helper, runtime, index, generator, schema,
dependency, version, Core or Interface changes. Preserve prior evidence,
environments, wheels, refs and previews. Stop for a newly required production path.

## Original experiment procedure and limits

The ignored `.runtime/graph-semantic-export-2026-10-21` holds activation and
dependency/interpreter pins, named activate.py, verify.py,
measure-semantic-export.py and freeze.py helpers, original-function oracle,
immutable baseline/candidate sources and complete results. Create a new isolated
environment from the unchanged lock and existing cached payloads; no old install
or network/service configuration changes. Compare ordered diagnostics and
ownership against the frozen original function before timing, including multiple
faults, all semantic families, raw inputs, indexes, history, Geometry and subclass
fallbacks, presence, input nonmutation and detached public exports.

Run three serial paired fresh-process trials per unchanged primary/growth fixture.
Record first and subsequent fully validating public codec reads, imports, exact
source/input hashes, memory and all failures. Do not edit measured snapshots.
The original export subtree is 0.312426 seconds cumulative, 4.4 percent of a
7.119-second profiled run; this is an attribution bound, not measured savings.
Growth codec time is 7.459 seconds and still exceeds Core's five-second budget.
No deadline increase, fixture reduction, prewarming or capacity claim is allowed.
Omit the candidate if gain is not stable and material. Retention requires
independent review and a separately released version/wheel/delivery packet.

## Verification on 21 October 2026

The isolated environment uses Python 3.12.3 and the unchanged lock SHA256
`b97849d09a72b7ed24b37cd4ed9c0fad59b9a213d58a3758b0dba29688c34c8c`.
`activation.json` records the baseline, exact paths and protection inventory;
`environment.json` records the interpreter, 76 distributions and setup command.
All commands ran from the Rangekeeper root through the named helpers above.

The first equivalence run is retained in `verification-1`: 135 passed and five
failed test expectations. Both implementations produced the same scenario
parameter ValueError; the test wrongly required a ValidationReport. Three null
optional sections failed structural validation before semantic validation; their
tests wrongly required valid records. Only the new test was corrected. The exact
failed helper, test, production module and log remain preserved.

`verification-2/plan.json` pins the corrected test, full source map, commands and
environment. All 140 ordered diagnostic/ownership equivalence cases passed in
5.75 seconds. All 1,248 source tests passed in 202.93 seconds. Black, documentation
and diff checks passed. Independent review cleared the production guard, original
function oracle, corrected assertions and measurement helper before timing.

## Paired full-fixture measurements

The helper ran 12 serial fresh processes: three baseline/candidate pairs for each
unchanged full fixture, with order reversed in the second pair. Each process
verified the intended package import before timing, then checked every loaded RK
module path, exact input hashes, both detached exports and the independent compact
oracle digest. Import time is separate from the reported codec read time. Each
second read repeats full validation; it is not a cached result. All trials passed.

| Full fixture | Read | Baseline median (s) | Candidate median (s) | Reduction |
| --- | --- | ---: | ---: | ---: |
| Primary 377/376 | First | 2.952391 | 2.853044 | 3.36% |
| Primary 377/376 | Subsequent | 2.609506 | 2.484140 | 4.80% |
| Growth 1024/1024 | First | 7.443671 | 7.224215 | 2.95% |
| Growth 1024/1024 | Subsequent | 7.194244 | 6.815702 | 5.26% |

Every candidate read was faster than its paired baseline. Growth first-read
ranges were 7.424391–7.466348 seconds for baseline and 7.188167–7.236401 for the
candidate. The paired first-read reductions were 0.242133, 0.187990 and 0.255504
seconds. These exceed the observed within-variant first-read ranges, but three
pairs are a bounded experiment, not a general performance or capacity guarantee.

Growth median process peak RSS was 378,257,408 bytes for baseline and 378,503,168
for the candidate. Maximum peaks were 379,076,608 and 382,582,784 bytes respectively.
No memory improvement is claimed. Primary median peaks were 204,783,616 and
202,080,256 bytes. Per-process import timings, memory, full module paths, failures,
source pins, commands and outputs are in `measure-1`.

## Disposition and remaining work

The candidate has a consistent modest gain in these unchanged full fixtures.
Independent experiment review cleared it, and the coordinator released the exact
[packaging amendment](packaging-proposal.md). Packaging results follow below.
Git staging, commit, push and Core adoption still require separate clearance.

Growth direct RK first-read median remains 7.224215 seconds. The last delivered
Core baseline failed its first supervised full-growth read at 5.016142 seconds
under the former five-second rule; that failure is preserved. On 21 October the
user accepted a longer finite initial load while requiring responsive graph
interactions. Five seconds is no longer an initial-load acceptance blocker.
The full 1024/1024, matched Core/HTML, private-state reopen, interaction and
actual-host checks remain open. No deployment or live result is established here.

The immutable `snapshot.json` pins baseline and candidate packages plus the test
and helpers (SHA256 `60a689c2951eaf7450c27d43e145e2a27154969ed1a96c0c22b68abe92a1c0cd`).
`final-manifest.json` records final owned-file hashes, receipts, protected-file
verification and unchanged original references. All older experiments, failures,
environments, wheels, recovery references and Interface previews remain protected.


## Dev5 packaging verification

The exact released amendment is preserved under
`packaging-1/preserved/docs/research/graph-semantic-export-2026-10-21/packaging-proposal.md`.
The original experiment manifest, snapshot and all four original file versions
remain intact. Activation SHA256 is
`3c34401aebfbfa3d210a5d998a30dd3edaddb415e98d895caf9ad8336c6622a2`;
it records 1,828 tracked files, 62,245 protected entries and seven preserved files.

Only the project version and editable RK lock entry changed to `0.10.0.dev5`.
The other 89 lock entries and dependency metadata are unchanged; offline lock
checking passed. New isolated environments use the pinned interpreter, copied
setuptools 80.9.0/pip 24.0 and 74 unchanged third-party distributions. Neither local
project was installed editably. All non-RK dependency RECORD hashes remained
identical after installing the wheel.

The single wheel is `rangekeeper-0.10.0.dev5-py3-none-any.whl`, 1,044,053 bytes,
SHA256 `b5c01c3fce1b78793bb459ab137e5739c165d3cc612373384892c017f97eeaac`.
All 150 build inputs were pinned; all 145 package payload files equal the measured
candidate. Archive paths, RECORD digests/sizes and exact package membership passed.
Compared with dev4, distribution metadata differs only by version and its dependent
paths/RECORD entries. The package difference remains the reviewed semantic guard.

`checks-1` preserves an installed-verification pass and 607 regression passes plus
one runner failure. Multiprocessing re-entered the helper and attempted to recreate
a receipt, causing FileExistsError/BrokenProcessPool. The original helpers and
failure log remain in `helper-repair-1` and `checks-1`; `helper-amendment-1.json`
pins the corrected main-entry guard and separate output paths. No production,
wheel, dependency or test change was needed.

`checks-2` passed the installed-package verification slices and all **608 exact-wheel
regression tests**, including the 140 equivalence cases. Collection and final import
checks exclude checkout `src` and require every RK module to come from the new
installed wheel. Both unchanged full fixtures passed two codec reads and detached
export equality against their frozen independent hashes. These are correctness
checks, not a new paired performance campaign. Black, docs and diff checks passed.
The earlier 1,248 source passes retain identical source/test pins.

The packaging manifest is a new artifact under `packaging-1`; it does not replace
the experimental manifest. It freezes the seven delivery paths, artifact, helpers,
failures, receipts and protection results for independent review. No staging,
commit, merge, push, Core installation or service change occurred in packaging.
Further cold-load experiments are deferred under the user's new requirement.
