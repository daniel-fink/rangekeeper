# ADR-005 local implementation acceptance — 2026-10-08

The codebase implementation of [ADR-005](../../decisions/005-flux-and-stream-implementation.md)
passed local acceptance. Notebook migration remains a separate phase. The
[executable example](../../../examples/rangekeeper_examples/flux.py) covers both the
small Stream interface and a connected monthly/annual/hierarchy investigation.

## Source and environment

The baseline was the actual `acausal-modelling` working tree at `53d9bfa`, including
its existing staged and unstaged changes. A source archive, source hashes, both Git
diffs, environment data and original timings were captured before editing under
`/private/tmp/rangekeeper-005-baseline`. The Git index was not changed. Changes in
this task are uncommitted; the checkpoint alone does not identify the tested tree.
[Source file hashes](source-files.json) identify the changed implementation,
callers and tests. Null identifies the removed `model/flow.py` path.

[Environment](environment.json): Python 3.10.19, macOS 15.7.9 arm64, 20 reported
logical processors, Polars 1.44.2, NumPy 2.2.6, Pint 0.24.4, Pyomo 6.10.1 and
HiGHS 1.15.1. Hardware model and installed RAM were not available through the
sandbox. The schema environment used the pinned LinkML 1.11.1 tooling and mypy
1.18.2. Black 25.9.0 checked the maintained handwritten changes. Existing unrelated
formatting in the held legacy test file was preserved; its one current-API import
was migrated.

The final wheel is `rangekeeper-0.8.71-py3-none-any.whl`, SHA-256
`5870e152b744602fbf807889de4b9065925c360cba404c46cd5f907ee4a9bcbe`.
It was built in a separate staging directory and verified outside the checkout.
Its Python/JSON runtime files match the final working-tree files byte for byte.
The retired public module is absent. The wheel remains in the baseline directory;
no distribution was published.

## Correctness and acausal acceptance

- Baseline full suite: **1,454 passed, 24 skipped**.
- Final full suite: **1,478 passed, 24 skipped**, in 180.04 seconds. Three held
  live-service tests in `src/tests/legacy/test_api.py` were explicitly excluded.
- Static checks: **215 valid source files**, plus all seven sets of deliberate
  invalid fixtures and their expected rejection counts.
- Python generator: **6 artifacts, 72 classes verified**. C# generated artifacts
  remain current. No persistent fields or document versions changed.
- Native bundle: **16 fixture round trips passed**. All seven schema conformance
  suites passed.
- Installed wheel: lightweight imports, records, Model/Specification APIs, stores,
  graph views, financial calculations, execution, workflows and table/CSV slices
  passed. Stream calculations and the connected acausal hierarchy example ran
  against the same wheel, with pandas absent.
- Current documentation links and routes passed. Notebook kernels and book output
  were not changed or accepted in this phase.

The first broad candidate run found one held legacy test that still imported the
current Flow through its retired path. Its import was migrated; the final full
run above includes that repair. Final signature formatting was verified to retain
the same Python AST. An installed-check reporting issue read dependency versions
from the build environment; the checker now reports the isolated candidate's
actual dependencies.

The new acceptance cases demonstrate:

1. Recorded monthly rents and expenses produce annual totals of 960 and 1,800,
   then a portfolio total of **2,760**.
2. The same equations, reused from the accepted Model revision, can fix the
   portfolio at **2,880** and solve the remaining A rent as **220** and its annual
   total as **1,080**.
3. Unlocking two A rent months yields a combined 320 and an `underdetermined`
   diagnostic; no unique split is claimed.
4. Keeping all original components fixed with the changed total is infeasible
   and publishes no output.
5. Fixed elapsed-weight means and FIRST/LAST equations execute through the
   existing compiler. Unknowns are never removed by numerical SKIP masks.
6. Role editing rejects inherited and policy-controlled roles, preserves
   revisions, and copies recorded amounts only by explicit request.
7. Declaration identity fixtures, source Claims, field presence, absent/unknown/
   zero distinctions, cancellation-sensitive sums, unit conversion, coordinate
   bounds, cache reuse and detached table exports remain covered.

Evidence: [full suite](final-pytest.txt), [typing](typing-final.txt),
[Python generation](schema-check.txt), [C# generation](csharp-check.txt),
[native boundary](native.txt), [conformance](conformance.txt), and
[installed wheel](installed-wheel.txt).

## Performance and memory

These are local, single observations per workload, not statistically estimated
speed guarantees. Baseline and candidate used the same interpreter and declared
input sizes. Some verification work ran concurrently. Arithmetic expectations
were checked independently. Timings exclude neither grouping preparation nor
combined-result construction. Input Flow construction and optional constituent
materialization are reported separately.

| Workload | Baseline resample + combined Flow | Candidate | Candidate with every constituent Flow materialized |
| --- | ---: | ---: | ---: |
| 3 flows × 132 months | 0.145 s | 0.096 s | 0.102 s |
| 100 flows × 120 months | 2.611 s | 0.758 s | 0.930 s |
| 1,000 flows × 360 months | 133.980 s | 21.904 s | 26.662 s |

With all result Flows materialized, the medium and large cases are approximately
**2.8× and 5.0× faster**. The large case also spends 57.265 seconds (baseline) or
56.082 seconds (candidate) constructing its canonical input records. Including
that construction and all output materialization gives approximately **191.245 s
versus 82.743 s**, or **2.3×**. Canonical record storage was retained; those costs
are not hidden or used as a solver-scalability claim.

Repeated aggregation of already resampled lines took 0.641 s versus 0.011 s in
the medium case, and 17.148 s versus 0.023 s in the large case. The candidate
reuses prepared columns. Each public aggregate still receives new Movement IDs.

| Additional workload | Baseline operation | Candidate operation |
| --- | ---: | ---: |
| 100 mixed-frequency/sparse lines | 0.409 s | 0.216 s |
| 100 buildings × 10 contributors × 120 months | 40.177 s | 9.614 s |

Hierarchy timings include contributor selection, resampling, every subtree
aggregate and Flow results. Model/Flow construction is separate: 65.265 s versus
65.775 s. The baseline explicitly composes existing resampling and aggregation
calls because it had no Flow hierarchy factory.

Peak process RSS for the large sequential workload increased from **396 MiB to
513 MiB** (about 30%). The hierarchy case increased from **552 MiB to 558 MiB**.
These cumulative process peaks include input records and prior operations, not
only dataframe buffers. This is the main measured trade-off of retaining prepared
columns. No claim is made that Polars always uses less memory.

A selection from 100 × 120 rows compacted numerical storage from 483,000 to 4,830
bytes and retained 120 metadata rows instead of 12,000. The selected batch also
retained only its 120 coordinates. A Model-backed selection intentionally retains
its pinned canonical Model. See [selection memory](selection-memory.json).

Raw measurements: [baseline](baseline.json), [candidate](candidate.json),
[extra baseline](extra-baseline.json), [extra candidate](extra-candidate.json).
The repeatable drivers are [Stream timings](../../../tools/performance/flux.py)
and [hierarchy/mixed timings](../../../tools/performance/flux_extra.py).

## Scope and code growth

The old public `model/flow.py`, retired calculation enum/keyword paths, dedicated
`financial.reversion` helper, repeated target-period scans and Python cross-flow
reduction implementation were removed or replaced. Frozen declaration fixtures
were not rewritten. There are no compatibility aliases and no new runtime package
dependencies. Flow and Movement remain canonical schema records.

[Line counts](line-counts.json), across affected paths including additions/removals:

| Material | Before | After | Change |
| --- | ---: | ---: | ---: |
| Handwritten runtime | 2,862 | 4,497 | +1,635 |
| Generated artifacts | 4,170 | 4,171 | +1 |
| Tests | 6,414 | 6,853 | +439 |
| Maintained examples | 1,213 | 1,399 | +186 |
| Tools | 1,072 | 1,313 | +241 |
| Documentation (Markdown) | 2,733 | 3,169 | +436 |

Runtime growth supplies capabilities absent from the baseline: collection
coordination and reusable buffers, compact selection, presentation, shared mapping,
passive resampling/hierarchy equations, Flow hierarchy reduction and explicit
Specification role editing. Bulk arithmetic has one backend shared by series,
Stream and hierarchy callers. The numeric risk repair preserves stable sums; it
is not a separate selectable calculation engine. Small intrinsic Flow operations
retain their existing implementation.

The source architecture and immutable contracts permit later backend work without
changing persistent Flow storage. Solver capabilities and limits are unchanged.
Linux, Windows/Rhino, native layout engines missing from this environment, and
live services were not accepted by this run. Those existing external gates remain
explicit. Notebook migration and rendered walkthrough acceptance are next.

## Commands

Run from the repository root with the recorded environments:

```sh
MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/rangekeeper-acausal-mpl PYTHONPATH=src:examples \
  src/.venv/bin/python -m pytest -q --ignore=src/tests/legacy/test_api.py
PYSTOW_HOME=/private/tmp/rk-005-pystow /private/tmp/rk-005-schema/bin/python tools/schema/generate.py --check
PYSTOW_HOME=/private/tmp/rk-005-pystow /private/tmp/rk-005-schema/bin/python tools/schema/generate_csharp.py --check
PYSTOW_HOME=/private/tmp/rk-005-pystow /private/tmp/rk-005-schema/bin/python tools/schema/typecheck.py
.venv/bin/python tools/docs/check.py
PYTHONPATH=src src/.venv/bin/python tools/performance/flux.py --large --output /private/tmp/flux-timings.json
PYTHONPATH=src src/.venv/bin/python tools/performance/flux_extra.py --output /private/tmp/flux-extra.json
```

Native and conformance commands used the pinned schema interpreter plus the
recorded runtime site-packages on `PYTHONPATH`. Installed checks used
`tools/schema/verify_install.py --wheel` with the exact wheel above and all five
runtime/execution/workflow/financial/table interpreter options pointing at
`src/.venv/bin/python`. The isolated wheel checker copies dependencies; it does
not import the checkout's runtime modules.
