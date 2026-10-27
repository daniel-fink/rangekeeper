# Walkthrough proposed cells

Issue: [#201](https://github.com/daniel-fink/rangekeeper/issues/201). Plan:
[ADR-020](../../../docs/decisions/020-walkthrough-plan-v2.md).

This folder holds the cells that a reader types in each of the seven lessons. They
are written against the 1.0 API that the decisions describe, not against today's
code. They are the acceptance test for the 1.x API: each place where the planned API
cannot support a cell is a gap, filed under
[#169](https://github.com/daniel-fink/rangekeeper/issues/169).

These files are not notebooks and do not run. The lessons
([#203](https://github.com/daniel-fink/rangekeeper/issues/203)–[#208](https://github.com/daniel-fink/rangekeeper/issues/208),
[#244](https://github.com/daniel-fink/rangekeeper/issues/244)) are authored from them
when the library work lands.

| Lesson | File | Core cells |
| --- | --- | --- |
| 01 Basic discounted cash flow | [01_basic_dcf.md](01_basic_dcf.md) | 20 |
| 02 Front door, back door | [02_front_door_back_door.md](02_front_door_back_door.md) | 21 + 4 optional |
| 03 Cases, debt and equity | [03_cases_debt_equity.md](03_cases_debt_equity.md) | 25 + 2 optional |
| 04 Many market futures | [04_market_futures.md](04_market_futures.md) | 17 + 2 optional |
| 05 When to commit | [05_when_to_commit.md](05_when_to_commit.md) | 18 + 2 optional |
| 06 Project structure | [06_project_structure.md](06_project_structure.md) | 25 + 1 optional |
| 07 Policies and the model graph | [07_policies_and_graph.md](07_policies_and_graph.md) | 20 + 5 optional |

Each lesson file has the goals box, the narrative outline, the cells, the exercises
with solutions, the checks and recap, the cell budget and a rule check. The rule
check tests each cell against the 11 developer-experience rules of ADR-020 and
names the gaps.

## Decisions

The maintainer made these choices during the proposed-cells pass. They resolve the open
preparation decisions of ADR-020 and the authoring shape that ADR-015 left to this
pass.

| ID | Question | Decision | Used in |
| --- | --- | --- | --- |
| D1 | Can lesson 03's cases reach the cash flows through the solve? | Yes. The Model declares the DCF as Flow equations: growth with a rate, the terminal value, NPV at a rate. A case fixes the rates, so the solve stays affine. One Model answers lessons 02–05 | 03, 04, 05 |
| D2 | Where do the funding accounts and the commitment check live? | Nowhere special: they are composition, in the rk 0.8 pattern of one account's overdraft drawing on the next. Equity is drawn as needed and spent first; the loan takes what the equity cannot cover: `funding_need = -(net_cash_flow + loan_interest).cumulative()`, `loan_principal = max(0 AUD, funding_need - equity)`, `loan_draws = loan_principal.diff()`, and `equity_cash_flow = net_cash_flow + loan_interest + loan_draws`. Income and the sale repay the loan first. What can still be spent is `equity_available` and `loan_available`; loan principal above the limit is a `shortfall`; committed but unpaid payments use `cumulative()`, `total()` and `since(on=)`. The word "headroom" is not used. There is no account class in `rk.finance` and no account declaration in the Model. Repeated use is served by a recipe in the how-to guides (#194), not by an API. Revised 2026-10-27: the bridge facility and the pro-rata loan are replaced by the cascade | 03, 04, 05, 07 |
| D3 | How does an equation refer to a rollup result? | A rollup declares a Value. Equations refer to it by key, as to any other value. The solve traces through the rollup to its contributors | 06, 07 |
| D4 | How does a batch report IRR, peak shortfall and other non-affine results? | Staged evaluation. `irr`, `min` and `max` are Model equations. The solve evaluates them after the affine stage, and verification checks them | 03, 04 |
| D5 | When do the inverse rewrites land? | In 1.0. A fixed IRR becomes an NPV row at that rate, and a bound on a minimum becomes one row for each period. The target-IRR land price is a core cell of lesson 03 | 03 |
| D6 | How is a Model made and changed? | One way each. `rk.Model(name=...)` makes an empty, immutable Model. `model.edit()` gives a `ModelDraft`; `commit()` checks it once and returns a new revision. There is no implicit entity: `draft.add_entity(code=, classification=)` makes one and `draft.entity(code=)` finds one. Values, Flows, equations and rollups are declared on the entity handle, and its equations use bare keys. Other entities use dotted paths, such as `building_a.income`. `root=` keeps its meaning in rollups | 02–07 |
| D7 | Must every unknown be named with `free()`? | No. A value that is not fixed is free. `free()` releases a value that was fixed before. An underdetermined solve names the free unknowns | 02–07 |
| D8 | Specification builder or chained calls? | Chained calls. `fix`, `free`, `cases`, `across` and `decide` each return a new immutable Specification, because each step is valid on its own. A Model change is often invalid until it is complete, so the Model uses a draft and `commit()` | 02–07 |
| D9 | How does a policy change the plan? | If a value can change, it belongs in the Specification. If it is part of the modelling, it belongs in the Model. The Model declares the equations between dates (lesson 03). A rule **decides** one value: it fixes the value on the first review date on which its condition holds. "Decided" is a role beside fixed and free. There is no separate action concept | 03, 05, 07 |
| D10 | How is a design variant declared? | Each option is its own Model revision. The Specification lists the alternatives, and the choice between them is a decided value. A provision cost is a fixed value in the Specification | 07 |
| D11 | Rates by use on each floor (lesson 06) | Keyed values (`by="use"`) and floor equations (`equations_for`). The reference income is a rollup of floor income, so income traces to floors | 06, 07 |
| D12 | Where does growth live, and what replaces "projection"? | A **profile** says how an amount develops over Periods. Profiles live in a new public namespace, `rk.profile`: growth profiles (`Constant`, `Linear`, `Compounding`) take an `initial=` amount; distribution profiles (`Uniform`, `SCurve`) take a `total=` amount. `rk.flow.Flow.from_profile(profile, periods=, initial= or total=)` makes the Flow. Growth is series maths, not finance, so it is not in `rk.finance` | 01, 03 |
| D13 | How does a reader make a Quantity? | `rk.Quantity("5 %")` or `rk.Quantity(0.05, "ratio")`, at the root beside the three documents: every layer uses it. The namespace that holds the unit system, the registry and `isclose` is `rk.quantity`, not `rk.units`, so "units" keeps one meaning: a unit string. `q()` and `Quantity.parse` are not added | 01–07 |
| D14 | Are arguments named? | Yes. Every Rangekeeper call and every function in an equation string names its arguments, and the API makes them keyword-only. Exceptions: lists of any length (`select`, `free`, `table`, `stream`, `equations`, `involving`), `min` and `max` in equations, Python built-ins, `datetime.date` and Polars calls | 01–07 |
| D15 | How are cells formatted? | With the project's `ruff format` (Black style): 88 columns, and a trailing comma after the last argument puts one argument per line. The pre-commit hook formats the lesson notebooks the same way, so the cell budgets count formatted lines. A cell split for length keeps its number with a letter (4, 4b). A long equation string is wrapped in parentheses | 01–07 |
| D16 | How are values declared, and how is a rate per year written? | One call for each value, naming its key and units: `site.value(key="land_cost", units="AUD")`, `site.flow(key="rent_index", units="ratio")`, `site.date(key="start_date")`. Keyed and timeline variants add `by=` and `periods=`. `units=` always means units; a date has none. A rate per year is `"% pa"`, for example `"7 % pa"`, not `"1/year"` | 01–07 |
| D17 | How is unit text written? | `per` divides (`"5 per sqm"`, `"750 AUD per sqm pa"`), `pa` means per year, and a count has a named unit (`"0.02 dwelling per sqm"`). A unit expression contains no numbers: Pint reads `"per 100 sqm"` as "÷ 100 × sqm", so the registry rejects it with a suggestion | 01–07 |
| D18 | Equations, expressions or constraints? | "Equation" is the reader's word: one relation that must hold, an equality or a bound. It is stored as a Constraint over Expressions; the glossary says so. `equations(..., formulation="Debt")` puts equations in a named Formulation, for display and traces; without it they join the entity's default Formulation | 02–07 |
| D19 | Is the mortgage constant a library function? | No. `rk.finance.payment(principal=, rate=, term=, frequency=)` is the one general loan calculation, like a spreadsheet's PMT with units. The mortgage constant is derived in the open: the payment per year on one dollar of loan, `(payment / rk.Quantity(text="1 AUD")).to(units="% pa")` | 02, 06 |
| D20 | Does a Model have a default timeline or unit system? | No. `rk.Model(name=, namespace=, description=)` takes neither. A Flow made from amounts by a profile or an event is declared with its `periods=`; every other Flow takes its Periods from its operands. The Model records the unit system in use (the curated registry, its version and any registered extensions) as a read-only `model.unit_system`; custom units go through the registry extension point | 03–07 |
| D21 | How are functions named in equation strings? | As in Python, with the `rk.` namespace: `rk.profile.uniform(...)`, `rk.flow.event(...)`, `rk.finance.npv(...)`. Operations on one Flow are methods: `operating.at(on=...)`, `project_cash.trim(end=...)`, `loan_draws.cumulative()`, `loan_available.min()`. Only `max(a, b)` stays bare. Eight words are reserved: `rk`, `max`, `never`, `and`, `or`, `not`, `true`, `false` | 03–07 |
| D22 | ~~How does a known-data Account take transactions?~~ | Withdrawn with the Account (D2) | — |
| D23 | When is something a library function, and when is it composition? | Compose when it is plain arithmetic on Flows: a balance is `cumulative()`, a repayment at sale is `rk.flow.event(amount=loan_principal.at(on=sale_date), on=sale_date)`, a terminal value is `shift`, divide and `trim`. Keep a library function when it carries a real convention: `rk.finance.interest(..., method=)` (compounding, day count), `npv`, `irr`, `payment`, profiles. So there is no `settle`, no account and no reversion helper | 01–07 |
| D24 | How much Python may a cell use? | Plain Python only. Cells use no `**` unpacking, no comprehensions or generator expressions, and no f-strings that build keys. A `for` loop may repeat a calculation, a display or a check over a short list; it never declares values (D16). Where a few cases differ, write each one out by key. A helper takes the batch it draws (`plot_target_curve(outcomes=, key=)`), so the cell does not build a mapping for it | 01–07 |
| D25 | How is a sequence of Periods held and named? | `rk.duration.Periods`: an ordered, gap-free sequence of Periods with one frequency, like rk 0.8's `PeriodIndex`. `Span.periods(frequency=)` returns one. An argument that takes one is always `periods=`; one date is `on=`; a move by whole periods is `by=` (`x.shift(by=-1)`); a Span is `span=`. `decide` takes its reviews as `periods=`, reviewed on the first day of each Period, with optional `earliest=` and `latest=` expressions in place of a window tuple. Not `Sequence`, which is Python's abstract type | 04–07 |
| D26 | Strings or enums for fixed words? | A fixed list of words that rangekeeper defines is an enum (`rk.duration.Frequency`, `rk.specification.Role`, `rk.execution.Criterion`, `rk.execution.ReviewResult`, `rk.execution.Status`, `rk.model.Direction`, `rk.errors.Code`). Words that the data or the user defines stay strings: classifications, labels, relationship names, case keys, formulation names, units and equation text. "This event does not happen" is the constant `rk.duration.NEVER` (a one-member enum inside), written `never` in equation text; it is not `None`, which means missing | 05–07 |
| D27 | How are results named in the cells? | A Specification is named for its question (`base`, `funded`, `strategy`); its result is the same name with `_outcome`, also for a batch; a dict of results ends in `_outcomes` | 03–07 |
| D28 | What stays as it is? | `rk.execution.solve(specification=)` stays a function (a method would make `specification` depend on `execution`); amounts such as `"2.5e6 AUD"` keep `e` notation; `fix` takes a bare number for a ratio (`coverage=1.25`) | 02–07 |
| D29 | How do path generators and relationships read? | Path generators are series maths, like profiles (D12), so they leave `finance` for `rk.market` (`Dynamics`, `Paths`). Correlations are given by name. Relationships have one snake_case name each (`contains`, `serves`); the other direction is `direction=rk.model.Direction.INCOMING`. The data package maps the source names | 04–07 |
| D30 | How are Outcomes compared? | With one call whatever their number: `rk.execution.compare(outcomes={name: outcome}, keys=[...], baseline=None)`. Without a baseline it shows the values side by side; with one it gives differences, paired by path when the Outcomes hold paths. There is no `Outcome.compare(other=)` and no `rk.execution.table`, so the call does not change between two Outcomes and more | 02–07 |

Two choices in the cells are open for review. They do not change the API shape:

- **Unit inference (G16).** Lesson 02 declares every value. From lesson 03, only
  inputs are declared, and the draft infers the units of the other values. Without
  inference, lesson 03 needs about 15 more lines of declarations.
- **Equity timing.** Equity is drawn as needed and spent before the loan (D2). A
  pro-rata structure after a minimum equity tranche is the common alternative; it
  changes only the `loan_principal` equation.

## Target API at a glance

This is the 1.0 surface that the cells use. Names that are already planned keep
their issue. Names with a gap ID are new.

### Root and namespaces

```python
import rangekeeper as rk

rk.Model, rk.Specification, rk.Run, rk.Quantity
(
    rk.quantity,
    rk.duration,
    rk.profile,
    rk.flow,
    rk.finance,
    rk.model,
    rk.specification,
    rk.execution,
    rk.io,
    rk.errors,
)
```

### Values and time

```python
(
    rk.Quantity(text="20e6 AUD"),
    rk.Quantity(text="7 % pa"),
    rk.Quantity(magnitude=1697.45, units="sqm"),
)  # #148, #149, G71
rk.quantity.isclose(actual=a, expected=b, abs="1 AUD")  # G06
span = rk.duration.Span.years(start=date(2001, 1, 1), count=10)  # G01
yearly = rk.duration.Frequency.YEAR
years = span.extend(years=1).periods(frequency=yearly)  # an rk.duration.Periods
years.start, years.end, years.frequency, len(years), years[-1]  # G01
rk.duration.NEVER  # "the event does not happen"; G50
flow = rk.flow.Flow(amounts={period: 100, date(2001, 1, 1): -50}, units="USD")  # G02
flow.at(on=date(2010, 1, 1)), flow.total(), -0.05 * flow + other_flow  # G03, G04
flow.shift(by=-1), flow.trim(span=period)  # G05
stream = rk.flow.Stream(flows={"PGI": pgi, "OPEX": opex}).with_flows(
    flows={"NOI": noi}
)  # G04
stream.select("PGI", "OPEX").sum(), stream.trim(span=span), stream.display()
flow.resample(
    frequency=rk.duration.Frequency.QUARTER, method=rk.flow.ResampleMethod.SPLIT
)  # #103
growth = rk.profile.Compounding(rate="2 % pa")  # G70
pgi = rk.flow.Flow.from_profile(
    profile=growth, periods=years, initial="100 USD", base=None, start=None, every=None
)
fees = rk.flow.Flow.from_profile(
    profile=rk.profile.SCurve(), periods=build, total="3e6 AUD"
)
```

### Finance on known data

```python
(
    rk.finance.pv(flow=flow, rate="7 % pa", on=date),
    rk.finance.npv(flow=flow, rate="7 % pa", on=date),
)  # #167, #164
rk.finance.payment(
    principal="1 AUD", rate="6 % pa", term="20 years", frequency=monthly
)  # #167: like PMT, with units
```

### Market paths

```python
paths = rk.market.Dynamics(trend="2 % pa", volatility="5 % pa").generate(
    periods=years, seed=1, count=500
)  # #135, #136, G29
rk.market.Dynamics.correlated(
    generators={"hotel_index": hotel, "residential_index": residential},
    correlation={"hotel_index": {"residential_index": 0.5}},
)  # G32
(
    paths.mean(name="rent_index"),
    paths[key]["rent_index"],
    paths.capture,
    paths.regenerate(seed=2),
)  # #137, G30, G69
```

### Model

```python
model = rk.Model(name="...", namespace=None, description=None)  # G08
model.unit_system  # recorded automatically; read-only
draft = model.edit(name=None)  # #141
site = draft.add_entity(code="property", classification="property")  # G08
site = draft.entity(code="property")  # find, in an edit
site.value(key="land_cost", units="AUD")  # G08
site.value(key="rent", units="AUD per sqm pa", by="use")  # G43
site.flow(key="rent_index", units="ratio", periods=years)  # G08
site.flow(key="use_index", units="ratio", periods=years, by="use")  # G43
site.date(key="start_date")  # G15
site.equation(equation="total_cost = land_cost + works_cost")
site.equations("...", "...", formulation="Debt")  # #145, G18, G72
draft.equations_for(
    filter=rk.model.Filter(classification="floor"),
    equations=["income = nla * rent[use]"],
)  # G43
site.rollup(
    key="reference_income",
    of="income",
    over="contains",
    root="property",
    contributors=floors,
)  # G44
site.replace(key=key, equation=eq)
site.add_to(key=key, term="b_site_sale")
site.remove(key=key)  # G27
draft.relabel(filter=filter, use="hotel")
draft.include(fragment=fragment)
draft.remove(entity=code)  # G61
model = draft.commit()
model.equations, model.equations.involving("start_date"), equation.text  # G10, G47
(
    model.entity(code="a_hotel_floor_1"),
    model.find(filter=rk.model.Filter(...)),
    model.view(over="serves"),
)  # #156, #160, G37
model.rollup(of="gfa", over="contains", root="property", contributors=floors)  # #158
model.rollup(
    of="volume",
    over="serves",
    direction=rk.model.Direction.INCOMING,
    roots=["building_a", "building_b"],
)  # G39, G40
(
    result.value,
    result.coverage,
    result.pivot(rows="building", columns="use"),
    result.trace(root="building_b"),
)  # #159, G41
rk.model.diff(before=a, after=b), rk.model.namespace(name="...")  # G62, #147
rk.model.compare(models={"Residential": a, "Hotel": b}, rollups=["b_cost"])  # G74
```

### Specification

```python
spec = model.specify(name="Front door").fix(
    land_cost="20e6 AUD", rent={"hotel": "750 AUD per sqm pa"}
)  # #144, G11, G45
spec.free("land_cost"), spec.roles, spec.on(model=new_model)  # G11, G21
spec.cases(cases={"weak": {...}, "strong": {...}}), spec.case(key="weak")  # G20, G75
spec.across(paths=paths)  # #138, G73: path series match Model values by key
spec.across(paths=use_paths, series={"use_index": {"hotel": "hotel_index"}})  # G73
spec.parameters(start_threshold=1.05).decide(
    key="start_date",
    when="rent_index >= start_threshold",
    periods=reviews,  # an rk.duration.Periods; reviewed on the first day of each
    earliest=None,  # or an expression, such as "shared_start + 1 year"
    latest=None,
    timing=rk.duration.PeriodTiming.FIRST,
    otherwise=rk.duration.NEVER,
)  # G49, G55, G57
(
    spec.fix(start_threshold=1.02),
    spec.rules,
    spec.with_rules(rules=rules),
)  # G57, G64, G65
spec.roles  # the role column holds rk.specification.Role: FIXED, FREE, DECIDED (G76)
spec.alternatives(b_design={"residential": residential, "hotel": hotel})  # G63
```

### Execution and evidence

```python
outcome = rk.execution.solve(specification=spec)  # #126, G12
(
    outcome["rent_factor"],
    outcome.status,
    outcome.raise_for_status(),
    outcome.free_unknowns,
)  # #127
(
    outcome.stream("land", "works"),
    outcome.case(key="weak"),
    outcome.table("npv", "irr"),
)  # G19, G20
(
    outcome.distribution(key="equity_npv").summary(),
    outcome.distribution(key="equity_npv").case(quantile=0.05),
    outcome.distribution(key="b_design").counts(),
    outcome.mean(),
)  # G31
gain.breakeven(
    key="provision", criterion=rk.execution.Criterion.QUANTILE, level=0.05
)  # G68
outcome.decisions().where(
    key="b_start", result=rk.execution.ReviewResult.DECIDED
)  # G51
outcome.status == rk.execution.Status.INFEASIBLE, error.code  # rk.errors.Code; G76
(
    outcome.trace(),
    outcome.decisions(),
    outcome.rollup(key="reference_income"),
    outcome.model,
)  # G51, G46
rk.execution.compare(outcomes={"Front": a, "Back": b}, keys=["land_cost"])  # G66
rk.execution.compare(
    outcomes={"fixed": f, "both": c}, keys=["equity_npv"], baseline="fixed"
).summary()  # G56, G66: paired by path against the baseline
(
    rk.execution.execute(specification=spec, store=store),
    rk.execution.replay(run=run, store=store),
)  # #126, G25
(
    rk.io.load(path=path),
    rk.io.save(document=document, path=path),
    rk.io.DirectoryStore(path=path),
)  # G26
```

### Equation strings

Equations use value keys, dotted paths (`building_a.income`),
keyed members (`rent[use]` by a label, `use_index["hotel"]` by name), quantity literals (`0 AUD`, `2 years`), the operators
`+ - * /`, the comparisons `= >= <= > <` and functions. Every function argument is
named (D14). Functions are called as in Python, with their `rk.` namespace (D21):

| Form | Meaning |
| --- | --- |
| `rk.profile.compounding(initial=, rate=, start=, every=, base=)`, `rk.profile.linear(initial=, ...)`, `rk.profile.constant(initial=, ...)` | A Flow made by a growth profile, over the Periods of the Flow it defines; zero before `start`; `every` for periodic amounts. `base=` is the date of the initial amount; it defaults to the first of those Periods |
| `rk.profile.uniform(total=, start=, years=)`, `rk.profile.scurve(total=, start=, years=)` | A Flow made by a distribution profile: a total divided over the years from a start date |
| `rk.flow.event(amount=, on=)` | A Flow with one amount on one date |
| `rk.finance.npv(flow=, rate=, on=)`, `rk.finance.irr(flow=)` | Valuation on one date basis (D4, D5 for `irr`) |
| `rk.finance.interest(balance=, rate=, method=)` | Interest on a balance under a stated convention (compounding, day count, opening or average balance) |
| `x.at(on=)`, `x.trim(start=, end=)`, `x.since(on=)`, `x.shift(by=)`, `x.cumulative()`, `x.diff()`, `x.total()`, `x.first()`, `x.last()`, `x.min()`, `x.max()` | Methods on a Flow `x`, as in Python: the amount of the period that contains a date; the part inside a span; the same Periods with zero before a date; each period's amount `by` periods away (`-1` gives the next period's; a rule cannot read a later amount, G53); running totals; each period's difference from the previous period, as in pandas (the reverse of `cumulative()`); the sum; the first and last amounts; and extremes (D4) |
| `max(a, b)` | The larger of two values. Like Python's built-in, its arguments are not named |

Each profile in `rk.profile` is also an equation function, under its own name in lower
case: `Compounding` is `rk.profile.compounding(...)`. A profile registered through the
extension point is an equation function too.

**Reserved words.** These cannot be value keys or entity codes; `commit()` rejects
them by name: `rk`, `max`, `never`, `and`, `or`, `not`, `true`, `false`. `never` in a
string is `rk.duration.NEVER` in Python (D26). Other words
are free, because their position decides what they mean: a unit word follows a number,
a method name follows a Flow, an argument name is inside a call, and a label key is
inside brackets.

**Quantity literals.** A literal is a number followed by unit words, joined only by
spaces and `per`: `1 year`, `0 AUD`, `0.02 dwelling per sqm`. `*` and `/` are never
part of a literal, so `1 year * rate` means `(1 year) * rate`. Put a complex unit in
brackets: `(750 AUD per sqm pa)`.

A Flow-valued equation applies period by period. A Flow made from amounts by a profile
or an event takes its Periods from its declaration; every other Flow takes them from
its operands, and Flows with different Periods do not combine. A scalar term applies
to every period (G18).

## Gap list

Each row is one issue under [#169](https://github.com/daniel-fink/rangekeeper/issues/169),
with milestone 1.0.0b1. The **Gaps** column gives the IDs that the lesson rule checks
use. **Issue** is filled in when the issue is filed.

| # | Issue | Title | Gaps | Layer | Cells | Related |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | — | `rk.duration.Periods` and Span conveniences: `years`, `extend`, `periods(frequency)` returning a `Periods` with `start`, `end`, `span`, `frequency`, `len`, indexing, `trim`, `extend(count=)`, `containing(on=)`, value equality and a compact document form | G01 | `duration` | 01·4; 03·3; 04·3; 05·6, 9–11; 07·7, 18 | #119 |
| 2 | — | Flow and Stream construction, lookup and arithmetic | G02–G04 | `flow` | 01·5–13; 03·17 | #103, #162 |
| 3 | — | Value equality and `rk.quantity.isclose` | G06 | `quantity`, `flow` | 01·12, 15, 21; 02·22 | #109, #117 |
| 4 | — | Flow methods: `shift(by=)`, `trim(span=)` with a Period, `cumulative()`, `diff()`, `total()`, `since(on=)`, `first()`, `last()`, `min()`, `max()` | G05 | `flow` | 01·11–12, 20; 03·13; 05·8 | #103, #162 |
| 5 | — | Staged solve: evaluate known blocks and non-affine Functions of determined values | G09 | `execution` | 02·6, 11; 03·13, 19 | #125, #129, #152 |
| 6 | — | Inverse rewrites: fixed `irr` and bounds on `min` | G22 | `execution` | 03·16 | #164, #167 |
| 7 | — | Function catalogue for equations, called as `rk.profile.*`, `rk.flow.*`, `rk.finance.*` and Flow methods, with the reserved words and the literal rule | G17 | `model`, `finance` | 03·6–8, 13; 05·10; 07·17 | #145, #163, #167, #168 |
| 8 | — | Flow-valued string equations, with Periods from declarations and operands | G18 | `model` | 03·6–8 | #145, #163 |
| 9 | — | Date values, date arithmetic, `rk.duration.NEVER` and `never` in equation text | G15, G50 | `quantity`, `model` | 03·5–6; 05·6–13 | #119 |
| 10 | — | `rk.Model(name=, namespace=, description=)`, read-only `model.unit_system`, `ModelDraft` with `add_entity` and `entity`, entity handles with `value(key=, units=)`, `flow(key=, units=)` and `date(key=)` | G08, G28 | `model` | 02·4; 03·5; 04·3 | #141, #142 |
| 11 | — | Infer units and shapes from equations | G16 | `model` | 03·5–8 | #151 |
| 12 | — | Equation keys, `replace`, `remove`, `add_to(key=, term=)`, `Equation.text`, `equations.involving` | G10, G27, G47 | `model` | 02 aside; 04·3; 05·2, 10; 06·24; 07·17 | #141, #145 |
| 13 | — | Keyed values, label indexing (`rent[use]`), members by name in equation text (`use_index["hotel"]`) and `equations_for` | G43, G45, G60 | `model`, `specification` | 06·19, 21; 07·3 | #121, #138, #141 |
| 14 | — | An entity's `rollup(key=, ...)` declares a Value; `Model.rollups()` | G44, G59 | `model` | 06·20; 07·2, 17 | #158 |
| 15 | — | Rollup facade: several roots, `direction=rk.model.Direction`, pivots by ancestor, `trace`, Outcome rollups, and `rk.model.compare(models=, rollups=)` (G74) | G39–G41, G46, G74 | `model`, `execution` | 06·11–15, 23; 07·6, 12 | #157, #158, #159 |
| 16 | — | Model inspection: `summary`, `entities`, `relationships`, `view`, `diff`; one snake_case name per relationship (`contains`, `serves`) | G35–G37, G62 | `model` | 06·2–8; 07·5 | #160 |
| 17 | — | Filter additions: `where=`, `within=`, `has=`, `name=` | G38 | `model` | 06·10, 16; 07·4, 6 | #121 |
| 18 | — | Error and diagnostic fields: ambiguous lookups, non-affine unknowns, broken constraints | G14, G42, G52 | `errors`, `execution` | 02·20–21; 05·7; 06·16–17, 24 | #134, #154, #155, #156 |
| 19 | — | Specification roles: unfixed values are free; `fix` input types; a later `fix` of a key replaces the earlier one; `roles` | G11 | `specification` | 02·10, 13; 03·exercises | #144 |
| 20 | — | `Specification.on(model)`; it refuses a fixed value that the new revision does not declare, so a removed value is freed first | G21 | `specification` | 03·14, 20; 04·4; 05·11, 13 | #144 |
| 21 | — | Cases and batch Outcomes: `cases(mapping)`, `Specification.case(key=)`, `Outcome.case`, `table`, `stream` | G19, G20, G75 | `specification`, `execution` | 02·15; 03·10–14 | #127, #144 |
| 22 | — | `solve` resolves the documents that made the Specification | G12 | `execution` | 02·11 onwards | #126 |
| 23 | — | `rk.execution.replay` and `Store.find_runs` | G25 | `execution`, `io` | 03·22–23 | #126, #176 |
| 24 | — | One-call document IO: `rk.io.load` and `rk.io.save`; a loaded Specification brings the documents it pins, so `solve` can resolve them | G26 | `io` | 04·2, 9; 05·2; 06·2, 22; 07·2, 7 | #112 |
| 25 | — | ~~`rk.finance.Account` with a limit; `with_transactions` returns a new Account with balance and headroom Flows~~ Withdrawn: funding is composition (D2) | G23 | — | — | — |
| 26 | — | ~~An entity's `account(key=, ..., commitments=)`~~ Withdrawn: funding is composition (D2) | G24 | — | — | — |
| 27 | — | Outcome distributions: `summary`, `quantile(level=)`, `probability`, `counts()`, `case(quantile=)`; `Outcome.mean()` for a batch | G31 | `execution` | 04·12–16; 05·16 | #127 |
| 28 | — | One comparison call for two or more Outcomes: `rk.execution.compare(outcomes=, keys=, baseline=None)`. Without a baseline it shows the values side by side; with one it gives differences paired by path, with `summary`, `by`, `by_case`, `where`, `select`, and `breakeven` and `best` with `criterion=rk.execution.Criterion` and `level=`. No `Outcome.compare` and no `rk.execution.table` (G13 merged) | G13, G56, G66, G68 | `execution` | 02·15; 03 Try it 1; 04·14; 05·14–17; 07·9, 14–18b | #138, #213, #214 |
| 29 | — | `rk.market.Paths` access and construction; `regenerate(seed=)` | G30, G33, G48, G69 | `market` | 04·10, 19; 05·4; 07·16 | #137 |
| 30 | — | `rk.market.Dynamics` parameters and correlated generators, with correlations given by name; `generate` requires `seed=` only when the dynamics have a random component (volatility, noise or shocks), and raises an error that names those components when it is missing; fixed dynamics take no seed | G29, G32 | `market` | 04·5–7, 17–18 | #136 |
| 31 | — | Rules that decide values: `decide(key=, when=, periods=, earliest=, latest=, timing=, otherwise=)`, traces, `decisions().where(key=, result=rk.execution.ReviewResult)`, availability errors with `key` | G49, G51, G53, G55, G64, G65, G67 | `specification`, `execution` | 05·6–12; 07·7–8, 13 | #102, #139, #213, #215 |
| 32 | — | Specification parameters for rule thresholds, fixed and swept like other values, and cases across paths | G57 | `specification` | 05·17; 07·13, 15 | #138 |
| 33 | — | Design options: `edit(name=)`, `relabel`, `include` and `Specification.alternatives` | G61, G63 | `specification`, `model` | 07·4, 7, 18 | #214, #216 |
| 34 | — | `rk.profile` namespace, growth and distribution profiles, and `Flow.from_profile` | G70 | `profile`, `flow` | 01·6; 03·7 (`compounding`, `uniform`) | #168, #131 |
| 35 | — | `rk.Quantity` at the root, text in the constructor, and the `rk.quantity` namespace | G71 | `quantity` | 01·2–3, 10, 17; 02·22; 03·24 | #148, #149, #150 |
| 36 | — | Named formulations: `equations(..., formulation=)`, a default Formulation for each entity, and equations grouped by formulation in displays and traces | G72 | `model` | 03·6–8, 13, 19b | #141, #145 |
| 37 | — | `across` matching: each path series fixes the Model value with the same key. `series=` maps a value whose key differs, or the members of a keyed value, to path series. A series that matches no value, a value that `series=` names but the paths lack, or a value with two sources raises an error that lists the path series and the Model keys | G73 | `specification` | 04·11; 05·5; 07·3b | #138 |
| 38 | — | Enums for the words rangekeeper defines: `rk.specification.Role`, `rk.execution.Criterion`, `rk.execution.ReviewResult`, `rk.execution.Status`, `rk.errors.Code`; `rk.model.Direction` made public (D26) | G76 | `specification`, `execution`, `errors`, `model` | 02·18–21; 05·8, 18; 06·13; 07·14 | #134, #154 |
| 39 | — | Piecewise equations with a free value: the solve picks the active side of each `max` or `min` (for example the equity-first cascade), solves the affine problem and verifies the choice; a wrong choice is reported, not hidden | G77 | `execution` | 03·16 | #125, #152, #164 |

Scope changes for existing issues:

- [#194](https://github.com/daniel-fink/rangekeeper/issues/194) (how-to guides) gains a
  recipe: a funding cascade (equity first, then a loan with a limit, interest and
  commitments), composed from `cumulative()`, `diff()`, `max`, `total()`,
  `since(on=)` and `rk.finance.interest` (D2).
- [#94](https://github.com/daniel-fink/rangekeeper/issues/94) (rename map and codemod)
  needs an entry: today's `calculations.account.Account` is not carried into 1.0.
  Its uses become `cumulative()` and `rk.finance.interest`.

- [#167](https://github.com/daniel-fink/rangekeeper/issues/167) provides NPV and a
  general `payment(principal=, rate=, term=, frequency=)`, like a spreadsheet's PMT
  with units. It has no separate mortgage-constant helper: the cells derive the
  constant as the payment per year on one dollar of loan (D19).

Acceptance tests for existing issues. These cells depend on
[#149](https://github.com/daniel-fink/rangekeeper/issues/149) (the curated unit
registry). Its tests must include:

- `rk.Quantity(text="7 % pa") == rk.Quantity(magnitude=0.07, units="1/year")`. With
  Pint's stock registry, `pa` is a picoyear, so this fails today.
- `per` is division: `rk.Quantity(text="750 AUD per sqm pa")` has the dimension
  currency / area / time.
- A number inside a unit expression fails with a suggestion:
  `rk.Quantity(text="0.5 dwelling per 100 sqm")` raises, and suggests
  `"0.005 dwelling per sqm"`. Stock Pint reads it as 0.005 dwelling × m².

Later ideas, not for 1.0:

- Include a saved Formulation as a fragment, with its keys mapped to the Model's keys,
  so a team can reuse a block of equations (for example a funding account) without a
  new API.

Not filed as gaps:

- **G07 (helpers).** The helpers load the data package with origins and draw
  charts, graphs, timelines and geometry. This is helper work for
  [#87](https://github.com/daniel-fink/rangekeeper/issues/87) and
  [#88](https://github.com/daniel-fink/rangekeeper/issues/88): `load_property` and
  `load_base_plan` (both return an object that displays a table and gives each
  Quantity by key, such as `plan["a_cost"]`), `load_fragment`, `data_path`,
  `path_count`, `show_equations`, `show_timeline`, `show_geometry`, `show_graph`,
  `show_decisions`, `plot_paths`, `plot_cash_flows`, `plot_flows`,
  `plot_target_curve` and `plot_decisions`. Notes for that work:
  - **Drawing stack.** Plotly (plotly.js, with a local bundle and the shared light
    and dark theme) draws the charts, the timeline and the equation network.
    vis-network (through PyVis, which leaves the library under ADR-010) draws the
    project graph. The Speckle viewer draws geometry.
  - **Geometry.** `show_geometry(name=)` draws a design from the data package
    without loading a Model (lesson 02). `show_geometry(model=, highlight=,
    color_by=)` draws a Model's entities, marks the entities in `highlight` and
    colours by a classification or a label (lesson 06). Give `name=` or `model=`,
    not both. The viewer reads the captured Speckle transport, not a server.
  - **Batch arguments.** A helper that draws several Outcomes takes the mapping and
    the key, for example `plot_target_curve(outcomes=, key=)` (D24).
  - **Signatures follow the 1.0 API.** Today's drafts on `develop` take today's
    records and a `path=`: `show_timeline(phases=, path=)` and
    `show_relations(formulation=, names=, specifications=, path=)`. The proposed
    cells call `show_timeline(plan=)` or `show_timeline(outcome=)` (the solved dates
    of one case, for lessons 03 and 05), and `show_equations(of=)` with a Model, a
    Specification or an Outcome. The helpers choose their own file paths.
  - **The docs site.** The helpers show local HTML files in iframes, served by a
    local server (`LocalDisplay`). A static Zensical page has no server, so the site
    build needs inline notebook output (for example Plotly's notebook renderer) or
    copies of the HTML files published with the pages
    ([#191](https://github.com/daniel-fink/rangekeeper/issues/191),
    [#187](https://github.com/daniel-fink/rangekeeper/issues/187)).
- **G54 (sequential solve with solved observations)** and **G58 (policy evidence)**.
  These are the core of [#213](https://github.com/daniel-fink/rangekeeper/issues/213)
  and [#215](https://github.com/daniel-fink/rangekeeper/issues/215).
- **G34** was merged into G61.

## Data preparation

These are inputs for authoring, not API gaps:

- The 1.0 data package gives entities readable unique codes, such as
  `a_hotel_floor_1`, and `use` labels on floors
  ([#210](https://github.com/daniel-fink/rangekeeper/issues/210)).
- The data package maps the source relationship names to one snake_case name each:
  `spatiallyContains` becomes `contains`, and `servedBy` becomes `serves` read in the
  other direction (D29).
- CI writes the documents that later lessons load from the cells of earlier lessons,
  with a namespace, and checks that they do not change: `02_feasibility.model.json`,
  `02_back_door.specification.json`, `03_base_case.specification.json` (lesson 03's
  `funded` Specification), `04_base_case.specification.json` (lesson 04's `base`, on
  the Model with the rent index),
  `03_base_plan.model.json`, `04_base_plan_on_paths.model.json`,
  `04_rent_index.paths.json`, `04_use_indices.paths.json` and
  `05_strategy.specification.json`. `07_property_plan.model.json` joins the graph of
  lesson 06 with the dated plan of lessons 03–05.
- The base plan gives `equity` and `loan_limit` (in place of `bridge_limit`) for lesson
  03's funding cascade (D2).
- Lesson 05 needs the three readable histories (`05_histories.paths.json`).
- Lesson 07 needs the Building B hotel fragment and the Building A expansion fragment
  ([#214](https://github.com/daniel-fink/rangekeeper/issues/214)). If the fragments
  carry geometry, lesson 07 can show the realised design of one path.

## Changes from the ADR-020 sketches

The sketches in ADR-020 were not binding. The cells differ from them here:

- Growth is a profile, `rk.flow.Flow.from_profile(rk.profile.Compounding(...), ...)`,
  not `rk.flow.Flow.grow` (D12). This amends
  [ADR-010](../../../docs/decisions/010-layers-and-packages.md) and
  [ADR-012](../../../docs/decisions/012-naming-and-glossary.md), which put growth in
  `finance`.
- Quantities are `rk.Quantity("20e6 AUD")`, not `rk.units.q(...)`, and the namespace is
  `rk.quantity` (D13).
- Values are declared one call each, `site.value(key=, units=)` (D16), not as
  `values(land_cost="AUD", ...)`, and rates per year are `"% pa"`, not `"%/year"`.
- Policies use `Specification.decide(key, ...)` (D9), not `base.policy(...).when(..., do=...)`.
- Lesson 06 declares the rollup as a Value (D3), not `edit().fix_from(...)`.
- Lesson 07 uses separate Model revisions for options (D10), not
  `edit().variant(...)`.
