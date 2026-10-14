# Retired behaviour and its canonical destination

The frozen ledger records 671 symbols, including fields and private helpers.
This table groups them by behaviour. It does not promise method-for-method
compatibility. The public API deliberately requires explicit units, coordinates,
missingness, random inputs and execution. [ledger.json](ledger.json) retains a
status and destination for every inventoried symbol.

| Retired responsibility | Canonical replacement and intentional change | Acceptance |
|---|---|---|
| `flux.Flow` construction and mutable pandas storage | `model.flow.from_events`, `from_periods`, immutable `Flow`/`Movement`; detached pandas/Polars adapters. Constructors do not sample or run mathematics. | `test_modules`, `test_flow_dates`, `test_flow_operations`, adapter checks |
| `flux.Stream` selection and reduction | Revision-pinned `Stream.from_values/select/merge`; `calculations.series.sum_flows`, `reduce_flows`, `multiply_flows`, `total`. Values retain UUIDs; names are not identities. | `test_modules`, `test_calculations`, installed notebooks |
| Alignment, resampling and time dimensions | `series.align/resample/integrate/convert`; explicit grids, weighting, unit conversions and missing policy. Products preserve dimensions. Partial period overlap fails until explicitly allocated. | `test_flow_operations`, canonical monthly/weekly projection checks |
| Negation, differences, trimming and collapse | `series.negate/difference/trim/clean/collapse`; new detached results, explicit date/timing for collapse. No mutation of stored content. | `test_calculations`, `test_flow_operations` |
| `_legacy_duration` enums, pandas sequences and inclusive spans | `model.duration.Period/Span`, `duration.calendar/period`; day resolution and half-open intervals. Explicit payment timing replaces inferred pandas period meaning. | `test_flow_dates`, `test_modules`, `test_migration_foundations` |
| Distributions and hidden global randomness | Generated `model.distribution` records; `calculations.distribution.sample/calculate_interval_mass` with explicit generator; scenario stream metadata. | Probability mass checks, sampling-before-allocation checks, scenario replay/order checks |
| Extrapolation and projection objects | `calculations.projection.project_values/project/allocate/pad`; explicit integer origin, Period grid and padding. Allocation preserves mass. | Four canonical projection checks, broader calculation tests |
| Financial Flow methods | `calculations.financial.calculate_pv/calculate_xnpv/calculate_irr`; PyXIRR delegates numerical financial algorithms. Governing equations use `formulations.financial`. | `test_financial_library`, temporal/scalar execution and DCF notebook |
| `formula.financial` account calculations | `calculations.account.calculate_account` and `AccountResult`; declared symbolic cases use `formulations.account`. | 18 captured predecessor cases plus independent recurrence and arithmetic tests |
| Market trend, volatility, cyclicality, noise and shock classes | Pure `calculations.dynamics` kernels; `scenarios.components.make_*`, `scenarios.plan.make_plan`, `generate/realize/replay`. Inputs and realised paths are canonical Values. | Three captured cycle paths plus defining equation, fixed-input dynamics, replay and parallel invariance |
| Callback policy | Generated policy records, finite dated rules and explicit controlled assignments through `policies`. Arbitrary callbacks are unsupported. Market paths stay intact. | Strict threshold, information boundary, one sale, horizon fallback, paired-scenario notebook checks |
| Segmentation `Interval`, `Segment` and `Type` | Numerical bounds in `calculations.interval`; domain segment meaning in Entities/Assemblies and property Values; taxonomy ancestry uses canonical classification UUIDs. Mutable standalone segment/type trees are retired. | Canonical interval partition, property/membership and classification checks |
| `format`, `rgba_from_cmap`, `update_class` | Explicit authoring steps and detached adapters. Presentation can use Python formatting, dataframe styling and plotting-library colours. There are no aliases. | No active callers in audit, seven executed notebooks, removed-name guards |
| `space.py`, `tests/models/linear_graph.py` | Comment-only stubs removed. They provided no implemented runtime capability. | Removed-file inventory and import guards |

The synthetic fixture `src/tests/fixtures/numerical/turn3-reference.json` was
captured from checkpoint `305f3ff` before deletion. It records source hashes,
18 account cases and three cycles. It contains no private project data. Its
capture script requires that historical code; tests read the captured data and
never import the retired modules.

The local test total changes from 1,061 to 1,058 passes. The old 29 module tests
become 16 canonical checks, eight dynamics tests become four fixed-input checks,
and 14 retirement checks are added. Four projection checks and all 21 captured
account/cycle checks remain. Existing independent canonical financial, flow,
scenario, policy and execution suites also remain. This consolidates old display
and container tests; it does not count removed tests as passed.

## Consumer placement

- All seven walkthroughs run from the exact candidate wheel in fresh kernels.
  The routine scenario count is visibly four; 2,000 remains selectable.
- Deterministic, probabilistic, flexible and linear financial test models use the
  canonical implementation and pass in the full suite.
- Mandarin and both East Whisman scenarios use a normal Python 3.13 wheel install
  without numerical, dataframe, service or plotting libraries. Builds, strict
  comparisons and project checks pass. Mandarin also runs its review notebook.
- The two documentation examples now import Evidence records from `evidence`
  and `operation` from the root public export. Both execute outside the checkout.
- Old graph/Measure/Speckle regression tests remain attached to the Windows hold.
  Three live predecessor API tests are excluded; exclusion is not acceptance.
- Historical research, original Rhino/GHX inputs, archives and reference branches
  remain unchanged. Unknown downstream code has guidance, not a compatibility claim.
