# Lesson 02: Front door, back door (proposed cells)

Issue: [#204](https://github.com/daniel-fink/rangekeeper/issues/204). Plan:
[ADR-020 §02](../../../docs/decisions/020-walkthrough-plan-v2.md#02-front-door-back-door).
API conventions and the gap list: [README](README.md).

## Goals box

> **Question.** What rent must the property earn to support its cost? What land price
> can the reference rents support?
>
> **You will learn to:**
>
> 1. build a Model with a builder and string equations;
> 2. tell an equation from a calculation direction;
> 3. fix values in a Specification, solve, and read the result from `Outcome`;
> 4. reverse the question by changing two roles;
> 5. (optional) recognise underdetermined, infeasible and unsupported outcomes.
>
> **Before you start.** Lesson 01.
>
> **Time.** 60 minutes core, 20 minutes optional.
>
> **Not in this lesson.** Dates and cash flows over time (lesson 03). The project
> graph (lesson 06): here the property is one asset, with totals by use.
>
> **Source.** Simple financial feasibility analysis (SFFA), Geltner et al. (2007),
> section 28.4.1. The method is cited; the exhibits are not reproduced. The numbers
> are the property's own.

## 1. The property as one asset

Narrative: the mixed-use property has two buildings over a shared basement. In
this lesson we use only its totals at a stabilised year, 2032: lettable area,
reference rent and vacancy for each use, the operating cost and the works cost. The
data package records the origin of each number.

```python
# cell 1
from datetime import date

import rangekeeper as rk
import helpers
```

```python
# cell 2
data = helpers.load_property(snapshot=2032)
data.inputs                            # key, quantity and origin of each total
```

## 2. A calculation has a direction

Narrative: a spreadsheet calculates in one direction. Start from the cost and
calculate the income that a lender needs. Do it once in plain Python. Then ask the
reverse question: what land price does a given income support? The spreadsheet needs
new formulas. The relations did not change; only the question did.

```python
# cell 3
total_cost = 20e6 + data.inputs["works_cost"].magnitude
debt_service = 0.0860 * 0.65 * total_cost
required_noi = 1.25 * debt_service
required_noi                          # AUD per year, calculated from cost to income
```

## 3. Declare the relations once

Narrative: a Model declares values with their units and the equations between them.
An equation does not say which side is known. The builder collects the declarations;
`commit()` checks them once, including the units of every equation, and returns an
immutable Model.

```python
# cell 4
b = rk.Model.build(name="Mixed-use feasibility", subject="property")
b.values(
    land_cost="AUD", works_cost="AUD", total_cost="AUD",
    leverage="ratio", mortgage="AUD", mortgage_constant="1/year",
    debt_service="AUD pa", coverage="ratio", noi="AUD pa",
    operating_cost="AUD pa", effective_income="AUD pa",
    rent_factor="ratio", reference_income="AUD pa",
)
```

```python
# cell 5
b.equations(
    "total_cost = land_cost + works_cost",
    "mortgage = leverage * total_cost",
    "debt_service = mortgage_constant * mortgage",
    "noi = coverage * debt_service",
    "effective_income = noi + operating_cost",
    "effective_income = rent_factor * reference_income",
)
```

Narrative: the reference income keeps the different rents and vacancies of each use.
One dimensionless rent factor scales all of them: 1 means the reference rents, 1.1
means 10 % higher. Parking earns no rent.

```python
# cell 6
b.values(hotel_area="sqm", hotel_rent="AUD/sqm pa", hotel_vacancy="ratio",
         residential_area="sqm", residential_rent="AUD/sqm pa", residential_vacancy="ratio",
         retail_area="sqm", retail_rent="AUD/sqm pa", retail_vacancy="ratio")
b.equation(
    "reference_income = hotel_area * hotel_rent * (1 - hotel_vacancy)"
    " + residential_area * residential_rent * (1 - residential_vacancy)"
    " + retail_area * retail_rent * (1 - retail_vacancy)"
)
model = b.commit()
```

```python
# cell 7
helpers.show_relations(model)          # a diagram with no input or output arrows
```

> **Under the hood: the operator form.** The same equation can use Python operators
> on value handles. Both forms make the same records.
>
> ```python
> v = model.edit().handles()
> assert (v.noi == v.coverage * v.debt_service).text == "noi = coverage * debt_service"
> ```

## 4. The mortgage constant, by hand once

Narrative: the mortgage constant is the annual debt service per dollar of loan. It is
not the interest rate. With monthly payments over 20 years at 6 % a year:

```python
# cell 8
r, n = 0.06 / 12, 20 * 12
12 * r / (1 - (1 + r) ** -n)           # 0.0860 per year
```

```python
# cell 9
constant = rk.finance.mortgage_constant(rate="6 %/year", term="20 years", payments_per_year=12)
constant
```

> **Finance note.** Loan-to-value (leverage) limits the loan to a share of value. SFFA
> uses total development cost as a proxy for value. The debt-service coverage ratio
> requires NOI to exceed debt service by a margin.

## 5. The front door

Narrative. **Predict:** at a land cost of 20 million AUD, must rents be above or below
the reference rents? A Specification asks the question. It fixes the known values.
Every value that it does not fix is free: the solve finds it.

```python
# cell 10
lending = {"leverage": "65 %", "coverage": 1.25, "mortgage_constant": constant}
front = model.specify("Front door").fix(**data.inputs, **lending, land_cost="20e6 AUD")
front.roles                            # fixed values, and the free values the solve finds
```

```python
# cell 11
front_outcome = rk.execution.solve(front)
front_outcome.raise_for_status()
front_outcome["rent_factor"]
```

Narrative: the rent factor applies to every use. Show the required rent beside the
reference rent. A required rent is a threshold, not a forecast.

```python
# cell 12
factor = front_outcome["rent_factor"]
{use: factor * data.inputs[f"{use}_rent"] for use in ("hotel", "residential", "retail")}
```

## 6. The back door

Narrative. **Predict:** at the reference rents, can the property support a land price
of 20 million AUD? Change two roles: fix the rent factor at 1 and free the land cost.
The Model does not change.

```python
# cell 13
back = front.fix(rent_factor=1).free("land_cost")
back_outcome = rk.execution.solve(back)
back_outcome["land_cost"]
```

```python
# cell 14
helpers.show_relations(back)           # the same equations, with different markers
```

```python
# cell 15
rk.execution.table({"Front door": front_outcome, "Back door": back_outcome},
                   "land_cost", "rent_factor", "noi", "mortgage")
```

> **Finance note.** A negative supportable land price is a shortfall under these
> assumptions. It is not a price that anyone can pay. The back-door number is a cost
> threshold, not a valuation of the land.

## 7. Round trip

Narrative: put the front door's rent factor into the back door. The solve must give
back the land cost that we started with.

```python
# cell 16
round_trip = back.fix(rent_factor=front_outcome["rent_factor"])
rk.execution.solve(round_trip)["land_cost"]          # 20e6 AUD
```

## 8. Change one input

Narrative. **Predict:** if the lender allows only 50 % leverage, does the supportable
land price rise or fall? Change one fixed value.

```python
# cell 17
rk.execution.solve(back.fix(leverage="50 %"))["land_cost"] - back_outcome["land_cost"]
```

## 9. Optional: when the question is not well posed

Narrative: a solve can fail in three different ways. Each failure has its own status
and a diagnostic that names the values or equations by key.

**Too few fixed values.** Free both the land cost and the rent factor. Many pairs fit.

```python
# cell 18
loose = rk.execution.solve(back.free("rent_factor"))
loose.status, loose.free_unknowns      # UNDERDETERMINED, ('land_cost', 'rent_factor')
```

**Too many fixed values that disagree.** Fix both the land cost and the rent factor.

```python
# cell 19
tight = rk.execution.solve(front.fix(rent_factor=1))
tight.status, tight.diagnostics        # INFEASIBLE; the diagnostic names the equations
```

**A product of two unknowns.** Ask for leverage and coverage together.

```python
# cell 20
product = rk.execution.solve(back.fix(land_cost="20e6 AUD").free("leverage", "coverage"))
product.status, product.diagnostics    # UNSUPPORTED: nonaffine_unknowns in "noi = coverage * debt_service"
```

```python
# cell 21
try:
    product.raise_for_status()
except rk.errors.UnsupportedError as error:
    print(error.code, error.equation)
```

## Exercises

**Try it 1: the largest loan.** At a land cost of 20 million AUD and reference rents,
what is the highest leverage the income supports?

```python
# solution
max_leverage = model.specify("Largest loan").fix(
    **data.inputs, **lending, land_cost="20e6 AUD", rent_factor=1).free("leverage")
rk.execution.solve(max_leverage)["leverage"]
```

**Try it 2: a longer amortisation.** With a 25-year amortisation, what rent factor
does the front door need?

```python
# solution
longer = rk.finance.mortgage_constant(rate="6 %/year", term="25 years", payments_per_year=12)
assert rk.execution.solve(front.fix(mortgage_constant=longer))["rent_factor"] < factor
```

**Try it 3: a stronger market.** If rents were 10 % above the reference rents, what
land price could they support? Predict the change before you solve.

```python
# solution
stronger = rk.execution.solve(back.fix(rent_factor=1.1))["land_cost"]
assert stronger > back_outcome["land_cost"]
```

## Checks and recap

```python
# cell 22 (checks)
assert rk.quantity.isclose(rk.execution.solve(round_trip)["land_cost"], rk.Quantity("20e6 AUD"))
assert rk.quantity.isclose(front_outcome["effective_income"],
                        factor * front_outcome["reference_income"])
assert back.model_id == front.model_id == model.id
```

**Recap.**

1. A Model declares relations once. An equation has no calculation direction.
2. A Specification asks the question: fix what you know, and the solve finds the
   rest. The back door changes two roles, not the Model.
3. A solve can be underdetermined, infeasible or unsupported. Each status names its
   cause.

**Next.** Lesson 03 puts the property on a timeline, compares named market cases and
adds debt, equity and funding.

## Cell budget

17 core code cells, 4 optional cells and 1 check cell (budget 20–25). The longest
cell has 9 lines (cell 4).

## Rule check

| Cell | Rules | Result |
| --- | --- | --- |
| 1 | 1, 10 | Walkthrough helpers package ([#87](https://github.com/daniel-fink/rangekeeper/issues/87), [#88](https://github.com/daniel-fink/rangekeeper/issues/88)) |
| 2 | 10 | G07: helpers load totals with origins; they do not calculate |
| 3 | 6 | By hand once; replaced in cells 9–11 |
| 4–6 | 2, 3, 5 | `Model.build`, `values`, `equations`, `commit` ([#141](https://github.com/daniel-fink/rangekeeper/issues/141), [#145](https://github.com/daniel-fink/rangekeeper/issues/145), [#151](https://github.com/daniel-fink/rangekeeper/issues/151)). G08: `subject=` and bulk `values(**units)` |
| 6, 11 | 6 | G09: staged solve. `reference_income` is a product of fixed values, then `rent_factor * reference_income` is affine |
| 7, 14 | 10 | Helper draws the relations ([#88](https://github.com/daniel-fink/rangekeeper/issues/88)) |
| aside | 3 | Operator form ([#143](https://github.com/daniel-fink/rangekeeper/issues/143)). G10: `Equation.text` gives canonical text |
| 9 | 6 | `mortgage_constant` ([#167](https://github.com/daniel-fink/rangekeeper/issues/167)) |
| 10, 13 | 2, 4 | `specify`, `fix`, `free` ([#144](https://github.com/daniel-fink/rangekeeper/issues/144)). G11: unfixed values are free by default; `fix` takes strings, numbers and Quantities; `roles` table |
| 11, 13 | 8 | `solve` and `Outcome` ([#126](https://github.com/daniel-fink/rangekeeper/issues/126), [#127](https://github.com/daniel-fink/rangekeeper/issues/127)). G12: `solve` resolves the Model that made the Specification, with no resolver argument |
| 15 | 8 | G13: `rk.execution.table` for named Outcomes |
| 18 | 9 | `underdetermined` ([#152](https://github.com/daniel-fink/rangekeeper/issues/152)) |
| 19 | 9 | Fixed values that conflict are infeasible ([#153](https://github.com/daniel-fink/rangekeeper/issues/153)), with coded diagnostics ([#154](https://github.com/daniel-fink/rangekeeper/issues/154)) |
| 20–21 | 9 | G14: `nonaffine_unknowns` diagnostic and `UnsupportedError` with `code` and `equation` |
| 22 | 8 | G06 (`isclose`); `Specification.model_id` |
