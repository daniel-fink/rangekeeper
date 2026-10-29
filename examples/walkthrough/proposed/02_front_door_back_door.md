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
> 1. make a Model, edit it in a draft and commit it, with string equations;
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
data = helpers.load_property(year=2032)
data  # key, quantity and origin of each total
```

Narrative: this is the property. Its totals come from this design. Lesson 06 opens
the design and shows the objects behind each total.

```python
# cell 2b
helpers.show_geometry(name="mixed_use_property")
```

## 2. A calculation has a direction

Narrative: a spreadsheet calculates in one direction. Start from the cost and
calculate the income that a lender needs. Do it once in plain Python. Then ask the
reverse question: what land price does a given income support? The spreadsheet needs
new formulas. The equations did not change; only the question did.

```python
# cell 3
total_cost = 20e6 + data["works_cost"].magnitude
debt_service = 0.0860 * 0.65 * total_cost
required_noi = 1.25 * debt_service
required_noi  # AUD per year, calculated from cost to income
```

## 3. Declare the equations once

Narrative: a Model describes things, called entities, with their values and the
equations between them. Here it describes one entity: the project, the whole
property as one asset. An equation does
not say which side is known.

A Model never changes. To change one, `edit()` gives a draft. The draft collects the
changes; `commit()` checks them all once, including the units of every equation, and
returns a new Model. The first Model is empty; the draft adds the project, its values
and its equations.

```python
# cell 4
model = rk.Model(name="Mixed-use feasibility")
draft = model.edit()
project = draft.add_entity(code="project", classification="project")
project.value(key="land_cost", units="AUD")
project.value(key="works_cost", units="AUD")
project.value(key="total_cost", units="AUD")
project.value(key="leverage", units="ratio")
project.value(key="mortgage", units="AUD")
project.value(key="mortgage_constant", units="% pa")
project.value(key="debt_service", units="AUD pa")
```

Narrative: the cost and loan values are declared. Now the income values.

```python
# cell 4b
project.value(key="coverage", units="ratio")
project.value(key="noi", units="AUD pa")
project.value(key="operating_cost", units="AUD pa")
project.value(key="effective_income", units="AUD pa")
project.value(key="rent_factor", units="ratio")
project.value(key="reference_income", units="AUD pa")
```

```python
# cell 5
project.equations(
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
project.value(key="hotel_area", units="sqm")
project.value(key="hotel_rent", units="AUD per sqm pa")
project.value(key="hotel_vacancy", units="ratio")
project.value(key="residential_area", units="sqm")
project.value(key="residential_rent", units="AUD per sqm pa")
project.value(key="residential_vacancy", units="ratio")
project.value(key="retail_area", units="sqm")
project.value(key="retail_rent", units="AUD per sqm pa")
project.value(key="retail_vacancy", units="ratio")
```

```python
# cell 6b
project.equations(
    "reference_income = hotel_area * hotel_rent * (1 - hotel_vacancy)"
    " + residential_area * residential_rent * (1 - residential_vacancy)"
    " + retail_area * retail_rent * (1 - retail_vacancy)"
)
model = draft.commit()
```

```python
# cell 7
helpers.show_equations(of=model)  # a diagram with no input or output arrows
```

> **Under the hood: the same equation in Python.** `rangekeeper.expressions`, imported
> as `rx`, writes equations with Python operators. A declaration returns a handle, and
> `project.ref(key=)` finds the handle of a value declared earlier. Text and Python make
> the same records, and `.text` prints the text form. Both forms use the same
> names.
>
> ```python
> import rangekeeper.expressions as rx
>
> project = model.edit().entity(code="project")
> noi = project.ref(key="noi")
> coverage = project.ref(key="coverage")
> debt_service = project.ref(key="debt_service")
> assert (noi == coverage * debt_service).text == "noi = coverage * debt_service"
> ```

## 4. The mortgage constant, by hand once

Narrative: the mortgage constant is the annual debt service per dollar of loan. It is
not the interest rate. With monthly payments over 20 years at 6 % a year:

```python
# cell 8
r, n = 0.06 / 12, 20 * 12
12 * r / (1 - (1 + r) ** -n)  # 0.0860 per year
```

Narrative: the library has one general loan calculation: the payment, like a
spreadsheet's PMT, but with units. The mortgage constant is the payment on one dollar
of loan, per year. Check that it agrees with the calculation by hand.

```python
# cell 9
monthly = rk.duration.Frequency.MONTH
payment = rk.finance.payment(
    principal="1 AUD", rate="6 % pa", term="20 years", frequency=monthly
)
payment  # the monthly payment on each dollar of loan
constant = (payment / rk.Quantity(text="1 AUD")).to(units="% pa")
constant  # 8.60 % pa
```

> **Finance note.** Loan-to-value (leverage) limits the loan to a share of value. SFFA
> uses total development cost as a proxy for value. The debt-service coverage ratio
> requires NOI to exceed debt service by a margin.

## 5. The front door

Narrative. **Predict:** at a land cost of 20 million AUD, must rents be above or below
the reference rents? A Specification asks the question. It fixes the known values, by
name. Every value that it does not fix is free: the solve finds it. Each `fix` returns
a new Specification, so the fixes can be grouped by topic.

```python
# cell 10
front = (
    model.specify(name="Front door")
    .fix(land_cost="20e6 AUD", works_cost=data["works_cost"])
    .fix(operating_cost=data["operating_cost"])
    .fix(leverage="65 %", coverage=1.25, mortgage_constant=constant)
)
```

Narrative: the reference rents and areas by use, from the data package. Every fixed
value is named.

```python
# cell 10b
front = front.fix(
    hotel_area=data["hotel_area"],
    hotel_rent=data["hotel_rent"],
    hotel_vacancy=data["hotel_vacancy"],
    residential_area=data["residential_area"],
    residential_rent=data["residential_rent"],
    residential_vacancy=data["residential_vacancy"],
    retail_area=data["retail_area"],
    retail_rent=data["retail_rent"],
    retail_vacancy=data["retail_vacancy"],
)
front.roles  # each value: fixed with its quantity, or free for the solve to find
```

```python
# cell 11
front_outcome = rk.execution.solve(specification=front)
front_outcome.raise_for_status()
front_outcome["rent_factor"]
```

Narrative: the rent factor applies to every use. Show the required rent beside the
reference rent. A required rent is a threshold, not a forecast.

```python
# cell 12
factor = front_outcome["rent_factor"]
required_rent = {
    "hotel": factor * data["hotel_rent"],
    "residential": factor * data["residential_rent"],
    "retail": factor * data["retail_rent"],
}
required_rent
```

## 6. The back door

Narrative. **Predict:** at the reference rents, can the property support a land price
of 20 million AUD? Change two roles: fix the rent factor at 1 and free the land cost.
The Model does not change.

```python
# cell 13
back = front.fix(rent_factor=1).free("land_cost")
back_outcome = rk.execution.solve(specification=back)
back_outcome["land_cost"]
```

```python
# cell 14
helpers.show_equations(of=back)  # the same equations, with different markers
```

```python
# cell 15
rk.execution.compare(
    outcomes={"Front door": front_outcome, "Back door": back_outcome},
    keys=["land_cost", "rent_factor", "noi", "mortgage"],
)
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
rk.execution.solve(specification=round_trip)["land_cost"]  # 20e6 AUD
```

## 8. Change one input

Narrative. **Predict:** if the lender allows only 50 % leverage, does the supportable
land price rise or fall? Change one fixed value.

```python
# cell 17
lower_leverage = back.fix(leverage="50 %")
lower_leverage_outcome = rk.execution.solve(specification=lower_leverage)
lower_leverage_outcome["land_cost"] - back_outcome["land_cost"]
```

## 9. Optional: when the question is not well posed

Narrative: a solve can fail in three different ways. Each failure has its own status
and a diagnostic that names the values or equations by key.

**Too few fixed values.** Free both the land cost and the rent factor. Many pairs fit,
and each pair changes every value between them.

```python
# cell 18
loose = back.free("rent_factor")
loose_outcome = rk.execution.solve(specification=loose)
(
    loose_outcome.status,
    loose_outcome.free_unknowns,
)  # UNDERDETERMINED, ('land_cost', 'total_cost', ..., 'rent_factor')
```

**Too many fixed values that disagree.** Fix both the land cost and the rent factor.

```python
# cell 19
tight = front.fix(rent_factor=1)
tight_outcome = rk.execution.solve(specification=tight)
(
    tight_outcome.status,
    tight_outcome.diagnostics,
)  # INFEASIBLE; the diagnostic names the equations
```

**A product of two unknowns.** Ask for leverage and coverage together.

```python
# cell 20
both_free = back.fix(land_cost="20e6 AUD").free("leverage", "coverage")
both_free_outcome = rk.execution.solve(specification=both_free)
both_free_outcome.status, both_free_outcome.diagnostics
# UNSUPPORTED: nonaffine_unknowns in "noi = coverage * debt_service"
```

```python
# cell 21
try:
    both_free_outcome.raise_for_status()
except rk.errors.UnsupportedError as error:
    print(error.code, error.equation)
```

## Exercises

**Try it 1: the largest loan.** At a land cost of 20 million AUD and reference rents,
what is the highest leverage the income supports?

```python
# solution
max_leverage = front.fix(rent_factor=1).free("leverage")
rk.execution.solve(specification=max_leverage)["leverage"]
```

**Try it 2: a longer amortisation.** With a 25-year amortisation, what rent factor
does the front door need?

```python
# solution
longer = rk.finance.payment(
    principal="1 AUD", rate="6 % pa", term="25 years", frequency=monthly
)
longer_constant = (longer / rk.Quantity(text="1 AUD")).to(units="% pa")
longer_outcome = rk.execution.solve(
    specification=front.fix(mortgage_constant=longer_constant)
)
assert longer_outcome["rent_factor"] < factor
```

**Try it 3: a stronger market.** If rents were 10 % above the reference rents, what
land price could they support? Predict the change before you solve.

```python
# solution
stronger = back.fix(rent_factor=1.1)
stronger_outcome = rk.execution.solve(specification=stronger)
assert stronger_outcome["land_cost"] > back_outcome["land_cost"]
```

## Checks and recap

```python
# cell 22 (checks)
assert rk.quantity.isclose(
    actual=rk.execution.solve(specification=round_trip)["land_cost"],
    expected=rk.Quantity(text="20e6 AUD"),
)
assert rk.quantity.isclose(
    actual=front_outcome["effective_income"],
    expected=factor * front_outcome["reference_income"],
)
assert back.model_id == front.model_id == model.id
```

**Recap.**

1. A Model declares its equations once. An equation has no calculation direction.
2. A Specification asks the question: fix what you know, and the solve finds the
   rest. The back door changes two roles, not the Model.
3. A solve can be underdetermined, infeasible or unsupported. Each status names its
   cause.

**Next.** Lesson 03 puts the property on a timeline, compares named market cases and
adds debt, equity and funding.

## Cell budget

21 core code cells, 4 optional cells and 1 check cell (budget 20–25). The longest cell
has 13 lines (cell 10b). Cells follow `ruff format` (D15).

## Rule check

| Cell | Rules | Result |
| --- | --- | --- |
| 1 | 1, 10 | Walkthrough helpers package ([#87](https://github.com/daniel-fink/rangekeeper/issues/87), [#88](https://github.com/daniel-fink/rangekeeper/issues/88)) |
| 2 | 10 | G07: helpers load totals with origins; they do not calculate |
| 2b | 10 | G07: the helper draws the design's geometry. It shows no graph and no values |
| 3 | 6 | By hand once; replaced in cells 9–11 |
| 4–6 | 2, 3, 5 | `rk.Model`, `edit`, `commit` ([#141](https://github.com/daniel-fink/rangekeeper/issues/141), [#145](https://github.com/daniel-fink/rangekeeper/issues/145), [#151](https://github.com/daniel-fink/rangekeeper/issues/151)). G08: `rk.Model(name=)`, `ModelDraft.add_entity` and `entity`, entity handles with `value(key=, units=)` and `equations` (D6, D16) |
| 6, 11 | 6 | G09: staged solve. `reference_income` is a product of fixed values, then `rent_factor * reference_income` is affine |
| 7, 14 | 10 | Helper draws the equations and their values, with role markers for a Specification ([#88](https://github.com/daniel-fink/rangekeeper/issues/88)) |
| aside | 3 | G78: `rangekeeper.expressions` (`rx`), `project.ref(key=)` and operators on handles ([#143](https://github.com/daniel-fink/rangekeeper/issues/143)); G10: `Equation.text` gives canonical text |
| 9 | 6 | `rk.finance.payment` ([#167](https://github.com/daniel-fink/rangekeeper/issues/167)); the constant is derived from it (D19) |
| 10, 13 | 2, 4 | `specify`, `fix`, `free` ([#144](https://github.com/daniel-fink/rangekeeper/issues/144)). G11: unfixed values are free by default; `fix` takes strings, numbers and Quantities; `roles` table |
| 11, 13 | 8 | `solve` and `Outcome` ([#126](https://github.com/daniel-fink/rangekeeper/issues/126), [#127](https://github.com/daniel-fink/rangekeeper/issues/127)). G12: `solve` resolves the Model that made the Specification, with no resolver argument |
| 15 | 8 | G66: `rk.execution.compare(outcomes=, keys=)` shows named Outcomes side by side; the same call takes `baseline=` in later lessons |
| 18 | 9 | `underdetermined` ([#152](https://github.com/daniel-fink/rangekeeper/issues/152)) |
| 19 | 9 | Fixed values that conflict are infeasible ([#153](https://github.com/daniel-fink/rangekeeper/issues/153)), with coded diagnostics ([#154](https://github.com/daniel-fink/rangekeeper/issues/154)) |
| 20–21 | 9 | G14: `nonaffine_unknowns` diagnostic and `UnsupportedError` with `code` and `equation` |
| 22 | 8 | G06 (`isclose`); `Specification.model_id` |
