# Calculations, Flow and calendar contracts

Known-data calculations consume immutable records and return new records or explicit
results. A Flow records ordered movements with units. It does not declare whether
those movements mean stock, income, rate or balance; the model and chosen operation
define that meaning.

## Flow semantics and explicit operations

A `Movement` has an owner-local key, magnitude and date or bounded Period. Its date
records a payment or observation; its Period records coverage. Both may be present
and need not coincide. Magnitude `None` is unresolved; zero is an observed amount.
Nonfinite numbers are invalid. Omission and explicit null survive canonical codecs.

`movement.number` returns a finite float or raises for unresolved content.
`movement.coordinate` supplies the alignment coordinate. `movement.resolve(timing=)`
uses the recorded date or an explicit convention for period-only content.
`flow.check(resolved=True)` checks arithmetic readiness and returns the same Flow.
`flow.clean()` removes unresolved movements explicitly; it does not fill them with
zero. These operations have different purposes and never repair content silently.

```python
from datetime import date
from rangekeeper.model.flow import Flow

flow = Flow.from_events([date(2026, 1, 1)], [100], units="AUD")
assert flow.check(resolved=True).movements[0].number == 100.0
assert flow.scale(2).total().magnitude == 200
```

A Flow owns conversion, scaling, negation, totals, trimming, differences, collapse
and extent. Multi-Flow operations live in `calculations.series`: `align`, `aggregate`,
`multiply`, resampling and integration. `Alignment` owns aligned reduction;
`Aggregation` returns its Flow with contribution metadata. Join and missing-data
policies are explicit. A coordinate absent from one input is distinct from a
movement whose magnitude is unresolved. A requested absent zero stays zero in the
destination unit, including conversion between affine units.

Dimensional compatibility is necessary but does not prove the intended economics.
The caller chooses additive totals, weighted means, integration or compounding.
Recorded Claims survive supported operations; derived results retain their declared
contribution boundaries. See [record methods](RECORD_BOUNDARY.md).

## Calendar and numerical ownership

| Owner | Responsibility |
| --- | --- |
| `duration` | Native Gregorian dates, Period coverage, explicit frequencies and timing |
| `Period.check()` / `.resolve()` | Valid coverage and a declared representative date |
| `Distribution` | Canonical parameters and intrinsic `check`, `sample`, `cdf`, `mass` |
| `calculations.projection` | Project a known Quantity over explicit periods |
| `calculations.series` | Align and combine several Flows with explicit policies |
| `calculations.account.Account.calculate` | Interest, overdraft and balance recurrence |
| `calculations.financial` | PV, XNPV, IRR and day counts using PyXIRR |
| `calculations.dynamics` | Deterministic kernels over supplied shocks or samples |
| `formulations` | Build declared equations for forward and inverse investigations |

Dates are calendar values, never implicit timestamps. Periods are half-open:
`[start, end)`. Financial valuation uses actual payment dates; period-only movements
need `timing="start"`, `"end"` or `"last_day"`. Frequency and elapsed time are
explicit. Currency and time units are not stripped from quantities.

Distribution sampling accepts an explicit random generator or seed according to
its API. Distribution algorithms load SciPy only when needed. Financial valuation
can use the smaller `financial` extra without a dataframe or SciPy import.

## Detached tables and plots

`adapters.polars.to_frame(flow)` and `from_frame(frame, units=...)` preserve
movement fields and their presence. The `_present` column is part of that format.
`dates(flow, timing=...)` returns date and magnitude columns for display; it omits
keys, coverage and Claims. `to_frame(table)` and `to_table(frame)` handle ordinary
Table cells. Table row identity and provenance require separate evidence.

Polars serves dataframe operations. Native records remain the interchange format;
NumPy and SciPy serve numerical kernels. There is no pandas adapter or dependency.
The `tables` extra installs Polars; `calculations` includes it too.
[CSV rules](CONSUMER_MIGRATION.md#tables-and-presentation) are deliberately textual.
Plot adapters return figures so callers choose display and storage.

## Movement naming

The current API is `Movement` and `Flow.movements`. Old `Sample`, pandas containers,
free functions for intrinsic Flow operations and old duration namespaces have no
compatibility aliases. Use the [upgrade guide](LEGACY_UPGRADE_GUIDE.md) when porting
an older consumer. Schema fields and generated records are described in the
[schema guide](../schema/README.md); the [walkthroughs](../walkthrough/README.md)
show complete calculations and investigations.
