# Calculations, Flow and calendar contracts

Known-data calculations consume immutable records and return new records or explicit
results. A Flow records ordered movements with units. It does not declare whether
those movements mean stock, income, rate or balance; the model and chosen operation
define that meaning.

## Flow semantics and explicit operations

A `Movement` has a UUID, optional matching key, magnitude and date or bounded Period. Its date
records a payment or observation; its Period records coverage. Both may be present
and need not coincide. Magnitude `None` is unresolved; zero is an observed amount.
Nonfinite numbers are invalid. Omission and explicit null survive canonical codecs.

`movement.number` returns a finite float or raises for unresolved content.
`movement.coordinate` supplies the alignment coordinate; it does not use the UUID. `movement.resolve(timing=)`
uses the recorded date or an explicit convention for period-only content.
`flow.check(resolved=True)` checks arithmetic readiness and returns the same Flow.
`flow.clean()` removes unresolved movements explicitly; it does not fill them with
zero. These operations have different purposes and never repair content silently.

```python
from datetime import date
from rangekeeper.flow import Flow

flow = Flow.from_events([date(2026, 1, 1)], [100], units="AUD")
assert flow.check(resolved=True).movements[0].number == 100.0
assert flow.scale(2).total().magnitude == 200
```

A Flow owns conversion, scaling, negation, totals, `trim(span)`,
`resample(periods, *, method, ...)`, `integrate`, `multiply`, differences, collapse
and extent. A Stream owns the operations on several Flows: `align`, `trim`,
`resample`, `aggregate`, `sum`, `min` and `max`. `trim` and `resample` take the
same arguments on Flow and Stream. `FlowAggregate` returns the reduced Flow with
its coverage. Join and missing-data policies are explicit. A coordinate absent from one input is distinct from a
movement whose magnitude is unresolved. A requested absent zero stays zero in the
destination unit.

Dimensional compatibility is necessary but does not prove the intended economics.
The caller chooses additive totals, weighted means, integration or compounding.
Recorded Claims survive supported operations; derived results retain their declared
contribution boundaries. See [record methods](records.md).

## Coordinate flows with Stream

`flow.Stream` accepts an ordered name-to-Flow mapping. It retains default
`missing` and `join` policies. Model-backed selections use
`Stream.from_values(model, value_ids, names=None)`. Duplicate source IDs and
ambiguous names are errors. `select(names)` or `select(value_ids=...)` retains
selection order; `merge` requires compatible policies and exact Model revisions.

```python
from rangekeeper.flow import Stream
from rangekeeper.duration import Span, Frequency
from rangekeeper.flow import ResamplingMethod

span = Span.from_duration(
    name="Operations", start=date(2027, 1, 1), frequency=Frequency.YEAR, count=1,
)
monthly = span.periods(Frequency.MONTH)
income = Stream({
    "Rent": Flow.from_periods(monthly, [100] * 12, units="AUD"),
    "Vacancy": Flow.from_periods(monthly, [-20] * 12, units="AUD"),
})
annual = income.resample(span.periods(Frequency.YEAR), method=ResamplingMethod.SUM)
annual.display()
assert annual.sum().movements[0].number == 960
```

`sum`, `min` and `max` return Flow records. `aggregate(method=..., units=...,
missing=..., join=...)` also returns coverage. `trim(span)` keeps whole periods.
Resampling accepts one method or a complete label-to-method mapping. Means require
`MeanWeighting.OBSERVATIONS` or `ELAPSED`; a weighting mapping covers exactly the
mean lines. `stream.coverage` describes the last resampling step; aggregation
coverage is a separate result. Source records remain unchanged.

The private backend prepares compact coordinate and line columns once, retains
immutable identity/evidence metadata, and reuses columns through selection,
trimming, resampling and display. Native Polars operations handle bulk grouping,
unit conversion and masks. Cancellation-sensitive sums use an `math.fsum` repair.
A group gets the repair when the error bound of its native sum,
`n * eps * sum(|x|) / |sum(x)|`, is more than `1e-8`. Groups with no cancellation
stay native below about 45 million rows. Intermediate resampling does not reconstruct
Flow records. Explicit `.flows` access materializes current content.

Known-data operations do not create equations. Use an original Model selection
with `model.formulation.flow.sum(summands=..., total=...)`, and declare temporal
relationships with `flow.resample(sequence=..., resampled=..., method=...)`.
Numerically transformed Streams cannot stand in for original Value references.
Their `source_values` remain available for source inspection. See
[acausal authoring](expressions.md#passive-flow-and-hierarchy-builders).

## Calendar and numerical ownership

`profile.extrapolate(initial=..., periods=..., method=..., rate=...)` extends
an initial Quantity into a Flow. Compound growth starts at exponent zero unless
`origin` is supplied. `profile.distribute(quantity=..., periods=...,
distribution=...)` spreads a total using a Distribution's interval masses and
preserves that total. Explicit `weights=` can replace a distribution. Neither
operation declares equations or selects unknowns. `grow_values` is the numeric
sequence helper used by extrapolation and the market kernels. Profile classes and
`Flow.from_profile` replace these functions
([#298](https://github.com/daniel-fink/rangekeeper/issues/298)).

| Owner | Responsibility |
| --- | --- |
| `duration` | Native Gregorian dates, Period coverage, explicit frequencies and timing |
| `Period.resolve()` | A declared representative date; coverage is valid from construction |
| `Distribution` | Canonical parameters and intrinsic `check`, `sample`, `cdf`, `mass` |
| `profile` | Grow a known Quantity, or distribute a total, over explicit periods |
| `flow.Stream` | Align and combine several Flows with explicit policies |
| `finance.financial` | PV, XNPV, IRR and day counts using PyXIRR |
| `market.dynamics` | Deterministic kernels over supplied shocks or samples |
| `model.formulation` | Build declared equations for forward and inverse investigations |

Dates are calendar values, never implicit timestamps. Periods are half-open:
`[start, end)`. Financial valuation uses actual payment dates; period-only movements
need `PeriodTiming.FIRST`, `PeriodTiming.END` or `PeriodTiming.LAST`. Frequency and elapsed time are
explicit. Currency and time units are not stripped from quantities.

`Distribution.sample(size=..., generator=...)` requires an explicit random
generator. Scenario plans own seed-based stream construction. Distribution algorithms load SciPy only when needed. Financial valuation
uses the `calculations` extra; the valuation operation itself does not import
a dataframe library or SciPy.

## Detached tables and plots

The [table reference](tables.md) owns lossless Flow-to-Polars conversion,
`_present` metadata, detached date projections and textual CSV rules. These
projections do not change the Model. Plot adapters return figures so callers
choose display and storage.

## Movement naming

The current API is `Movement` and `Flow.movements`. Old `Sample`, pandas containers,
free functions for intrinsic Flow operations and old duration namespaces have no
compatibility aliases. Use the [upgrade guide](../guides/upgrading.md) when porting
an older consumer. Schema fields and generated records are described in the
[schema guide](../contributing/schema.md); the [walkthroughs](../guides/walkthroughs.md)
show complete calculations and investigations.

## Movement identity

The [identity contract](identity.md#movement-identity-and-alignment) owns Movement
UUID retention and creation. Coordinate alignment does not use UUIDs. Clone a
Flow before placing an independent copy under a second Value.

## Alignment and reduction

`Stream(flows, join=..., missing=...).align()` returns a Stream whose lines share
coordinates. It keeps the original known-value coverage and the missing policy.
`Stream.aggregate(method=AggregationMethod.SUM, units=...)` shares unit conversion,
Claim collection and coverage calculation, on an aligned or an unaligned Stream.
Each aggregation returns `FlowAggregate(flow, coverage)`.

`AlignmentJoin.EXACT` is the default. `UNION` and `INTERSECTION` are explicit.
Missing choices use `MissingValueHandling`; reducer choices use `AggregationMethod`. Zero filling
applies to absent coordinates; an explicitly unresolved movement remains unresolved.
Skip can reduce a partly known group; an entirely unknown group remains unresolved.
Coverage reports the original known fraction, including after zero filling.

`Flow.multiply`, `Flow.integrate` and `Flow.resample` keep explicit calculation
contracts. `Stream.resample` also reports the coverage of each line.
Financial valuation remains in `finance.financial`, with explicit timing and
PyXIRR conventions. Calendar grids remain in `duration.period`.

## Funding without accounts

Rangekeeper has no account class and no account declaration (#201, decision D2).
Funding is composition: a balance is the `cumulative()` sum of a Flow, and the
equations of the Model relate draws, interest and repayments.
`model.formulation.financial.interest` declares interest on an explicitly selected,
nonnegative principal. Unknown rates and piecewise overdraft branches are
unsupported.

## Calendar choices

`Frequency` owns the ten supported steps. `duration.offset`, `measure`, `align`,
`cover`, `make_period`, `make_periods` and `periods_between` use native dates.
Month offsets default to `MonthRoll.PRESERVE_END`; `CLAMP` is explicit. These rules
are independent of the Period wire-field migration. `DayCount` owns supported
financial year fractions; imported PyXIRR constants remain an adapter detail.
Closed Python API choices require enum members. Wire codecs continue to use text.

## Timing, integration and valuation

`Flow.from_periods` stores coverage only unless `dates=` supplies independent
payment or observation dates. `collapse` requires `on=` or a timing convention
unless the final movement records a date. Trimming keeps whole covered periods
and rejects partial overlap. Resampling groups coverage into a complete target
Period grid and produces period aggregates without payment dates. Keep the
original Flow when individual payment facts are required.

Rate-to-amount conversion needs an exposure. Multiplying `AUD/year` by a
dimensionless factor leaves `AUD/year`; multiplying two rates retains both time
dimensions. `Flow.integrate` accepts explicit exposure Quantities or a `DayCount`
member for bounded periods:

```python
from datetime import date
from rangekeeper.duration import DayCount, Frequency, make_periods
from rangekeeper.flow import Flow

periods = make_periods(date(2026, 1, 1), frequency=Frequency.MONTH, count=3)
rates = Flow.from_periods(periods, (120, 120, 120), units="AUD/year")
amounts = rates.integrate(day_count=DayCount.ACTUAL_365, units="AUD")
assert abs(amounts.total().magnitude - 120 * 90 / 365) < 1e-9
```

The caller selects last for a closing balance, sum for receipts, or mean with
explicit weighting. The library does not infer this from a Flow kind. Bounded
movements crossing target periods must be allocated first. Resampling coverage
counts known observations, not continuous time coverage. Zero filling does not
resolve an explicitly unknown observation.

`calculate_pv` uses a per-observation rate and explicit `first_period` index.
`calculate_xnpv` uses a valuation date and day-count convention; `calculate_irr`
returns one PyXIRR root and its residual. Both require `timing=` for period-only
movements. `IrrResult` contains `rate`, `residual`, `guess` and
`method="pyxirr.xirr"`. A guess is neither a bound nor proof of root uniqueness.
Failed or nonfinite library results raise `ValueError`. An IRR residual greater
than `1e-8 * max(gross_movements, 1)` also fails. This check uses the residual at
the earliest payment, so a distant `valuation_date` does not reject a valid root;
`IrrResult.residual` is the residual at `valuation_date`. Empty Flows have zero XNPV
but no IRR. There is no bounded-solver fallback.
