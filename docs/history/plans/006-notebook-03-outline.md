# Notebook 03 A development plan and its financial limits

Archived 2026-10-26: superseded by [ADR-020: walkthrough plan v2](../../decisions/020-walkthrough-plan-v2.md).
Its content is source material for lessons 02 (front door, back door) and 03
(cases, debt and equity). The original outline below is unchanged except for
relative links.

Status: implemented and locally accepted on 2026-10-13 under
[ADR-006](../../decisions/006-walkthrough-curriculum.md). This outline records the agreed teaching
structure. See the [executed notebook](https://github.com/daniel-fink/rangekeeper/blob/codex/walkthrough-acausal/examples/walkthrough/development_feasibility.ipynb)
and [acceptance evidence](../../research/notebook-03-2026-10-13/README.md).

## Purpose

Answer: **What must this development earn, what cost can its income support,
and can we fund the payments when they fall due?**

Continue with the same Building A, Building B, shared basement plinth and shared
services introduced in notebook 02. Keep their source identities, geometry,
quantities and use mix. Add a fixed development plan and a financial investigation.
Do not substitute a separate office building or two-pad numerical example.

The reader should leave able to:

- distinguish a physical design, a development plan and its financial base case;
- declare financial relations once and use Specifications to select known and
  unknown quantities;
- compare required rents with assumed achievable rents;
- calculate a supportable land price under stated lending assumptions;
- distinguish loan support, investment value and payment capacity;
- recognise when a problem needs another assumption or exceeds solver capability.

Aim for eight compact sections and about 25–30 code cells. Put a short question
before each calculation and a short interpretation after its output. Keep detailed
derivations, declaration setup and failure diagnostics in optional disclosures.

## Continuity and assumptions

Notebook 02 values a completed asset. Its periodic CAPEX is replacement or renewal
expenditure, not the cost to construct the project. Prepare a separate development
budget. Keep land, construction, soft costs, contingency and finance allowances
distinct. Map each cost contributor to its existing object UUID and count shared
works once. State whether unit rates include cores and plant before adding them.

The following teaching assumptions were adopted; they are not facts from the
design. Exact rates and funding amounts are recorded in
[development.json](../../../examples/data/mixed_use_property/development.json).

| Item | Proposed treatment |
| --- | --- |
| Starting state | An undeveloped site available for purchase at the valuation date; no existing parking income |
| Base date | 1 January 2027; a teaching date, not a source-model date |
| Shared works | Construct during 2027; include the basement plinth and shared plant |
| Building A | Construct during 2028–2029; open on 1 January 2030 |
| Building B | Construct during 2030–2031; open on 1 January 2032 |
| Common horizon | End of 2036, with a 2037 forecast for terminal value |
| Payments | Annual periods for the main lesson; state the payment date within each period |
| Rent and OPEX basis | Reuse the use-specific relationships from notebook 02. Explicitly rebase its teaching rates to 2027 without claiming an inflation adjustment or market calibration |
| Growth | Use one calendar from the base date; do not restart market growth when a building opens |
| Initial operations | No income before opening; immediate stabilisation after opening is a declared simplification |
| Development rates and funding | Separate teaching inputs, recorded and reconciled in the notebook; not inferred from renewal CAPEX |
| Wait baseline | Do not acquire or build; zero project cash flows under this starting-state convention. Later lessons must add any option premium or site-control costs explicitly |

Show these inputs in one bounded table. Document the terminal-value convention
explicitly. If retaining notebook 02's next-year NACF capitalisation, call it that;
do not silently replace it with NOI capitalisation. Keep the discount rate and all
other valuation conventions fixed during each comparison.

## Reading and cell sequence

### 1. The same property, now a development proposal

**Say.** The geometry describes what could be built. It does not specify when it
will be built, what it will cost or how it will be financed.

**Do.** Load the pinned source Model and its assumptions from disk in a fresh
kernel. Show a compact table of Building A, Building B and the shared works, with
their UUIDs, use mix and areas. Retain a single local Speckle inspection view and
a link to notebook 02's detailed graph explanation. Avoid repeating the complete
geometry, graph and sunburst sequence.

**Discover.** A plan refers to the existing objects. A schedule row does not create
a second Building A or transfer ownership of the shared plant.

### 2. Specify one base plan and a development budget

**Say.** First commit to one sequence. Later notebooks will test other conditions
and choices. These dates are fixed assumptions in this chapter.

**Do.** Create a plan table keyed by source UUID. Show construction start,
completion, opening and cost basis for each package. Use a Plotly timeline with
the shared works and two buildings as three rows. Explain which service
dependencies must be ready before each building can open.

Work one area-based development cost visibly, then apply the same rule to its
declared contributors. Show one reconciliation: building costs plus shared works,
soft costs and contingency equal the non-land development budget. Distinguish
cost amounts, shown as positive budget requirements, from negative cash payments.

**Discover.** Spatial membership, construction packages and service dependencies
answer different questions. The full shared plinth is paid for even while only
one building operates.

### 3. Turn the plan into dated cash flows

**Say.** The base plan determines when costs occur and when income can start.
Timing changes value even when total floor area and undiscounted cost do not change.

**Do.** Recall the Flow/Stream methods from notebook 01. Build signed construction
payments, gate the property income and operating costs by opening date, and align
them to a common annual grid. Show one pro forma and one Plotly cash-flow chart.

Intended code shape, after the preceding cells have supplied the dates and amounts:

```python
development_span = Span(
    name="Development and operations",
    start_inclusive=date(2027, 1, 1),
    end_exclusive=date(2037, 1, 1),
)
periods = development_span.periods(frequency=Frequency.YEAR)

construction = Flow.from_events(
    dates=payment_dates,
    magnitudes=[-cost for cost in payment_amounts],
    units="AUD",
)

cashflows = Stream({
    "Land": land_payments,
    "Construction": construction,
    "Operations": operating_cashflows,
    "Sale": sale_proceeds,
}).resample(
    periods=periods,
    method=ResamplingMethod.SUM,
    missing=MissingValueHandling.ZERO,
)
cashflows.display()
```

Zero-fill periods where the declared plan has no payment; validate that all
supplied payments have known amounts first. Include pre-opening OPEX or holding costs
only through an explicit assumption. Account for periodic asset CAPEX separately.

Calculate unlevered NPV at the common starting date. Do not count mortgage proceeds
as property income or mix equity cash flows with unlevered discounting. Explain why
the value from notebook 02 is not the NPV of this development plan.

### 4. Express the financial relationships once

**Say.** SFFA asks what the completed income can support under stated permanent
loan terms. Its front-door and back-door procedures traverse the same financial
relationships in different directions.

Use Geltner et al., section 28.4.1, Exhibits 28-4 and 28-5, printed pages 771–773.
Preserve the distinction between the annual mortgage constant and an interest
rate. Calculate the constant from fixed amortisation terms in an optional cell.

For this mixed-use property, retain the different hotel, residential and retail
rents and vacancies. Use one dimensionless **rent factor** applied to the reference
rent basket. A factor of 1 means the stated reference rents; 1.1 means each is 10%
higher. Zero parking rent remains zero. This avoids hiding the use mix in a single
average rent or leaving several independent rents unknown.

At a stated stabilised snapshot date, define these relations:

| Relation | Meaning and units |
| --- | --- |
| `total_cost = land_cost + works_cost` | All development costs included once, AUD |
| `mortgage = leverage * total_cost` | Simplified SFFA cost/value assumption, AUD |
| `debt_service = mortgage_constant * mortgage` | Annual mortgage service, AUD/year |
| `noi = coverage * debt_service` | NOI at the selected debt-coverage threshold, AUD/year |
| `effective_income = noi + operating_cost` | Operating cost is a positive requirement here, AUD/year |
| `effective_income = rent_factor * reference_income` | Reference income includes use-specific area, rent and vacancy, AUD/year |

Show a relation diagram with no permanent input/output arrows. Known and unknown
markers will change in the next section; object identities and equations will not.
Explain one scalar Value with its Measure and units before creating the others.
Add these declarations in a new Model revision while preserving the physical Model.

The following uses current expression and formulation constructors. `symbols` maps
the declared names to expression references, and `value_ids` maps them to Value UUIDs:

```python
from rangekeeper.model.expression.authoring import add, equal, multiply
from rangekeeper.model.formulation.authoring import declare

relations = declare(
    id=uuid4(),
    name="Development feasibility",
    equations=[
        ("cost", equal(
            left=symbols["total_cost"],
            right=add(
                left=symbols["land_cost"],
                right=symbols["works_cost"],
            ),
        )),
        ("income", equal(
            left=symbols["effective_income"],
            right=multiply(
                left=symbols["rent_factor"],
                right=symbols["reference_income"],
            ),
        )),
        # Show the four intervening relations in a second short cell.
    ],
    values=tuple(value_ids.values()),
)
```

The final notebook must include all six relations. The excerpt is an outline, not
a complete runnable model. Fix the coefficients, including `reference_income`,
for the first solves so every equation is affine in the selected unknowns.

**Discover.** `left` and `right` describe positions in an equation. They do not
select which quantity the solver must calculate. Known-data Python arithmetic
alone does not declare these relations or become invertible automatically.

### 5. Change the question with a Specification

**Say.** The Model states the relationships. The Specification states the question.

**Do.** Build a front-door Specification with land cost, works cost, operating cost,
reference income and lending coefficients fixed. Declare intermediate values and
the rent factor unknown. Show explicit `Assignment` and `Reference` construction
once, execute with `Executor`, inspect the Run status, and display the required
rent by use beside the reference rent. A required rent is a threshold, not a
forecast or a quantity the developer can command.

Next derive the back-door Specification. Keep the original Model pin and change
only the two roles. With `front_spec`, `model` and `value_ids` defined above:

```python
back_spec = front_spec.lock(
    target=value_ids["rent_factor"],
    quantity=Quantity(magnitude=1.0, units="dimensionless"),
    id=uuid4(),
    model=model,
).unlock(
    target=value_ids["land_cost"],
    id=uuid4(),
    model=model,
)

back_run = executor.execute(back_spec)
assert back_run.report.status.solution is SolutionStatus.FEASIBLE
back_model = store.load_model(back_run.record.outputs[0])
```

Show the same relation diagram with the known/unknown markers swapped and one
comparison table. The original Specification and Model remain unchanged. Do not
pass a solved Model to role editing while the Specification still pins the original
revision; investigate either that original pin or explicitly revise the pin first.

Run a short round-trip check: use the front-door rent factor in the inverse problem
and recover the original land cost. Then restore a factor of 1 to ask what the
reference market basket supports. Interpret a negative residual land amount as a
shortfall under these assumptions, not an achievable negative purchase price.

### 6. Explain what each answer establishes

**Say.** Loan support, investment value and a feasible solution are different claims.

The source's front-door example explicitly uses total cost as a proxy for finished
value and checks that assumption against a capitalised value. Make this assumption
visible here. The back-door number is a conditional cost threshold, not a general
land valuation or proof that a lender will advance that amount. Debt-coverage
requirements do not substitute for a developer's required return.

Compare the SFFA threshold with the dated unlevered DCF from section 3. The snapshot
omits parts of timing and investment risk; matching the two answers is not an
acceptance criterion. Explain any extra finance allowance without counting it
twice in a financing schedule.

Keep three small variations in an optional disclosure:

| Variation | Lesson |
| --- | --- |
| Unlock land cost and rent factor together | There may be many feasible pairs. A returned feasible candidate is not a unique valuation |
| Lock both to values that violate the threshold equality | Inconsistent requirements differ from missing information |
| Unlock a multiplier and the quantity it multiplies | A nonlinear unknown product is outside the current affine executor |

Inspect actual Run statuses and diagnostics. Do not teach that rank deficiency
necessarily causes solver failure, or call every unsuccessful run infeasible.

### 7. Can we fund the plan as payments fall due?

**Say.** A viable income level or positive NPV cannot pay a construction invoice
before cash or a committed facility is available.

**Do.** Add a separate, explicit funding schedule: initial equity, draw dates,
facility limit, payments, receipts and closing cash. Plot the cash balance beside
the facility limit and show the minimum headroom. Do not treat a permanent loan
available at stabilisation as cash available on the construction start date.

At one commitment date, show cash available, undrawn committed funding and costs
already committed but unpaid. Include an example where the immediate payment fits
but remaining committed obligations exceed available resources. Do not subtract
the same commitment a second time when its scheduled payment occurs. Label any
assumed future receipts that the funding test relies upon.

Use a fixed funding plan and explicit checks in this chapter. Do not introduce
optimised drawdowns, endogenous finance rules or automatic phase choice. Put an
amortisation or interest schedule in an optional extension if it obscures the main
forward/inverse lesson.

### 8. Record the base case and carry the question forward

**Do.** Close with one results table: assumed land price, required rent factor,
supportable land price, development NPV and funding shortfall/headroom. Include
the do-not-acquire baseline under the declared starting-state convention.

Retain the base plan, assumption identifiers and accepted investigation outputs
for comparison. Notebook 04 must load the same inputs independently and ask how
the fixed plan performs under different market paths. Timing choices and paid
flexibility provisions enter notebooks 05–06.

## Presentation and helper boundary

- Reuse `helpers/plot.py` and the shared light/dark Plotly style for the timeline,
  cash-flow chart and funding chart. Keep consistent building and use labels.
- Keep one source-backed geometry view for continuity. Use one financial relation
  diagram shown with two role assignments; do not repeat notebook 02's sunbursts.
- Use native Polars tables for assumptions, Specification roles and comparisons.
- Helpers may load validated source data and format views. Keep contributor
  selection, financial relations, role changes and funding checks visible.
- Each notebook runs independently. Do not execute notebook 02 as an import or
  conceal the financial model in a plotting helper.

## Authoring and acceptance work

1. Resolve the proposed dates and select explicit teaching construction, site and
   funding inputs. Reconcile contributor coverage before declaring a base case.
2. Build the canonical financial Values and all six relations. Verify unit handling
   for annual rates versus dated cash amounts; do not infer annualisation.
3. Execute front-door, back-door and round-trip investigations with independent
   arithmetic checks. Verify Model and Specification immutability and reported limits.
4. Reconcile development payments, opening gates, terminal value and funding
   obligations. Check that shared costs and finance costs are counted once.
5. Execute from a fresh kernel, inspect tables and charts in light and dark modes,
   and build with `--preview-chapter` before adding the chapter to `myst.yml`.

Current API review uses `model.expression.authoring`, `model.formulation.authoring`,
`Specification.lock()`/`unlock()` and the [execution contract](../../reference/execution.md).
An isolated API check on 2026-10-13 passed all six relations, forward/inverse and
round-trip solving, annual units, source immutability and sparse Flow resampling.
It used synthetic amounts solely to check the APIs, not the mixed-use development
budget. Code excerpts require the preceding declaration cells; the chapter itself
has since passed the independent checks in the acceptance record above. No
new library API was needed.
