# ADR-020: Walkthrough plan v2

Status: accepted for 1.0; proposed cells recorded ([#201](https://github.com/daniel-fink/rangekeeper/issues/201)); authoring pending. Recorded: 2026-10-26.

This record is the walkthrough plan for 1.0. It replaces the
[ADR-006 curriculum](006-walkthrough-curriculum.md) and follows the direction in
[ADR-019](019-walkthrough-direction.md). It defines the reader types, book
outcomes, lessons, developer-experience principles, teaching conventions and
source rights. The proposed cells ([#201](https://github.com/daniel-fink/rangekeeper/issues/201))
and the lessons ([#203](https://github.com/daniel-fink/rangekeeper/issues/203)–[#209](https://github.com/daniel-fink/rangekeeper/issues/209))
are separate work.

## Problem

- **The lessons follow the library's history, not its ideas.** ADR-006 teaches
  the property graph before the first solve. The main idea of the library,
  "declare an equation once and ask it different questions", appears in lesson 03.
- **The lessons do not say who they are for.** There are no reader types,
  book outcomes, prerequisites or time estimates.
- **The code hides the library.** Lesson 03 writes equations as nested
  constructors and revises a Model with nested `.replace` calls. It types a
  `schema_version`, uses seven deep imports and pastes UUID literals. It does
  its finance in plain Python: a mortgage constant, compounding loops, NPV as
  PV minus land and a cash-balance loop. It walks the hierarchy by hand and
  compares unit strings such as `"meter ** 2"`.
- **A usability test found more gaps.** There is no NPV helper. PV uses period
  indices while IRR uses dates. Reading a solved value takes four steps.
- **The source rights are not recorded.** The book uses four figures from a
  published book. The property data has no recorded licence.

## Choice

### Book shape

The book has seven lessons. Each lesson teaches one principle of the library.
All lessons after lesson 01 use one continuing project: the mixed-use property
from the pinned Speckle source (project `c0f66c35e3`, captured in
[`examples/data/mixed_use_property`](../../examples/data/mixed_use_property)).
It has two buildings over a shared basement plinth with shared services.

- **Lessons 02–05 use the property as one asset.** They use its totals, for
  example floor area by use and costs by package, from the data package. They
  do not show its graph.
- **Lesson 06 reveals the graph.** It shows that the totals in lessons 02–05 are
  rollups over the project's objects and relationships.
- **Lesson 07 changes the graph.** Policies select design variants that change
  the project's structure.

| Lesson | Principle | Project question | Replaces in ADR-006 |
| --- | --- | --- | --- |
| 01 Basic discounted cash flow | A DCF is dated amounts that are grown, combined and discounted | What is this income stream worth? | 01 |
| 02 Front door, back door | Declare an equation once. The Specification asks the question | What rent must the property earn, and what land price can its rent support? | 03 §4–6 |
| 03 Cases, debt and equity | One Model, many questions: a batch of named cases gives comparable results | How does the base plan perform in weak, reference and strong markets, with and without debt? Can we pay the bills on time? | 03 §1–3, §7–8 and legacy deterministic scenarios |
| 04 Many market futures | Market futures are captured, replayable inputs | How does the same plan perform across many possible market histories? | 04 |
| 05 When to commit | A policy uses only what is known at its date. Flexibility has value that we can compare | When should we buy the site, start Building B or stop? | 05 (timing) |
| 06 Project structure | The project is a graph. Totals are rollups over chosen relationships | Where do the income, costs and value of lessons 02–05 come from? | 02 |
| 07 Policies and the model graph | Policies can change the project's structure through bounded design variants | Which design provisions are worth paying for now? | 05 (phasing) and 06 |

A short book introduction (not a lesson) defines the terms below. It also has a
"Start here" page with a suggested route for each reader type.

| Term | Meaning |
| --- | --- |
| Base plan | What is proposed, in what sequence, and when |
| Base case | The financial result of the base plan under stated reference assumptions |
| Case | One named set of assumptions in a batch, for example "weak market" |
| Market path | One possible history of external conditions, made by a path generator |
| Flexibility strategy | The choices kept open, their costs and the rules to use them |
| Realised development | What is built, and when, after a strategy's rules run on one path |

### Reader types

All readers take the same lessons. Short asides serve the different types:
**Under the hood** asides for developers and **Finance note** asides for readers
who are new to real-estate finance. A reader can skip an aside without losing
the lesson.

| Reader | Assumed knowledge | Goal | Suggested route |
| --- | --- | --- | --- |
| Analyst | Spreadsheet DCF, NPV and IRR, cap rates, pro formas and debt service. Can run a notebook cell and change a number. Little Python | Build, question and revise a property model. Answer inverse questions without rewriting a calculation | All lessons in order. Skip Under the hood asides |
| Integrating developer | Python 3.12, typing, packaging and JSON. Little real-estate finance | Build documents with builders, run solves, read `Outcome`, keep and replay results, and add Rangekeeper to a pipeline | 01 quickly, then 02–07 with all Under the hood asides. Read Finance notes |
| Student or researcher | The flexibility and uncertainty methods of de Neufville and Geltner. Some Python or Excel | Apply the book's methods to a realistic project with replayable market paths and paired comparisons | All lessons in order. Spend most time on 02, 04, 05 and 07; Finance notes cite the book's chapters |
| Computational designer | Geometry, BIM and graphs. Some Python. Little finance | Connect design objects to value, query and roll up by structure, and compare design variants | 01–05 on the core path only, then 06 and 07 in depth. Read Finance notes |

### Book outcomes

After the whole book, a reader can:

1. Build a dated pro forma from Flows and Streams, and value it with NPV and IRR
   on the same date basis.
2. Declare financial equations once, and answer forward and inverse questions by
   changing which values are fixed and which are free.
3. Tell an underdetermined, infeasible or unsupported solve from a solved one,
   and explain each from its diagnostics.
4. Compare named cases in one batch, and read every result from `Outcome`.
5. Explain unlevered and levered returns, and test whether committed funding
   covers payments when they fall due.
6. Generate, capture and reuse market paths, and read the distribution of a
   plan's results across them.
7. Write decision rules that use only available information, and value a
   flexibility strategy by paired comparison on the same paths.
8. Trace a total to the project objects that contribute to it, through
   relationships, views, filters, rollups and pivots, and count shared items once.
9. Compare design variants that change the project's structure, and state the
   largest premium that a provision justifies under a stated criterion.
10. (Under the hood) Save, reload and replay documents, and build them with
    deterministic IDs.

### Lesson anatomy and time

Every lesson has these parts:

1. **Goals box.** The project question, three to five learning goals,
   prerequisite lessons, the time estimate and what the lesson does not cover.
2. **Predict, then run.** Pose a question and ask for a prediction. Explain the
   relationship, show a short calculation and inspect the result. Change one
   input, then explain what changed.
3. **Exercises.** Two or three "Try it" cells with collapsed solutions. CI runs
   the solutions.
4. **Checks and recap.** Assertions tied to the lesson's claims, a three-point
   recap and a bridge to the next lesson.

The core path takes 45–60 minutes, in about 20–25 code cells. Optional sections
(derivations, stochastic detail, failure cases) add 15–30 minutes.

### Lessons

Each lesson lists its library dependencies by issue. The proposed-cells pass (#201)
can add more dependencies to [#169](https://github.com/daniel-fink/rangekeeper/issues/169).
The sketches are not binding. They show the intended shape only. #201 writes
the real cells.

#### 01 Basic discounted cash flow

- **Question.** What is this income stream worth?
- **Project.** The small example of Table 1.1 in de Neufville and Geltner
  (2018), chapter 1. It is not the property.
- **Goals.** Make Flows with units and periods. Grow an amount over periods.
  Combine lines in a Stream, resample them and trim them to a holding span.
  Capitalise next-year net cash flow for the reversion. Calculate NPV on a date.
- **Prerequisites.** None in the book. Spreadsheet DCF.
- **Time.** 45 minutes core, 15 optional.
- **Library shown.** `rk.duration` (Span, Frequency), `rk.flow` (Flow, Stream:
  display, resample, trim, sum), growth, `rk.finance` NPV and PV, `rk.Quantity`. Known
  data only: no Model, equations or solve.
- **Finance taught.** Potential and effective gross income, vacancy, operating
  expenses, NOI, capital expenditure, net annual cash flow, reversion, cap rate,
  discount rate, PV and NPV, holding period and forecast period.
- **Changes from today.** "Projection" becomes "growth". A single-event Flow
  replaces the uniform distribution for the reversion. An NPV helper replaces
  PV plus collapse. Discounting and IRR use the same date basis.
- **Depends on.** [#167](https://github.com/daniel-fink/rangekeeper/issues/167)
  (NPV), [#168](https://github.com/daniel-fink/rangekeeper/issues/168) (growth),
  [#148](https://github.com/daniel-fink/rangekeeper/issues/148) (`Quantity` from text),
  [#164](https://github.com/daniel-fink/rangekeeper/issues/164) (IRR), and the
  public namespaces of [#52](https://github.com/daniel-fink/rangekeeper/issues/52).

```python
import rangekeeper as rk

holding = rk.duration.Span.years(start=date(2001, 1, 1), count=10)
pgi = rk.flow.Flow.grow(rk.units.q("100 USD"), periods=holding.extend(years=1), rate=0.02)
noi = rk.flow.Stream({"PGI": pgi, "Vacancy": -0.05 * pgi, "OPEX": -0.35 * pgi}).sum()
value = rk.finance.npv(cashflows, rate=0.07, on=holding.start)
```

#### 02 Front door, back door

- **Question.** What rent must the property earn to support its cost? What land
  price can the reference rents support?
- **Project.** The property as one asset, at a stabilised snapshot year. Area
  by use comes from the data package. One dimensionless rent factor scales the
  reference rents of all uses.
- **Goals.** Make a Model, edit it in a draft and commit it, with string equations. Tell an
  equation from a calculation direction. Fix and free values in a
  Specification. Solve and read the result from `Outcome`. Reverse the question
  by changing two roles. Recognise underdetermined, infeasible and unsupported
  outcomes (optional section).
- **Prerequisites.** Lesson 01.
- **Time.** 60 minutes core, 20 optional.
- **Library shown.** `rk.Model()`, `edit()` and `commit()`, string equations (the
  operator form once, in an Under the hood aside), the Specification builder
  with `fix` and `free`, `solve`, `Outcome`, the `underdetermined` status,
  dimensional checks and coded diagnostics.
- **Finance taught.** Simple financial feasibility analysis (SFFA) front door
  and back door (Geltner et al., 2007, section 28.4.1). Mortgage constant
  against interest rate, loan-to-value, debt-service coverage, required rent
  against achievable rent, residual land value, and total cost as a proxy for
  value.
- **By hand once.** The mortgage constant formula, then the library helper.
- **Depends on.** [#141](https://github.com/daniel-fink/rangekeeper/issues/141),
  [#143](https://github.com/daniel-fink/rangekeeper/issues/143),
  [#144](https://github.com/daniel-fink/rangekeeper/issues/144),
  [#145](https://github.com/daniel-fink/rangekeeper/issues/145),
  [#146](https://github.com/daniel-fink/rangekeeper/issues/146),
  [#126](https://github.com/daniel-fink/rangekeeper/issues/126),
  [#127](https://github.com/daniel-fink/rangekeeper/issues/127),
  [#149](https://github.com/daniel-fink/rangekeeper/issues/149),
  [#151](https://github.com/daniel-fink/rangekeeper/issues/151),
  [#152](https://github.com/daniel-fink/rangekeeper/issues/152),
  [#154](https://github.com/daniel-fink/rangekeeper/issues/154) and #167
  (mortgage constant).

```python
b = rk.Model.build(name="Mixed-use feasibility")
b.values(land_cost="AUD", works_cost="AUD", leverage="ratio", coverage="ratio",
         mortgage_constant="1/year", operating_cost="AUD pa", rent_factor="ratio", ...)
b.equation("total_cost = land_cost + works_cost")
b.equation("effective_income = rent_factor * reference_income")
model = b.commit()

front = model.specify("Front door").fix(land_cost="20e6 AUD", ...).free("rent_factor")
rk.execution.solve(front)["rent_factor"]
back = front.fix(rent_factor=1).free("land_cost")
```

#### 03 Cases, debt and equity

- **Question.** How does the base plan perform in weak, reference and strong
  markets, with and without debt? Can we pay the bills when they fall due?
- **Project.** The property as one asset with a dated base plan: shared works in
  2027, Building A in 2028–2029 and Building B in 2030–2031, each opening the
  next January. Development budget, operations by use, renewal costs and sale.
- **Goals.** Build dated base-case cash flows from the plan. Tell the base plan
  from the base case. Declare three named market cases (weak, reference, strong)
  as cases of one batch Specification. Solve the batch and compare the cases in
  one table. For each case, report unlevered NPV, equity NPV and equity IRR at
  one fixed leverage. Then compare leverage levels on the reference case. Test
  construction funding: cash balance, headroom and the commitment gap.
- **Prerequisites.** Lessons 01 and 02.
- **Time.** 60 minutes core, 25 optional (amortisation schedule, more leverage
  levels).
- **Library shown.** Specification cases and batch solves, batch results in
  `Outcome`, growth from an opening date, NPV and IRR on dates, an account for
  the funding balance. Under the hood: `execute` into a store, the Run as
  evidence, replay in a fresh kernel and deterministic IDs.
- **Finance taught.** Base plan and base case, development budget (hard costs,
  soft costs, contingency), opening dates, unlevered and levered cash flows,
  loan-to-value, equity NPV, IRR and its failure cases, construction facility,
  headroom, committed but unpaid costs, and the do-nothing baseline.
- **By hand once.** One year of the funding balance, then the library account.
- **Depends on.** #144 (cases), #127, #167, #168, #147 (deterministic builds,
  aside) and two open questions for #201. First, can the cases reach the cash
  flows through the solve? That needs the DCF to be declared in the Model as
  equations, for example growth with a fixed rate. Second, the funding account
  and the commitment check need a library home.

```python
cases = {
    "weak": {"rent_growth": "1 %/year", "exit_cap_rate": "6 %"},
    "reference": {"rent_growth": "3 %/year", "exit_cap_rate": "5 %"},
    "strong": {"rent_growth": "5 %/year", "exit_cap_rate": "4.5 %"},
}
outcome = rk.execution.solve(base.cases(cases))
outcome.table("unlevered_npv", "equity_npv", "equity_irr", "peak_shortfall")
```

#### 04 Many market futures

- **Question.** How does the same plan perform across many possible market
  histories?
- **Project.** Lesson 03's base plan, unlevered and at one fixed leverage. The
  plan does not change.
- **Goals.** Tell named cases from generated paths. Build one path from trend,
  cycle, volatility, noise and shock components, one at a time. Generate and
  capture market paths with a seed. Run the plan across the paths with
  `Specification.across`. Read the distribution of NPV and funding shortfall.
  Explain why a plan valued on average inputs differs from the average of its
  results. Optional section: correlated hotel, residential and retail indices.
- **Prerequisites.** Lesson 03.
- **Time.** 60 minutes core, 30 optional.
- **Library shown.** `PathGenerator` and the built-in `MarketDynamics`,
  `MarketPaths` and its capture record, `Specification.across`, batch summaries
  in `Outcome`. The core path uses one property-wide rent index.
- **Finance taught.** Market cycles, volatility, mean reversion, rare shocks,
  the flaw of averages, target curves (value at risk and gain), correlation
  between use markets, and the rule not to apply market growth twice.
- **Path count.** An environment variable sets the count: small in CI, full
  locally.
- **Depends on.** [#135](https://github.com/daniel-fink/rangekeeper/issues/135)–[#138](https://github.com/daniel-fink/rangekeeper/issues/138),
  #127 and [#130](https://github.com/daniel-fink/rangekeeper/issues/130) (worker
  reuse, for run time).

```python
generator = rk.finance.MarketDynamics(trend="2 %/year", volatility=0.1, cycle_years=10)
paths = generator.generate(periods=plan_years, seed=2027, count=500)
outcome = rk.execution.solve(base.across(paths, assign={"rent_index": "rent_index"}))
outcome.distribution("equity_npv")
```

#### 05 When to commit

- **Question.** When should we buy the site, start Building B, or stop?
- **Project.** Lesson 03's plan and funding, on lesson 04's paths. The design
  does not change.
- **Options.** Three timing options, with no graph change:
  - **wait to start:** delay the purchase and shared works until an observed
    market value passes a threshold;
  - **conditional start of Building B:** start Building B only when observed
    conditions and funding allow, with a latest start date;
  - **abandon:** if conditions stay weak past a date, stop and sell the site by
    an explicit price rule.
- **Goals.** Write a decision rule with thresholds on observed values. Use only
  information available at the decision date. Check funding (from lesson 03)
  before an action. Read a decision trace. Compare the fixed plan with each
  strategy on the same paths, as paired differences. Include the cost of waiting
  and lost income. Tell rule parameters from realised actions.
- **Order.** Start with three readable histories (early recovery, long
  downturn, short recovery then decline). Then use the full path set.
- **Prerequisites.** Lessons 03 and 04.
- **Time.** 60 minutes core, 30 optional.
- **Library shown.** Policies with dated observations, availability, feasible
  actions and commitments; decision traces in the Run report; paired
  comparison across one `MarketPaths`.
- **Finance taught.** Real options in projects, option value as the difference
  between strategy distributions, the cost of delay, abandonment value,
  irreversible commitments and hindsight bias.
- **Depends on.** [#213](https://github.com/daniel-fink/rangekeeper/issues/213)
  (design), [#215](https://github.com/daniel-fink/rangekeeper/issues/215)
  (implementation) and [#139](https://github.com/daniel-fink/rangekeeper/issues/139)
  (availability). The lesson is not authored until #215 is verified.

```python
wait = base.policy("Wait to start").when("rent_index >= 1.05", do="start_shared_works")
start_b = wait.policy("Start B").when("rent_index >= 1.10 and funding_ok", do="start_b",
                                       latest=date(2033, 1, 1))
outcome = rk.execution.solve(start_b.across(paths, assign={"rent_index": "rent_index"}))
outcome.compare(rk.execution.solve(base.across(paths, ...)), "equity_npv")
```

#### 06 Project structure

- **Question.** Where do the income, costs and value of lessons 02–05 come from?
- **Project.** The property, now as its graph: 50 objects, spatial, service and
  grouping relationships, and geometry in the walkthrough viewer.
- **Goals.** Inspect entities, relationships and classifications. Choose a view
  for each question: spatial, service or grouping. Select objects with a
  filter. Roll up quantities and flows over a hierarchy. Pivot results by use
  and building. Count shared costs once. Trace a total to its contributors.
  Keep identities when names repeat. Finally, derive lesson 02's reference
  income from the graph and solve the back door again: the answer is the same,
  and now it traces to floors.
- **Prerequisites.** Lesson 02. Lessons 03–05 help but are not needed.
- **Time.** 60 minutes core, 20 optional.
- **Library shown.** Model lookups by code, `Filter`, quantity and flow
  rollups, pivots, coverage, `MissingReferenceError` and `model.edit()`. The
  walkthrough helpers show the geometry, graph views and sunbursts.
- **Finance taught.** A pro forma by component, the treatment of shared costs,
  the difference between a service link and a cost allocation, and coverage of
  missing values.
- **Depends on.** [#121](https://github.com/daniel-fink/rangekeeper/issues/121),
  [#156](https://github.com/daniel-fink/rangekeeper/issues/156)–[#160](https://github.com/daniel-fink/rangekeeper/issues/160),
  [#87](https://github.com/daniel-fink/rangekeeper/issues/87) and
  [#88](https://github.com/daniel-fink/rangekeeper/issues/88) (helpers). Open
  question for #201: how an equation refers to a rollup result.

```python
floors = model.find(rk.model.Filter(classification="floor"))
gfa = model.rollup("gfa", over="spatiallyContains", contributors=floors)
gfa.pivot(rows="building", columns="use")
feasibility = feasibility_model.edit().fix_from(gfa_by_use).commit()
```

#### 07 Policies and the model graph

- **Question.** Which design provisions are worth paying for now?
- **Project.** The property graph from lesson 06, with lesson 05's timing rules
  and lesson 04's paths.
- **Options.** Two structural options, as bounded design variants:
  - **Building B use switch:** a paid provision lets Building B open as hotel in
    place of residential. The variant changes cores, services, costs and income.
    It is not a new rent label;
  - **vertical expansion:** stronger structure, paid now, lets a building add
    floors later.
- **Goals.** Declare bounded design variants and their realised structures.
  Combine them with lesson 05's decision rules. Compare the fixed design, timing
  flexibility, each provision, and the combination, on the same paths. Include
  the provision cost on every path, also where the option is never used. Find
  the largest justified premium under a stated criterion, and state whether the
  policy stays fixed as the premium changes. Choose thresholds on one path set
  and test them on another. Report the delivered projects (completion dates and
  use mix) as well as value.
- **Prerequisites.** Lessons 05 and 06.
- **Time.** 60 minutes core, 30 optional.
- **Library shown.** Design variants, policies that select variants, rollups over
  realised structures and paired comparison.
- **Finance taught.** Flexibility in projects and on projects, the cost of a
  provision, the option premium, robustness and over-fitted thresholds. The
  best strategy tested is not a global optimum.
- **Depends on.** [#214](https://github.com/daniel-fink/rangekeeper/issues/214)
  (design), [#216](https://github.com/daniel-fink/rangekeeper/issues/216)
  (implementation) and #215. The lesson is not authored until #216 is verified.

```python
switch = model.edit().variant("B as hotel", replace={"Building B/residential": hotel_spaces},
                              provision="2.5e6 AUD").commit()
strategy = start_b.policy("Use switch").when("hotel_index > residential_index", do="B as hotel")
rk.execution.solve(strategy.across(paths, ...)).compare(fixed, "equity_npv", "completion", "use_mix")
```

### Developer-experience principles

These rules apply to every cell that a reader types. #201 tests each proposed cell
against them. Each break of a rule goes onto the gap list, not into a helper.

1. **One import.** `import rangekeeper as rk`, plus `datetime` and the helpers.
   The root stays small ([ADR-010](010-layers-and-packages.md)): only `rk.Model`,
   `rk.Specification`, `rk.Run` and `rk.Quantity`. Cells reach every other name through its
   public namespace, for example `rk.execution.solve`, `rk.quantity.isclose`,
   `rk.flow.Flow` and `rk.finance.npv`. The namespaces are `rk.duration`,
   `rk.profile`, `rk.flow`, `rk.finance`, `rk.model`, `rk.specification`, `rk.execution`,
   `rk.io`, `rk.errors` and `rk.quantity`. Cells never import `schema`, `shared`
   or private modules.
2. **Build, do not assemble.** Use `rk.Model()`, `model.edit()`, `commit()`
   and the chained Specification calls. Cells never write Metadata, a format version,
   `uuid4()` or a `.replace` chain.
3. **Equations are strings.** Write `b.equation("noi = coverage * debt_service")`.
   Lesson 02 shows the operator form once, in an Under the hood aside. Both
   forms are first-class and make the same records
   ([ADR-015](015-authoring.md#equations)).
4. **Refer by key or code.** Cells never paste a UUID. Under the hood asides use
   a namespace for reproducible IDs.
5. **Quantities, not unit strings.** Use `rk.Quantity("20e6 AUD")` or quantity text as
   an argument. Compare quantities and dimensions, never unit strings. Use the
   curated aliases (`pa`, `sqm`).
6. **The library does the finance.** NPV, IRR and PV use the same date basis.
   Growth starts from a date. Payment is a library call, and the mortgage constant
   is derived from it (#201, decision D19). An account balance is a cumulative sum
   of its transactions (decision D2). A new idea can be shown by hand once, checked, and then
   replaced by the library call.
7. **The library walks the graph.** Use views, filters, rollups and pivots.
   Cells never walk parents by hand.
8. **Read results in one step.** Use `outcome["key"]`, `outcome.status`,
   `outcome.raise_for_status()` and batch tables. Cells never load an output
   Model to read one value.
9. **Errors teach.** A diagnostic names the object by key and by code. Lesson 02's
   optional section shows the three failure outcomes on purpose.
10. **Helpers load and show.** Helpers load data, draw charts, graphs and
    geometry. They never select financial contributors, supply rates or hide an
    equation.
11. **One idea per cell.** A teaching cell has about 15 lines or fewer.
    Plain Python is for loading data, naming inputs and display.

| Problem in lesson 03 today | Rule | Library work |
| --- | --- | --- |
| Nested `equal(left=..., right=add(...))` | 3 | #143, #145, #163 |
| Nested `.replace` chains to revise a Model | 2 | #141, #142 |
| Hand-typed `schema_version` and Metadata | 2 | #146 |
| Seven deep imports | 1 | #52 |
| Mortgage constant, compounding loops, NPV as PV minus land, cash loop | 6 | #167, #168, account in `finance` |
| Index-based PV against date-based IRR | 6 | #164, #167 |
| Hand-written hierarchy walking | 7 | #121, #158, #160 |
| Unit-string comparisons such as `"meter ** 2"` | 5 | #148, #149, #150 |
| Pasted UUID literals | 4 | #147, #160 |
| Four hops to read a solved value | 8 | #126, #127 |

### Teaching conventions

**Keep from ADR-006:**

- the cycle of question, prediction, explanation, calculation, inspection and
  change;
- one object's calculation before a bulk operation;
- tables for exact values, charts for behaviour and diagrams for relationships,
  with consistent names, colours and units across the book;
- checks tied to claims: shared costs counted once, inverse values that
  reproduce a target, decisions that respect availability, and commitments that
  fit funding;
- optional sections for derivations, stochastic detail and policy searches;
- a common starting state, horizon and valuation convention for each comparison,
  with a do-nothing baseline and no double-counted terminal value;
- the source identities of the property, and separate spatial, service and
  grouping relationships;
- recorded provenance for every teaching assumption;
- each lesson runs from a fresh kernel, without an earlier lesson's state;
- redrawn concept diagrams where the 1.0 records differ from the old ones.

**Change from ADR-006:**

- seven lessons in order of principle, not six in order of project detail;
- lessons 02–05 use the property as one asset, and lesson 06 reveals the graph;
- debt, equity and IRR are core in lesson 03, not supplementary;
- the 1.0 terms: "market path" and "case" in place of "market scenario",
  "growth" in place of "projection", `fix`/`free` in place of lock/unlock,
  "rollup" in place of reduction, and `solve`/`execute` in place of `Executor`
  ([glossary](../concepts/glossary.md));
- the goals box, Under the hood and Finance note asides, and exercises with
  solutions in every lesson;
- notebooks have no outputs in git. The walkthrough CI job runs them
  ([#187](https://github.com/daniel-fink/rangekeeper/issues/187)) and the
  Zensical docs site renders them ([ADR-018](018-release-and-engineering.md)).
  The Jupyter Book 2 build and the `myst.yml` acceptance list retire;
- the lessons live on `develop` under `examples/walkthrough`
  ([#202](https://github.com/daniel-fink/rangekeeper/issues/202)), with file
  names `NN_slug.ipynb`;
- the walkthrough helpers own the charts, graph display and geometry viewer
  ([ADR-010](010-layers-and-packages.md)).

### Source rights

Third-party sources are cited by link and not copied
([ADR-019](019-walkthrough-direction.md)). Lessons use the books' methods with
the property's own numbers. Lesson 01 reproduces the small Table 1.1 example,
with a citation. The publisher gave permission to reuse the four figures below
with attribution.

| Source | Owner | Use | Treatment |
| --- | --- | --- | --- |
| Table 1.1, de Neufville and Geltner (2018) | Publisher | Lesson 01 | Original used with the publisher's permission and with attribution ([#76](https://github.com/daniel-fink/rangekeeper/issues/76)) |
| Table 4.1, same book | Publisher | Lesson 03 | Original used with the publisher's permission and with attribution (#76) |
| Figure 7.2, same book | Publisher | Lesson 04 | Original used with the publisher's permission and with attribution (#76) |
| Figure 9.1, same book | Publisher | Lesson 05 | Original used with the publisher's permission and with attribution (#76) |
| Text and Garden City chapters, same book | Publisher | Lessons 04, 05, 07 | Cite chapter and section by [DOI](https://doi.org/10.1002/9781119106470). The PDF is not in the repository and is not linked as a file |
| Chapter spreadsheets (`ch16.xlsx` to `ch23.xlsx`) and slides | Book authors | Method checks during preparation | Not committed and not redistributed. Cite the chapter and exhibit |
| Geltner et al. (2007), section 28.4.1, Exhibits 28-4 and 28-5 | Publisher | Lesson 02 | Cite edition, section and page. Do not reproduce the exhibits |
| Legacy Rangekeeper diagrams (`devModelGraph`, `devModelAssembly`, `modelProgression`, `objModel`) and logo | Rangekeeper author | Lessons 05 and 06 | Author's own work under the repository licence (MPL-2.0) |
| Mixed-use property design (Speckle project `c0f66c35e3`) | Rangekeeper author | Lessons 02–07 | Author's own design. The data package takes CC BY 4.0 ([#210](https://github.com/daniel-fink/rangekeeper/issues/210)) |
| Teaching assumptions (`assumptions.json`, `development.json`, later market and design inputs) | Rangekeeper author | Lessons 02–07 | Author's own. Each value names its origin |
| Speckle viewer bundle | Speckle | Lesson 06 helper | Keep its `SPECKLE-LICENSE` with the helper |

The data package records its provenance (#210):

- the manifest lists each file, its origin, its licence and its capture details;
- a licence file in the data folder states CC BY 4.0 for the property data;
- each teaching assumption names its origin: a legacy notebook cell, a book
  method or an author's choice;
- market paths carry their generator, parameters and seed in the `MarketPaths`
  capture record.

### Preparation decisions still open

| Decision | Needed before |
| --- | --- |
| Can lesson 03's cases reach the cash flows through the solve? Where do the funding account and commitment check live? | Resolved by #201: decisions D1 and D2 in the [proposed cells](../../examples/walkthrough/proposed/README.md#decisions) |
| How an equation refers to a rollup result | Resolved by #201: decision D3 in the [proposed cells](../../examples/walkthrough/proposed/README.md#decisions) |
| Generator parameters and correlations for the property's markets | Authoring lesson 04 |
| Thresholds, latest dates and the site sale price rule | Authoring lesson 05 |
| The hotel provision for Building B (cores, services, costs) and the expansion floors and premium | #214 and authoring lesson 07 |

### Delivery

1. #201 writes the proposed cells for every lesson and the gap list in #169.
2. The library work lands, and #213–#216 design and verify the executor
   features for lessons 05 and 07.
3. Each lesson is authored, run by CI from a fresh kernel and reviewed in the
   docs site.
4. Readers who have not seen the book do the usability test
   ([#212](https://github.com/daniel-fink/rangekeeper/issues/212)) before
   1.0.0rc1.

After this record merges, issues #203–#208 take the new lesson titles 01–06, and
a sub-issue of #209 tracks lesson 07.

## Alternatives and consequences

- **Keep ADR-006's order (graph in lesson 02, solve in lesson 03).** It follows
  the project's detail, but the library's main idea appears late, and a reader
  meets the most complex records before the simplest solve.
- **A simpler project for lessons 02–05.** It is easier to check by hand, but
  the reader changes project at lesson 06 and loses continuity.
- **Debt and equity as its own lesson.** It gives more room, but the book grows
  to eight lessons. Lesson 03's cases carry leverage naturally.
- **An integration lesson for developers.** It was rejected. Under the hood
  asides keep one path through the book.
- **Redraw all four figures.** It was rejected. The publisher gave permission
  to reuse the originals with attribution (#76).

The order puts the solve before the graph. Lessons 02–05 therefore need the
property's totals as data before lesson 06 derives them. Lesson 06 must show
that the two give the same answer. Lessons 05 and 07 wait for #215 and #216,
so 1.0.0 waits for them too ([ADR-019](019-walkthrough-direction.md)).

## Sources and related decisions

- [ADR-006: walkthrough curriculum](006-walkthrough-curriculum.md), superseded by
  this record. Its [notebook 02 outline](../history/plans/006-notebook-02-outline.md)
  and [notebook 03 outline](../history/plans/006-notebook-03-outline.md) are
  archived as source material for lessons 02, 03 and 06.
- [ADR-019: walkthrough direction](019-walkthrough-direction.md).
- [ADR-013](013-execution-and-extensions.md), [ADR-014](014-market-paths.md),
  [ADR-015](015-authoring.md) and [ADR-016](016-safety-defaults.md).
- [Mixed-use project brief](../guides/mixed-use-project.md) and
  [glossary](../concepts/glossary.md).
- de Neufville, R. and Geltner, D. (2018). *Flexibility and Real Estate
  Valuation under Uncertainty: A Practical Guide for Developers.* Wiley.
  [doi:10.1002/9781119106470](https://doi.org/10.1002/9781119106470).
- Geltner, D., Miller, N., Clayton, J. and Eichholtz, P. (2007). *Commercial Real
  Estate Analysis and Investments*, 2nd edition. Thomson South-Western.

Supersedes: ADR-006. Superseded by: none.
