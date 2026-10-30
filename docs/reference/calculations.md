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
Alignment matches Movements by their coordinate: the Period and the date, or the
event date and key. It does not use the UUID. `movement.resolve(timing=)`
uses the recorded date or an explicit convention for period-only content.
`flow.require_resolved()` checks arithmetic readiness and returns the same Flow.
`flow.clean()` removes unresolved movements explicitly; it does not fill them with
zero. These operations have different purposes and never repair content silently.

```python
from datetime import date
from rangekeeper.flow import Flow

flow = Flow.from_events(dates=[date(2026, 1, 1)], magnitudes=[100], units="AUD")
assert flow.require_resolved().movements[0].number == 100.0
assert flow.scale(2).total().magnitude == 200
```

A Flow owns conversion, scaling, negation, totals, `at(on=)`, `shift(by=)`,
`trim(span=)`, `resample(periods= or frequency=, method=, ...)`,
`split(periods= or frequency=)`, `integrate`, `multiply`, `cumulative()`,
`diff()`, `since(on=)`, `until(on=)`, `first()`, `last()`, `min()`, `max()`,
collapse and extent. A Stream owns the operations on several Flows: `align`, `trim`,
`resample`, `split`, `aggregate`, `sum`, `min` and `max`. `trim`, `resample` and
`split` take the same arguments on Flow and Stream.
`FlowAggregate` returns the reduced Flow with its coverage. Join and
missing-data policies are explicit. A coordinate absent from one input is
distinct from a movement whose magnitude is unresolved. A requested absent zero
stays zero in the destination unit.

### Make and read a Flow

`Flow(amounts=, units=None)` takes a mapping of Periods, or of dates, to
amounts: numbers, currency amounts, Quantities or Quantity text. With Quantities,
the units come from them and other compatible units convert. `Flow(units=,
movements=)`, `from_periods` and `from_events` remain. Periods and Spans are
hashable, so they can key the mapping.

```python
from datetime import date

import rangekeeper as rk

years = rk.duration.Span(start=date(2001, 1, 1), length="11 years").periods(
    frequency=rk.duration.Frequency.YEAR
)
pgi = rk.flow.Flow(amounts={years[0]: 100, years[1]: 102}, units="USD")
purchase = rk.flow.Flow(amounts={date(2001, 1, 1): rk.Quantity(text="-950 USD")})
pgi.at(on=date(2002, 6, 30))  # Quantity(text='102 USD')
```

`at(on=)` returns the amount of the Period that contains the date, or of the
event on that date, as a Quantity. A date with no amount raises
`MissingReferenceError`, several events on it raise `AmbiguousReferenceError`, and
an unresolved amount raises `NumericalError`.

### Flow arithmetic

| Operation | Result |
| --- | --- |
| `2 * flow`, `flow * 2`, `flow / 2` | Each amount scaled; the same units |
| `flow * quantity`, `quantity * flow`, `flow / quantity` | Each amount combined with the Quantity, with the [Quantity rules](units.md#quantities): `nacf / Quantity(text="5 %")` stays in `USD` |
| `a + b`, `a - b` | Amounts on matching coordinates added; a coordinate that only one Flow has keeps its amount, because the other Flow has nothing there. Compatible units; the result has the units of `a`. Dated and period Flows do not mix; `Stream.sum` dates the period amounts |
| `a * b`, `a / b` | Exact matching coordinates only; the units combine |
| `-flow` | `negate()` |

An unresolved amount gives an unresolved result. Each result has new Movement
UUIDs. Currency amounts use float64 inside and `to_amount` for each result
([ADR-023](../decisions/023-decimal-money.md)).

### Shift, trim and resample

`shift(by=)` moves each amount by whole Periods and keeps the Periods: with
`by=-1`, each Period holds the next Period's amount, and the last Period is
unresolved. Amounts that move past the ends are left out. The Periods must be
gap-free; a dated Flow does not shift. `trim(span=)` takes a Period or a Span.

`split(frequency=)` and `resample(frequency=, method=)` make the target Periods
from the start of the first Period to the end of the last; they must fit
exactly. `periods=` gives the target Periods directly.

`split` divides each amount equally over the shorter Periods inside its Period,
and the last part takes the remainder, so the parts add up to the amount. The
target Periods must partition each Period. `resample` reduces the movements
inside each longer Period with one `ResampleMethod`: `SUM`, `FIRST`, `LAST`,
`MIN`, `MAX`, `MEAN` or `ELAPSED_MEAN`. `MEAN` gives each movement the same
weight; `ELAPSED_MEAN` weights each movement by the days of its Period.
`missing=` treats a target Period with no amount or with an unresolved amount.

```python
quarters = pgi.split(frequency=rk.duration.Frequency.QUARTER)
assert quarters.resample(
    frequency=rk.duration.Frequency.YEAR, method=rk.flow.ResampleMethod.SUM
) == pgi
```

### Running totals, date masks and extremes

These methods are the operations on one Flow that equations use, such as
`loan_draws = loan_principal.diff()` (D2, D21):

| Method | Result |
| --- | --- |
| `cumulative()` | A Flow on the same coordinates: each amount is the sum of the amounts up to it. The last amount equals `total()` |
| `diff()` | A Flow on the same coordinates: each amount less the amount before it, and the first amount less zero. It reverses `cumulative()`: `flow.cumulative().diff() == flow`, to floating-point precision |
| `since(on=)` | A Flow on the same coordinates, with zero before a date: a Period that ends on or before `on`, or an event before it, holds zero |
| `until(on=)` | A Flow on the same coordinates, with zero after a date: a Period that starts after `on`, or an event after it, holds zero |
| `first()`, `last()` | The amount of the first or the last Movement, a Quantity |
| `min()`, `max()` | The smallest or the largest amount, a Quantity |

`since` and `until` keep the Period that contains `on`, as `at(on=)` finds it,
and they give zero whatever the amount was, also an unresolved one. `on` is a
date value: `NEVER` is later than every date, so `since(on=NEVER)` is zero
everywhere and `until(on=NEVER)` keeps every amount. In `cumulative` and `diff`,
an unresolved amount makes its own result unresolved, and also each later total,
or the next difference. Each running total is the exactly rounded sum of its
amounts, as `math.fsum` gives.

`first` and `last` read one Movement; `min` and `max` read every Movement, so an
unresolved amount anywhere raises `NumericalError` (use `clean()` first to leave
the unresolved Movements out). An empty Flow raises `ContractError` with
`Code.CONTRACT`. A currency amount keeps its exact `Decimal`.

```python
from datetime import date

import rangekeeper as rk

years = rk.duration.Periods(
    start=date(2027, 1, 1), frequency=rk.duration.Frequency.YEAR, count=4
)
net_cash_flow = rk.flow.Flow(
    amounts={years[0]: -60e6, years[1]: -30e6, years[2]: 10e6, years[3]: 100e6},
    units="AUD",
)
funding_need = -net_cash_flow.cumulative()  # 60e6, 90e6, 80e6, -20e6 AUD
funding_need.max()  # Quantity(text='90000000 AUD')
funding_need.diff() == -net_cash_flow  # True
net_cash_flow.since(on=date(2028, 6, 30))  # 0, -30e6, 10e6, 100e6 AUD
```

Dimensional compatibility is necessary but does not prove the intended economics.
The caller chooses additive totals, weighted means, integration or compounding.
Recorded Claims survive supported operations; derived results retain their declared
contribution boundaries. See [record methods](records.md).

## Equality

Flows and Quantities compare by value. Two Flows are equal when they have the
same units and, in order, the same coordinates, matching keys and amounts.
Movement UUIDs and Claims are identity and evidence, not value, so `flow.clone()
== flow`. `equivalent()` and `to_data()` compare the records. Floating-point
results that took different paths can differ in the last digit; compare them
with `rangekeeper.quantity.isclose`, which also takes two Flows
([units](units.md#equality-and-isclose)).

## Coordinate flows with Stream

`flow.Stream(flows=)` takes an ordered name-to-Flow mapping. It retains default
`missing` and `join` policies: `MissingValueHandling.ERROR` and
`AlignmentJoin.UNION`. Model-backed selections use
`Stream.from_values(model=, value_ids=, names=None)`. Duplicate source IDs and
ambiguous names are errors. `stream[name]` returns one Flow.
`select("a", "b")` and `select_values(ids)` keep the selection order.
`with_policy(missing=, join=)` returns the Stream with another policy; the
policies live on the Stream, and `align`, `resample` and `aggregate` read them.
`with_flows(flows=)` returns a Stream with more named Flows; a name that is
already there gets the new Flow in its place. `merge` requires compatible
policies and exact Model revisions.

```python
from rangekeeper.flow import Stream
from rangekeeper.duration import Span, Frequency
from rangekeeper.flow import ResampleMethod

span = Span(name="Operations", start=date(2027, 1, 1), length="1 year")
monthly = span.periods(frequency=Frequency.MONTH)
income = Stream(
    flows={
        "Rent": Flow.from_periods(periods=monthly, magnitudes=[100] * 12, units="AUD"),
        "Vacancy": Flow.from_periods(periods=monthly, magnitudes=[-20] * 12, units="AUD"),
    }
)
annual = income.resample(
    periods=span.periods(frequency=Frequency.YEAR), method=ResampleMethod.SUM
)
annual.display()
assert annual.sum().movements[0].number == 960
```

`sum`, `min` and `max` return Flow records. `aggregate(method=..., units=...)`
also returns coverage. A coordinate that a line does not have adds
nothing; only an unresolved amount follows the Stream's `missing` policy. When
the lines mix dated and period Flows, each period amount is dated at its
recorded date, or else at the end of its Period, the convention of `rk.finance`.
`dated(timing=)` dates the period amounts by another `PeriodTiming` first, for
example `stream.dated(timing=PeriodTiming.FIRST).sum()`. `trim(span=)` keeps
whole periods.
`resample` accepts one method for every line, or a mapping from each name to its
method. `split` divides the amounts of every line. `stream.coverage` describes
the last resampling step; aggregation
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
| `finance` | `pv`, `npv`, `irr` and `payment` with units; `finance.financial` has the older PV, XNPV and IRR functions and the PyXIRR day counts |
| `market.dynamics` | Deterministic kernels over supplied shocks or samples |
| `model.formulation` | Build declared equations for forward and inverse investigations |

Dates are calendar values, never implicit timestamps. Periods are half-open:
`[start, end)`. Financial valuation uses actual payment dates; period-only movements
need `PeriodTiming.FIRST`, `PeriodTiming.END` or `PeriodTiming.LAST`. Frequency and elapsed time are
explicit. Currency and time units are not stripped from quantities.

`Distribution.sample(size=..., generator=...)` requires an explicit
`numpy.random.Generator`. Scenario plans own seed-based stream construction. Distribution algorithms load SciPy only when needed. Financial valuation
uses the `calculations` extra; the valuation operation itself does not import
a dataframe library or SciPy.

## Detached tables and plots

The [table reference](tables.md) owns lossless Flow-to-Polars conversion,
`_present` metadata, detached date projections and textual CSV rules. These
projections do not change the Model. The library has no plot adapters: they
moved to the [walkthrough helpers](../../examples/walkthrough/helpers/README.md)
in 1.0.0a1. The helpers return figures, so callers choose display and storage.

## Movement naming

The current API is `Movement` and `Flow.movements`. Old `Sample`, pandas containers,
free functions for intrinsic Flow operations and old duration namespaces have no
compatibility aliases. Use the [upgrade guide](../guides/upgrading.md) when porting
an older consumer. Schema fields and generated records are described in the
[schema guide](../contributing/schema.md); the [walkthroughs](../guides/walkthroughs.md)
show complete calculations and investigations.

## Movement identity

The [identity contract](identity.md#one-rule-for-transforms) owns Movement
UUID retention and creation: a transform keeps the ID of each Movement that it
selects or converts, and gives a fresh ID to each Movement that it calculates.
Coordinate alignment does not use UUIDs. Clone a Flow before placing an
independent copy under a second Value.

## Alignment and reduction

`Stream(flows=flows, join=..., missing=...).align()` returns a Stream whose lines share
coordinates. It keeps the original known-value coverage and the missing policy.
`Stream.aggregate(method=AggregationMethod.SUM, units=...)` shares unit conversion,
Claim collection and coverage calculation, on an aligned or an unaligned Stream.
Each aggregation returns `FlowAggregate(flow=, coverage=)`.

`AlignmentJoin.UNION` is the default. `EXACT` and `INTERSECTION` are explicit.
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

## Profiles

A profile says how an amount develops over Periods (D12). `rangekeeper.profile`
has two kinds:

| Profile | Kind | Factor for each Period |
| --- | --- | --- |
| `Constant(start=None, every=None)` | Growth, `initial=` | 1 |
| `Linear(rate=, base=None, start=None, every=None)` | Growth, `initial=` | `1 + rate * t` |
| `Compounding(rate=, base=None, start=None, every=None)` | Growth, `initial=` | `(1 + rate) ** t` |
| `Uniform(start=None, length=None)` | Distribution, `total=` | `1 / n` |
| `SCurve(distribution=None, start=None, length=None)` | Distribution, `total=` | The increase of an S-shaped cumulative distribution over each Period's equal part: by default `3x² - 2x³` (Beta(2, 2)), or the `Distribution` given, such as `Distribution.pert()` |

`rate` is a rate per year, a Quantity or its text, such as `"2 % pa"`. `t` is the
years from `base` to the start of each Period: a start on the same day of the
month counts whole months, otherwise days at 365.25 a year. `base` is the date of
the initial amount, by default the start of the first Period, so a Period before
it has a negative `t`.

The other options say when the amount occurs. They are checked when the profile
is made:

| Option | Profiles | Meaning |
| --- | --- | --- |
| `start=` | All | A date value. A growth profile is zero in each Period that ends on or before it; the Period that contains it holds the amount. A distribution starts its window on it. `NEVER` gives zero everywhere |
| `every=` | Growth | A whole length, such as `"5 years"`. The amount occurs on `start`, by default the start of the first Period, and once each `every` after it, in the Period that contains each date. Two dates in one Period give twice the amount |
| `length=` | Distribution | A whole length. The window of the shares ends `length` after its start, by default at the end of the last Period |

A distribution divides the total over the `n` Periods of its window, and the
Periods outside it hold zero. The window must cover whole Periods and lie inside
the Periods: a window that crosses a Period raises `rk.duration.AlignmentError`
with `Code.ALIGNMENT_CROSSES`, and one that runs past the Periods raises it with
`Code.ALIGNMENT_PARTIAL`, so no part of the total is lost.

`Flow.from_profile(profile=, periods=, initial= or total=)` makes the Flow. A
growth profile takes `initial=`; with no `base` or `start`, the first Period
holds it. A distribution profile takes `total=`; the last Period with a share
takes the remainder, so the amounts add up to the total. With `start=NEVER` it
has no share, and every amount is zero: the payments do not happen. A profile
refuses the other keyword, so a total is never compounded by mistake. The amount
gives the Flow its units.

```python
growth = rk.profile.Compounding(rate="2 % pa")
pgi = rk.flow.Flow.from_profile(profile=growth, periods=years, initial="100 USD")
fees = rk.flow.Flow.from_profile(
    profile=rk.profile.SCurve(), periods=build, total="3e6 AUD"
)
# Lesson 03: rent grows from the first Period and starts at the opening, renewals
# come every five years after it, and the works divide over two years.
rent = rk.profile.Compounding(rate="3 % pa", start=date(2030, 1, 1))
renewals = rk.profile.Compounding(
    rate="3.5 % pa", start=date(2035, 1, 1), every="5 years"
)
works = rk.profile.Uniform(start=date(2028, 1, 1), length="2 years")
```

In equation text, each profile is a function with the same options:
`rx.profile.compounding(initial=, rate=, start=, every=, base=)` and
`rx.profile.uniform(total=, start=, length=)` (see the
[proposed cells](../../examples/walkthrough/proposed/README.md#equation-strings)).

A new profile is a class whose instances have `takes` (`"initial"` or `"total"`)
and `factors(*, periods)`. Register it in `rangekeeper.profile.profiles`
([extensions](extensions.md)).

## Spans and Periods

A `Span` is a named half-open range of time. Give its end, or a length: a whole
number of days, weeks, months, quarters or years, as a Quantity or its text.
`extend(by=)` returns a Span with the same start, a later end and no name.

`Span.periods(frequency=, include_partial=False, month_roll=PRESERVE_END)` returns a
`Periods`: an ordered, gap-free sequence of Periods with one `Frequency`. Make
one directly with `Periods(start=, frequency=, count=, month_roll=PRESERVE_END)`.

```python
from datetime import date

import rangekeeper as rk

holding = rk.duration.Span(start=date(2001, 1, 1), length="10 years", name="Holding")
years = holding.extend(by="1 year").periods(frequency=rk.duration.Frequency.YEAR)
len(years), years[-1], years.start, years.end, years.span
years.trim(span=holding)  # the first 10 Periods; a partial overlap raises
years.extend(count=2)  # two more steps from the same anchor
years.containing(on=date(2005, 6, 30))  # the Period of 2005
```

`Periods` is a sequence: `len`, iteration and indexing work, and a slice with
step one is a `Periods`. Two `Periods` are equal when they have the same
frequency and the same Periods. Each Period is a calendar step from the first
anchor, so `extend` keeps a month-end anchor. Only a Span partition with
`include_partial=True` ends with a partial Period, and it cannot extend.
`containing(on=)` raises `MissingReferenceError` for a date outside.

`rk.duration.AlignmentError` is a `ContractError` for Periods that do not
align. `trim` raises it with `Code.ALIGNMENT_CROSSES` when the Span crosses a
Period; `Span.periods` without `include_partial=True` and `extend` after a
partial Period raise it with `Code.ALIGNMENT_PARTIAL`. Its `values` give the
Periods as ISO intervals, such as `"2026-01-01/2027-01-01"`. A negative count,
a slice with a step and an empty `cover` raise `ContractError`; a count that is
not an `int` raises `TypeError`. A step outside the years 1 to 9999 raises
`ContractError`.

## Calendar grids

A grid divides the calendar into Periods of one `Frequency`.
`rk.duration.containing_period(on=, grid=)` returns the Period of a grid that
contains a date. Each kind of grid takes only the choices that apply to it, so a
choice that does not apply cannot be given:

| Grid | Frequencies | Choices |
| --- | --- | --- |
| `DayGrid()` | `DAY` | None |
| `WeekGrid(starts=)` | `WEEK` | The first weekday, a `calendar.Day`; `Day.MONDAY` by default |
| `MonthGrid(frequency=, year_starts=)` | `MONTH`, `QUARTER`, `HALFYEAR`, `YEAR` | The first month of the year, a `calendar.Month`; `Month.JANUARY` by default. Months are the same for each start |
| `MultiYearGrid(frequency=, origin=)` | `BIENNIUM`, `QUINQUENNIUM`, `DECADE` | An origin on the first day of a month, which also gives the first month of the year. The grid continues on both sides of it |

```python
from calendar import Month
from datetime import date

import rangekeeper as rk

fiscal = rk.duration.MonthGrid(
    frequency=rk.duration.Frequency.YEAR, year_starts=Month.JULY
)
rk.duration.containing_period(on=date(2026, 3, 3), grid=fiscal)
# Period(start='2025-07-01', end='2026-07-01')
```

`calendar.Day` and `calendar.Month` are the standard library enums. A grid is a
frozen value, and it checks its choices when it is made: a frequency of another
kind of grid, or an origin that is not the first day of a month, raises
`ContractError`. `rk.duration.Grid` is the union of the four grid types.

## Dates and NEVER

A date value is a calendar date or `rk.duration.NEVER`. NEVER means the event
does not happen; `None` means missing. NEVER is the one member of the
`rk.duration.Never` enum. `rk.duration.shift(on=, by=)` returns the date a whole
length later, or earlier for a negative length:

```python
from datetime import date

import rangekeeper as rk

rk.duration.shift(on=date(2027, 1, 1), by="1 year")  # date(2028, 1, 1)
rk.duration.shift(on=date(2027, 1, 31), by="1 month")  # date(2027, 2, 28)
rk.duration.shift(on=date(2027, 1, 1), by="-3 months")  # date(2026, 10, 1)
rk.duration.shift(on=rk.duration.NEVER, by="1 year")  # rk.duration.NEVER
```

A length is a whole number of days, weeks, months, quarters or years; other units
or a fraction raise `UnitError`. Month steps use `MonthRoll.PRESERVE_END`. NEVER
equals NEVER and is later than every date. Date Values and date Expressions use
the same rules ([expressions](expressions.md#dates-and-never)).

## Calendar choices

`Frequency` owns the nine supported steps, from a day to a decade. There is no
fortnight step: offset by `Frequency.WEEK` with `count=2`, or give 14-day
Periods explicitly. `Period`, `Span`, `Periods`, `offset`, `count_steps`,
`containing_period` and the grids, and `cover` use native dates. `shift(on=,
by=)` moves a date value, which can be `NEVER`, by a length; `offset(value=,
frequency=, count=, month_roll=)` moves a date by whole steps of a `Frequency`,
with an explicit `MonthRoll`.
Month offsets default to `MonthRoll.PRESERVE_END`; `CLAMP` is explicit. These rules
are independent of the Period wire-field migration. `DayCount` owns supported
financial year fractions; imported PyXIRR constants remain an adapter detail.
Closed Python API choices require enum members. Wire codecs continue to use text.

## Timing, integration and valuation

`Flow.from_periods` stores coverage only. To record independent payment or
observation dates, make the `Movement` records with a `period` and a `date`.
`collapse(on=)` takes a date or a `PeriodTiming`; without it, the final movement
must record a date. `total` and `collapse` take every `MissingValueHandling`:
`ZERO` adds the known amounts and gives zero when no amount is known. Trimming keeps whole covered periods
and rejects partial overlap. Resampling groups coverage into a complete target
Period grid and produces period aggregates without payment dates. Keep the
original Flow when individual payment facts are required.

Rate-to-amount conversion needs an exposure. Multiplying `AUD/year` by a
dimensionless factor leaves `AUD/year`; multiplying two rates retains both time
dimensions. `Flow.integrate(exposures=)` takes one exposure Quantity for each
Movement, and `Flow.integrate_time(day_count=)` uses the year fraction of each
bounded Period:

```python
from datetime import date
from rangekeeper.duration import DayCount, Frequency, Periods
from rangekeeper.flow import Flow

periods = Periods(start=date(2026, 1, 1), frequency=Frequency.MONTH, count=3)
rates = Flow.from_periods(periods=periods, magnitudes=(120, 120, 120), units="AUD/year")
amounts = rates.integrate_time(day_count=DayCount.ACTUAL_365, units="AUD")
assert abs(amounts.total().magnitude - 120 * 90 / 365) < 1e-9
```

The caller selects last for a closing balance, sum for receipts, or a mean
with its weighting (`MEAN` or `ELAPSED_MEAN`). The library does not infer this from a Flow kind. Bounded
movements crossing target periods must be allocated first. Resampling coverage
counts known observations, not continuous time coverage. Zero filling does not
resolve an explicitly unknown observation.

### Present value, NPV, IRR and payments

`rangekeeper.finance` calculates on known Flows and Quantities, with units:

| Function | Result |
| --- | --- |
| `pv(flow=, rate=, on=, day_count=ACTUAL_ACTUAL, timing=END)` | A Flow on the same coordinates: each amount divided by `(1 + rate) ** t`, where `t` is the years from `on` to its date |
| `npv(flow=, rate=, on=, ...)` | The total of `pv`, a Quantity. An empty Flow has zero value |
| `irr(flow=, guess=None, ...)` | The rate whose NPV is zero, in `% pa` |
| `payment(principal=, rate=, term=, frequency=)` | The level payment per period that repays a loan, like a spreadsheet's PMT, in `AUD per month` and so on |

Rates are effective rates per year, as Quantities or their text: `"7 % pa"`.
An amount's date is its recorded date, or else its Period's date by `timing`:
by default the end of the Period, so year 1 of a yearly Flow is discounted once.
The default day count is actual/actual (ISDA), so a calendar year is exactly
one year, also in a leap year. PyXIRR finds the IRR root; a `guess` is a starting
point, not a bound. `irr` needs amounts of both signs on at least two dates, and
the NPV at the root must be at most `1e-8` of the gross amounts; otherwise it
raises `NumericalError`. `pv`, `npv` and `irr` discount the same way, so a price
equal to the NPV earns the discount rate.

`payment` divides a nominal yearly rate over the periods of a year (`"6 % pa"`
monthly is 0.5 % a month) and pays at the end of each period. `term` is a whole
number of periods, such as `"20 years"`. There is no mortgage-constant helper
(D19): the constant is the payment per year on one unit of loan.

```python
value = rk.finance.npv(flow=cash_flows, rate="7 % pa", on=date(2001, 1, 1))
monthly = rk.finance.payment(
    principal="1 AUD", rate="6 % pa", term="20 years", frequency=rk.duration.Frequency.MONTH
)
(monthly / rk.Quantity(text="1 AUD")).to(units="% pa")  # the mortgage constant
```

### The financial module

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
