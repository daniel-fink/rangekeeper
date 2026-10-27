# Lesson 01: Basic discounted cash flow (proposed cells)

Issue: [#203](https://github.com/daniel-fink/rangekeeper/issues/203). Plan:
[ADR-020 §01](../../../docs/decisions/020-walkthrough-plan-v2.md#01-basic-discounted-cash-flow).
API conventions and the gap list: [README](README.md).

These are the cells that a reader types. They use the 1.0 API, not today's code. The
rule check at the end names each gap from the [gap list](README.md#gap-list).

## Goals box

> **Question.** What is this income stream worth?
>
> **You will learn to:**
>
> 1. make dated Flows with units over yearly periods;
> 2. describe growth with a profile, and make a Flow from it;
> 3. combine lines in a Stream, resample them and trim them to a holding span;
> 4. estimate the terminal value from the next year's net cash flow and an exit cap rate;
> 5. calculate present value, NPV and IRR on one date basis.
>
> **Before you start.** No earlier lesson. You know a spreadsheet DCF.
>
> **Time.** 45 minutes core, 15 minutes optional.
>
> **Not in this lesson.** Models, equations and solves (lesson 02). Market
> uncertainty (lesson 04). This lesson uses known data only.
>
> **Source.** Table 1.1 in de Neufville and Geltner (2018), chapter 1, used with the
> publisher's permission and with attribution. The numbers are the book's small
> example, not the property of lessons 02–07.

## 1. Set up

Narrative: one import. The lesson also uses `datetime` for dates.

```python
# cell 1
from datetime import date

import rangekeeper as rk
```

## 2. Amounts with units

Narrative: a Quantity is a number with units. Make one from text, or from a number
and a unit string. Rangekeeper checks units in every operation, so an annual rent
cannot be added to a monthly rent by mistake. `pa` means per annum. `%` is a
dimensionless ratio, so a rate per year, such as a growth or discount rate, is
`% pa`. `per` divides, as in `"750 AUD per sqm pa"`.

```python
# cell 2
rent = rk.Quantity(text="1200 USD pa")
rent.to(units="USD per month")
```

```python
# cell 3
rate = rk.Quantity(text="2 % pa")
rate * rk.Quantity(text="1 year")  # 0.02, a dimensionless ratio
```

> **Under the hood.** `rk.Quantity("5 %")` and `rk.Quantity(0.05, "ratio")` make the
> same Quantity. Most functions also accept the text directly, for example
> `rate="2 % pa"`. The `rk.quantity` namespace holds the unit system and its
> registry. The registry is curated: an unknown or misspelt unit fails with a
> suggestion. `"pa"` never becomes a picoyear ([ADR-016](../../../docs/decisions/016-safety-defaults.md)).

## 3. Time: spans and periods

Narrative: the holding period is 10 years from 1 January 2001. The forecast needs one
more year, because the buyer at the end of year 10 pays for year 11's income. A Span
is half-open: it includes its start and excludes its end. A Frequency is the calendar
step: type `rk.duration.Frequency.` and press Tab to see them all. Name the one you
use, and use the name after that.

```python
# cell 4
holding = rk.duration.Span.years(start=date(2001, 1, 1), count=10, name="Holding")
forecast = holding.extend(years=1)
yearly = rk.duration.Frequency.YEAR
years = forecast.periods(frequency=yearly)
years  # 11 Periods, 2001 to 2011
```

## 4. A Flow, by hand once

Narrative: a Flow is an ordered series of amounts in one unit, one for each Period or
date. Make the first two years of potential gross income by hand.

```python
# cell 5
first_two = rk.flow.Flow(amounts={years[0]: 100, years[1]: 102}, units="USD")
first_two.display()
```

## 5. Growth

Narrative. **Predict:** what is the potential gross income in 2010, after nine years
of 2 % growth? Then let the library do the compounding. A profile says how an amount
develops over Periods. State it once, as a spreadsheet states a growth row, and use
it for every line that grows the same way. With a growth profile, the first Period
holds the initial amount.

```python
# cell 6
growth = rk.profile.Compounding(rate=rate)
pgi = rk.flow.Flow.from_profile(profile=growth, periods=years, initial="100 USD")
pgi.display()
```

```python
# cell 7
pgi.at(on=date(2010, 1, 1))  # the amount of the Period that contains this date
```

> **Finance note.** Potential gross income (PGI) is the income if all the space is
> let at the market rent.

> **Under the hood.** Profiles live in `rk.profile`. Growth profiles (`Constant`,
> `Linear`, `Compounding`) start from an `initial=` amount. Distribution profiles
> (`Uniform`, `SCurve`) divide a `total=` amount over the Periods. A profile refuses
> the wrong keyword, so a total is never compounded by mistake.

## 6. Lines of the pro forma

Narrative: each operating line is a fraction of PGI. Multiply a Flow by a number to
scale it. Name the lines in a Stream, and add them period by period with `sum()`.

```python
# cell 8
operations = rk.flow.Stream(
    flows={
        "PGI": pgi,
        "Vacancy": -0.05 * pgi,
        "OPEX": -0.35 * pgi,
    }
)
noi = operations.sum()
noi.display()
```

```python
# cell 9
capex = -0.10 * pgi
nacf = noi + capex  # net annual cash flow
```

> **Finance note.** Effective gross income (EGI) is PGI less vacancy. Net operating
> income (NOI) is EGI less operating expenses. Net annual cash flow (NACF) also
> subtracts capital expenditure, which keeps the building competitive.

## 7. The terminal value

Narrative: at the end of year 10 the owner sells. A buyer pays for the income from
year 11 onwards. A common estimate divides year 11's net cash flow by an exit cap
rate. Do it once by hand. Then do it for every year with two Flow operations: shift
each year's next amount back by one period, and divide by the rate. The result is the
sale price at the end of each year. **Predict:** why is the last year empty? Keep the
year of the sale.

```python
# cell 10
exit_cap_rate = rk.Quantity(text="5 %")
nacf.at(on=date(2011, 1, 1)) / exit_cap_rate  # the price at the end of year 10, by hand
```

```python
# cell 11
# each year: next year's NACF / cap rate
exit_values = nacf.shift(by=-1) / exit_cap_rate
exit_values.display()
```

```python
# cell 12
sale_year = holding.periods(frequency=yearly)[-1]
terminal_value = exit_values.trim(span=sale_year)
assert terminal_value.total() == nacf.at(on=date(2011, 1, 1)) / exit_cap_rate
```

> **Finance note.** The terminal value has other names: the reversion (in US texts,
> including Table 1.1 and Geltner et al.), the exit value, the residual value or the
> sale price. Some analysts capitalise NOI in place of NACF. Here the choice is
> visible in one line, so you can change it.

## 8. Trim to the holding span

Narrative: the forecast has 11 years, but the owner holds for 10. `with_flows` gives
a new Stream with more named Flows; a name that is already in the Stream gets the new
Flow. Trim the table to the holding span and compare it with Table 1.1.

```python
# cell 13
table = operations.with_flows(
    flows={"NOI": noi, "CAPEX": capex, "NACF": nacf, "Terminal value": terminal_value}
)
table = table.trim(span=holding)
table.display()  # compare with Table 1.1
```

```python
# cell 14
cash_flows = table.select("NACF", "Terminal value").sum()
```

## 9. Resample

Narrative: rent is paid quarterly. Split each year into quarters, then add the
quarters back into years. The round trip gives the same Flow.

```python
# cell 15
by_quarter = pgi.resample(
    frequency=rk.duration.Frequency.QUARTER, method=rk.flow.ResampleMethod.SPLIT
)
assert by_quarter.resample(frequency=yearly, method=rk.flow.ResampleMethod.SUM) == pgi
```

## 10. Present value, by hand once

Narrative. **Predict:** which year contributes the most present value? Discount
year 1 by hand. Payments come at the end of each year, so year 1 is discounted once.
Then calculate the whole column.

```python
# cell 16
cash_flows.at(on=date(2001, 1, 1)) / 1.07
```

```python
# cell 17
discount_rate = rk.Quantity(text="7 % pa")
present_values = rk.finance.pv(flow=cash_flows, rate=discount_rate, on=holding.start)
present_values.display()
```

## 11. NPV and IRR on one date basis

Narrative: the value of the stream is the sum of its present values. If an investor
pays exactly that value on 1 January 2001, the investment earns exactly the discount
rate. This shows that NPV and IRR use the same dates.

```python
# cell 18
value = rk.finance.npv(flow=cash_flows, rate=discount_rate, on=holding.start)
value
```

```python
# cell 19
purchase = rk.flow.Flow(amounts={holding.start: -value})
investment = rk.flow.Stream(
    flows={"Purchase": purchase, "Cash flows": cash_flows}
).sum()
rk.finance.irr(flow=investment)  # 7 % pa
```

## 12. Change one input

Narrative. **Predict:** if the exit cap rate rises from 5 % to 6 %, how much value
does the owner lose? Change one input, then explain the result.

```python
# cell 20
exit_6 = (nacf.shift(by=-1) / rk.Quantity(text="6 %")).trim(span=sale_year)
flows_6 = (
    table.with_flows(flows={"Terminal value": exit_6})
    .select("NACF", "Terminal value")
    .sum()
)
rk.finance.npv(flow=flows_6, rate=discount_rate, on=holding.start) - value
```

## Exercises

**Try it 1: faster growth.** Change PGI growth to 3 % pa. Which lines change, and
by how much does the value change?

```python
# solution
growth_3 = rk.profile.Compounding(rate="3 % pa")
pgi_3 = rk.flow.Flow.from_profile(profile=growth_3, periods=years, initial="100 USD")
nacf_3 = 0.95 * pgi_3 - 0.35 * pgi_3 - 0.10 * pgi_3
terminal_3 = (nacf_3.shift(by=-1) / exit_cap_rate).trim(span=sale_year)
flows_3 = rk.flow.Stream(flows={"NACF": nacf_3, "Terminal value": terminal_3})
cash_3 = flows_3.trim(span=holding).sum()
value_3 = rk.finance.npv(flow=cash_3, rate=discount_rate, on=holding.start)
assert value_3 > value
```

**Try it 2: a seven-year hold.** Sell at the end of year 7. The price is already in
`exit_values`: it capitalises year 8.

```python
# solution
seven = rk.duration.Span.years(start=date(2001, 1, 1), count=7)
terminal_7 = exit_values.trim(span=seven.periods(frequency=yearly)[-1])
flows_7 = rk.flow.Stream(flows={"NACF": nacf, "Terminal value": terminal_7})
cash_7 = flows_7.trim(span=seven).sum()
value_7 = rk.finance.npv(flow=cash_7, rate=discount_rate, on=seven.start)
```

**Try it 3: a price above value.** Pay 5 % more than `value`. Is the IRR above or
below 7 %?

```python
# solution
overpay = rk.flow.Stream(
    flows={
        "Purchase": rk.flow.Flow(amounts={holding.start: -1.05 * value}),
        "Cash flows": cash_flows,
    }
).sum()
assert rk.finance.irr(flow=overpay) < discount_rate
```

## Checks and recap

```python
# cell 21 (checks)
assert table["NOI"] == table["PGI"] + table["Vacancy"] + table["OPEX"]
assert terminal_value.total() == exit_values.at(on=date(2010, 1, 1))
assert rk.quantity.isclose(
    actual=rk.finance.irr(flow=investment), expected=discount_rate
)
```

**Recap.**

1. A DCF is dated amounts with units. Grow them, combine them in a Stream and trim
   them to the holding span.
2. The terminal value capitalises the next year's cash flow, so the forecast is one
   year longer than the hold. Shift, divide and trim give it for any sale year.
3. PV, NPV and IRR use the same dates, so a price equal to the NPV earns the discount
   rate.

**Next.** Lesson 02 declares financial equations once and asks them two different
questions.

## Cell budget

20 core code cells and 1 check cell (budget 20–25), 3 exercise solutions. The longest
cell has 10 lines (cell 8). Cells follow `ruff format` (D15).

## Rule check

| Cell | Rules | Result |
| --- | --- | --- |
| 1 | 1 | Pass |
| 2–3 | 1, 5 | G71: `rk.Quantity(text)` at the root and the `rk.quantity` namespace (D13); `pa` and `% pa` ([#148](https://github.com/daniel-fink/rangekeeper/issues/148), [#149](https://github.com/daniel-fink/rangekeeper/issues/149)) |
| 4 | 1, 11 | G01: `Span.years`, `extend`, `periods(yearly)` |
| 5, 19 | 11 | G02: Flow from a mapping of Periods or dates to amounts |
| 6 | 1, 6 | G70: `rk.profile` and `Flow.from_profile` with `initial=` or `total=` (D12; absorbs [#168](https://github.com/daniel-fink/rangekeeper/issues/168)) |
| 7, 10, 12, 16 | 8 | G03: `Flow.at(date)` returns one Quantity |
| 8–9, 13–14 | 11 | G04: Flow arithmetic, `Stream(mapping)`, `with_flows(mapping)`, `select`, `sum()` |
| 11–12, 20 | 6 | G05: `Flow.shift(by=)` and `Flow.trim(period)`; no domain helper for the terminal value |
| 15 | 6 | `resample` with `ResampleMethod` (rename pass, [#103](https://github.com/daniel-fink/rangekeeper/issues/103)) |
| 17–19 | 6 | `pv`, `npv`, `irr` on dates ([#167](https://github.com/daniel-fink/rangekeeper/issues/167), [#164](https://github.com/daniel-fink/rangekeeper/issues/164)) |
| 12, 15, 21 | 5, 8 | G06: Flow value equality and `rk.quantity.isclose` |
