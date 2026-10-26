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
| 02 Front door, back door | [02_front_door_back_door.md](02_front_door_back_door.md) | 17 + 4 optional |
| 03 Cases, debt and equity | [03_cases_debt_equity.md](03_cases_debt_equity.md) | 23 |
| 04 Many market futures | [04_market_futures.md](04_market_futures.md) | 16 + 2 optional |
| 05 When to commit | [05_when_to_commit.md](05_when_to_commit.md) | 17 + 1 optional |
| 06 Project structure | [06_project_structure.md](06_project_structure.md) | 23 + 1 optional |
| 07 Policies and the model graph | [07_policies_and_graph.md](07_policies_and_graph.md) | 16 + 2 optional |

Each lesson file has the goals box, the narrative outline, the cells, the exercises
with solutions, the checks and recap, the cell budget and a rule check. The rule
check tests each cell against the 11 developer-experience rules of ADR-020 and
names the gaps.

## Decisions

The maintainer made these choices during the proposed-cells pass. They resolve the open
preparation decisions of ADR-020 and the builder shape that ADR-015 left to this
pass.

| ID | Question | Decision | Used in |
| --- | --- | --- | --- |
| D1 | Can lesson 03's cases reach the cash flows through the solve? | Yes. The Model declares the DCF as Flow relations: growth with a rate, reversion, NPV at a rate. A case fixes the rates, so the solve stays affine. One Model answers lessons 02–05 | 03, 04, 05 |
| D2 | Where do the funding account and the commitment check live? | Both places. `rk.finance.Account` calculates on known data (the "by hand once, then the library" cell). `ModelBuilder.account` declares the balance, headroom and committed payments as relations, so cases, paths and rules can use them | 03, 05 |
| D3 | How does an equation refer to a rollup result? | A rollup declares a Value. Equations refer to it by key, as to any other value. The solve traces through the rollup to its contributors | 06, 07 |
| D4 | How does a batch report IRR, peak shortfall and other non-affine results? | Staged evaluation. `irr`, `min` and `max` are Model relations. The solve evaluates them after the affine stage, and verification checks them | 03, 04 |
| D5 | When do the inverse rewrites land? | In 1.0. A fixed IRR becomes an NPV row at that rate, and a bound on a minimum becomes one row for each period. The target-IRR land price is a core cell of lesson 03 | 03 |
| D6 | Where do the builder's values live while the property is one asset? | On an implicit subject entity: `rk.Model.build(name=..., subject="property")`. Equations use bare keys. Other entities use dotted paths, such as `funding.headroom` | 02–07 |
| D7 | Must every unknown be named with `free()`? | No. A value that is not fixed is free. `free()` releases a value that was fixed before. An underdetermined solve names the free unknowns | 02–07 |
| D8 | Specification builder or chained calls? | Chained calls. `fix`, `free`, `cases`, `across` and `decide` each return a new immutable Specification. Only the Model uses a builder and `commit()` | 02–07 |
| D9 | How does a policy change the plan? | If a value can change, it belongs in the Specification. If it is part of the modelling, it belongs in the Model. The Model declares the relations between dates (lesson 03). A rule **decides** one value: it fixes the value on the first review date on which its condition holds. "Decided" is a role beside fixed and free. There is no separate action concept | 03, 05, 07 |
| D10 | How is a design variant declared? | Each option is its own Model revision. The Specification lists the alternatives, and the choice between them is a decided value. A provision cost is a fixed value in the Specification | 07 |
| D11 | Rates by use on each floor (lesson 06) | Keyed values (`by="use"`) and floor equations (`equations_for`). The reference income is a rollup of floor income, so income traces to floors | 06, 07 |
| D12 | Where does growth live, and what replaces "projection"? | A **profile** says how an amount develops over Periods. Profiles live in a new public namespace, `rk.profile`: growth profiles (`Constant`, `Linear`, `Compounding`) take an `initial=` amount; distribution profiles (`Uniform`, `SCurve`) take a `total=` amount. `rk.flow.Flow.from_profile(profile, periods=, initial= or total=)` makes the Flow. Growth is series maths, not finance, so it is not in `rk.finance` | 01, 03 |

Two choices in the cells are open for review. They do not change the API shape:

- **Unit inference (G16).** Lesson 02 declares every value. From lesson 03, only
  inputs are declared, and the builder infers the units of the other values. Without
  inference, lesson 03 needs about 15 more lines of declarations.
- **Funding structure.** Lesson 03 uses equity and an overdraft-style bridge limit.
  `development.json` also has a fixed draw schedule. Authoring picks one.

## Target API at a glance

This is the 1.0 surface that the cells use. Names that are already planned keep
their issue. Names with a gap ID are new.

### Root and namespaces

```python
import rangekeeper as rk
rk.Model, rk.Specification, rk.Run
rk.duration, rk.profile, rk.flow, rk.finance, rk.model, rk.specification, rk.execution, rk.io, rk.errors, rk.units
```

### Values and time

```python
rk.units.q("20e6 AUD"), rk.units.q("7 %/year"), rk.units.q("1200 USD pa")        # #148, #149
rk.units.isclose(a, b, abs="1 AUD")                                                  # G06
span = rk.duration.Span.years(start=date(2001, 1, 1), count=10)                      # G01
span.extend(years=1).periods("year")
flow = rk.flow.Flow({period: 100, date(2001, 1, 1): -50}, units="USD")              # G02
flow.at(date(2010, 1, 1)), flow.total(), -0.05 * flow + other_flow                  # G03, G04
stream = rk.flow.Stream({"PGI": pgi, "OPEX": opex}) | {"NOI": noi}                   # G04
stream.select("PGI", "OPEX").sum(), stream.trim(span), stream.display()
flow.resample("quarter", method=rk.flow.ResampleMethod.SPLIT)                       # #103
growth = rk.profile.Compounding(rate="2 %/year")                                     # G70
pgi = rk.flow.Flow.from_profile(growth, periods=years, initial="100 USD", base=None, start=None, every=None)
fees = rk.flow.Flow.from_profile(rk.profile.SCurve(), periods=build, total="3e6 AUD")
```

### Finance on known data

```python
rk.finance.reversion(nacf, cap_rate="5 %", at=holding)                              # G05
rk.finance.pv(flow, rate="7 %/year", on=date), rk.finance.npv(...), rk.finance.irr(flow)        # #167, #164
rk.finance.mortgage_constant(rate="6 %/year", term="20 years", payments_per_year=12) # #167
rk.finance.Account(opening=..., limit=...).post(transactions)                       # G23
rk.finance.MarketDynamics(trend="2 %/year", ...).generate(periods=, seed=, count=)   # #135, #136, G29
rk.finance.MarketDynamics.correlated({...}, correlation=[[...]])                    # G32
paths.mean("rent_index"), paths[key]["rent_index"], paths.capture, paths.generator   # #137, G30, G69
```

### Model

```python
b = rk.Model.build(name="...", subject="property", timeline=years, namespace=None)  # #141, G08
b.values(land_cost="AUD", start_date="date"), b.flows(rent_index="ratio")           # G08, G15
b.values(rent="AUD/sqm pa", by="use")                                               # G43
b.equation("total_cost = land_cost + works_cost"); b.equations("...", "...")        # #145, G18
b.equations_for(rk.model.Filter(classification="floor"), "income = nla * rent[use]")  # G43
b.rollup("reference_income", of="income", over="spatiallyContains", root="property",
         contributors=rk.model.Filter(classification="floor"))                      # G44
b.account("funding", opening="equity", limit="bridge_limit",
          transactions="land + works", commitments={"a_works": "a_start"})          # G24
model = b.commit()
e = model.edit(name=None); e.replace(key, eq); e.remove(key); e.extend(key, terms)  # G27
e.relabel(filter, use="hotel"); e.include(fragment)                                 # G61
model.equations, model.equations.involving("start_date"), equation.text            # G10, G47
model.entity("a_hotel_floor_1"), model.find(rk.model.Filter(...)), model.view("serves")   # #156, #160, G37
model.rollup("gfa", over="spatiallyContains", root="property", contributors=...)    # #158, G39
result.value, result.coverage, result.pivot(rows="building", columns="use"), result.trace("building_b")  # #159, G41
rk.model.diff(a, b), rk.model.namespace("...")                                      # G62, #147
```

### Specification

```python
spec = model.specify("Front door").fix(land_cost="20e6 AUD", rent={"hotel": "750 AUD/sqm pa"})  # #144, G11, G45
spec.free("land_cost"), spec.roles, spec.on(new_model)                              # G11, G21
spec.cases({"weak": {...}, "strong": {...}})                                        # G20
spec.across(paths, assign={"rent_index": "rent_index"})                             # #138
spec.decide("start_date", when="rent_index >= 1.05", review="year",
            window=(date(2027, 1, 1), date(2031, 1, 1)), otherwise="never")         # G49
spec.parameters(start_threshold=1.05), spec.rules, spec.with_rules(rules)           # G57, G64, G65
spec.alternatives(b_design={"residential": residential, "hotel": hotel})            # G63
```

### Execution and evidence

```python
outcome = rk.execution.solve(spec)                                                  # #126, G12
outcome["rent_factor"], outcome.status, outcome.raise_for_status(), outcome.free_unknowns  # #127
outcome.stream("land", "works"), outcome.case("weak"), outcome.table("npv", "irr")  # G19, G20
outcome.distribution("equity_npv").summary(), outcome.compare(other, "equity_npv")  # G31, G56
outcome.trace(), outcome.decisions(), outcome.rollup("reference_income"), outcome.model  # G51, G46
rk.execution.table({"Front": a, "Back": b}, "land_cost")                            # G13
rk.execution.compare({"fixed": f, "both": c}, "equity_npv", baseline="fixed")       # G66
rk.execution.execute(spec, store), rk.execution.replay(run, store)                  # #126, G25
rk.io.load(path), rk.io.save(document, path), rk.io.DirectoryStore(path)            # G26
```

### Equation strings

Equations use value keys, dotted paths (`funding.headroom`), keyed members
(`rent[use]`), quantity literals (`0 AUD`, `2 years`), the operators `+ - * /`, the
comparisons `= >= <= > <` and the functions in G17. The functions use the same names
and keywords as `rk.finance` and `rk.flow`. `grow` and `spread` are the two common
profiles: `grow(x, rate=r)` is `Flow.from_profile(rk.profile.Compounding(rate=r),
initial=x)`, and `spread(x, ...)` is `Flow.from_profile(rk.profile.Uniform(), total=x)`:

| Function | Meaning |
| --- | --- |
| `grow(amount, rate=, base=, start=, every=)` | Growth on the Model timeline from a base date; zero before `start`; `every` for periodic amounts |
| `spread(amount, start=, years=)` | An amount divided evenly over the years from a start date |
| `event(amount, on=)` | One amount on one date |
| `at(flow, date)` | The amount of the period that contains a date |
| `trim(flow, start=, end=)` | The part of a Flow inside a span |
| `cumulative(flow)`, `interest(balance, rate=)`, `settle(balance, on=)` | Balances, interest on the opening balance, and repayment of a balance |
| `reversion(flow, cap_rate=, at=)` | Next period's amount divided by the cap rate, on a date |
| `npv(flow, rate=, on=)`, `irr(flow)` | Valuation on one date basis (D4, D5 for `irr`) |
| `min(flow)`, `max(a, b)` | Extremes (D4) |
| `next(flow)` | The next period's amount; a rule cannot use it (G53) |

A Flow-valued equation applies period by period on the Model timeline. A scalar
term applies to every period (G18).

## Gap list

Each row is one issue under [#169](https://github.com/daniel-fink/rangekeeper/issues/169),
with milestone 1.0.0b1. The **Gaps** column gives the IDs that the lesson rule checks
use. **Issue** is filled in when the issue is filed.

| # | Issue | Title | Gaps | Layer | Cells | Related |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | — | Span conveniences: `years`, `extend`, `periods("year")` | G01 | `duration` | 01·4; 03·3 | #119 |
| 2 | — | Flow and Stream construction, lookup and arithmetic | G02–G04 | `flow` | 01·5–13; 03·17 | #103, #162 |
| 3 | — | Value equality and `rk.units.isclose` | G06 | `units`, `flow` | 01·11, 14, 20; 02·22 | #109, #117 |
| 4 | — | `rk.finance.reversion` | G05 | `finance` | 01·11; 03·8 | #167 |
| 5 | — | Staged solve: evaluate known blocks and non-affine Functions of determined values | G09 | `execution` | 02·6, 11; 03·13, 19 | #125, #129, #152 |
| 6 | — | Inverse rewrites: fixed `irr` and bounds on `min` | G22 | `execution` | 03·16 | #164, #167 |
| 7 | — | Function catalogue for equations, named as in `rk.profile`, `rk.flow` and `rk.finance` | G17 | `model`, `finance` | 03·6–8, 13; 05·10; 07·17 | #145, #163, #167, #168 |
| 8 | — | Flow-valued string equations on the Model timeline | G18 | `model` | 03·6–8 | #145, #163 |
| 9 | — | Date values, date arithmetic and `never` | G15, G50 | `units`, `model` | 03·5–6; 05·6–13 | #119 |
| 10 | — | Builder: `subject`, `timeline`, `values(**units)`, `flows(**units)` | G08, G28 | `model` | 02·4; 03·5; 04·3 | #141, #142 |
| 11 | — | Infer units and shapes from equations | G16 | `model` | 03·5–8 | #151 |
| 12 | — | Equation keys, `replace`, `remove`, `extend`, `Equation.text`, `equations.involving` | G10, G27, G47 | `model` | 02 aside; 04·3; 05·2, 10; 06·24; 07·17 | #141, #145 |
| 13 | — | Keyed values, label indexing and `equations_for` | G43, G45, G60 | `model`, `specification` | 06·19, 21; 07·3 | #121, #138, #141 |
| 14 | — | `ModelBuilder.rollup` declares a Value; `Model.rollups()` | G44, G59 | `model` | 06·20; 07·2, 17 | #158 |
| 15 | — | Rollup facade: several roots, pivots by ancestor, `trace`, Outcome rollups | G39–G41, G46 | `model`, `execution` | 06·11–15, 23; 07·6, 12 | #157, #158, #159 |
| 16 | — | Model inspection: `summary`, `entities`, `relationships`, `view`, `diff` | G35–G37, G62 | `model` | 06·2–8; 07·5 | #160 |
| 17 | — | Filter additions: `where=`, `within=`, `has=`, `name=` | G38 | `model` | 06·10, 16; 07·4, 6 | #121 |
| 18 | — | Error and diagnostic fields: ambiguous lookups, non-affine unknowns, broken constraints | G14, G42, G52 | `errors`, `execution` | 02·20–21; 05·7; 06·16–17, 24 | #134, #154, #155, #156 |
| 19 | — | Specification roles: unfixed values are free; `fix` input types; `roles` | G11 | `specification` | 02·10, 13 | #144 |
| 20 | — | `Specification.on(model)` | G21 | `specification` | 03·14, 20; 05·11, 13 | #144 |
| 21 | — | Cases and batch Outcomes: `cases(mapping)`, `case`, `table`, `stream`, `rk.execution.table` | G13, G19, G20 | `specification`, `execution` | 02·15; 03·10–14 | #127, #144 |
| 22 | — | `solve` resolves the documents that made the Specification | G12 | `execution` | 02·11 onwards | #126 |
| 23 | — | `rk.execution.replay` and `Store.find_runs` | G25 | `execution`, `io` | 03·22–23 | #126, #176 |
| 24 | — | One-call document IO: `rk.io.load` and `rk.io.save` | G26 | `io` | 04·2, 9; 05·2; 06·2, 22; 07·2, 7 | #112 |
| 25 | — | `rk.finance.Account` with a limit and headroom | G23 | `finance` | 03·18 | — |
| 26 | — | `ModelBuilder.account` with commitments | G24 | `model` | 03·19; 05·9 | — |
| 27 | — | Outcome distributions | G31 | `execution` | 04·12–16; 05·16 | #127 |
| 28 | — | Paired comparison of Outcomes | G56, G66, G68 | `execution` | 05·14–17; 07·9, 14–16 | #138, #213, #214 |
| 29 | — | MarketPaths access and construction | G30, G33, G48, G69 | `finance` | 04·10, 19; 05·4; 07·16 | #137 |
| 30 | — | MarketDynamics parameters and correlated generators | G29, G32 | `finance` | 04·5–7, 17–18 | #136 |
| 31 | — | Rules that decide values: `decide`, traces, availability errors | G49, G51, G53, G55, G64, G65, G67 | `specification`, `execution` | 05·6–12; 07·7–8, 13 | #102, #139, #213, #215 |
| 32 | — | Specification parameters, and cases across paths | G57 | `specification` | 05·17; 07·13, 15 | #138 |
| 33 | — | Design options: `edit(name=)`, `relabel`, `include` and `Specification.alternatives` | G61, G63 | `specification`, `model` | 07·4, 7, 18 | #214, #216 |
| 34 | — | `rk.profile` namespace, growth and distribution profiles, and `Flow.from_profile` | G70 | `profile`, `flow` | 01·6; 03·7 (`grow`, `spread`) | #168, #131 |

Not filed as gaps:

- **G07 (helpers).** The helpers load the data package with origins and draw
  charts, graphs, timelines and geometry. This is helper work for
  [#87](https://github.com/daniel-fink/rangekeeper/issues/87) and
  [#88](https://github.com/daniel-fink/rangekeeper/issues/88): `load_property`,
  `load_base_plan`, `load_fragment`, `data_path`, `path_count`, `show_relations`,
  `show_timeline`, `show_geometry`, `show_graph`, `show_decisions`, `plot_paths`,
  `plot_cash_flows`, `plot_funding`, `plot_target_curve`, `plot_decisions`.
- **G54 (sequential solve with solved observations)** and **G58 (policy evidence)**.
  These are the core of [#213](https://github.com/daniel-fink/rangekeeper/issues/213)
  and [#215](https://github.com/daniel-fink/rangekeeper/issues/215).
- **G34** was merged into G61.

## Data preparation

These are inputs for authoring, not API gaps:

- The 1.0 data package gives entities readable unique codes, such as
  `a_hotel_floor_1`, and `use` labels on floors
  ([#210](https://github.com/daniel-fink/rangekeeper/issues/210)).
- CI writes the documents that later lessons load from the cells of earlier lessons,
  with a namespace, and checks that they do not change: `02_feasibility.model.json`,
  `03_base_plan.model.json`, `04_base_plan_on_paths.model.json`,
  `04_rent_index.paths.json`, `04_use_indices.paths.json` and
  `05_strategy.specification.json`. `07_property_plan.model.json` joins the graph of
  lesson 06 with the dated plan of lessons 03–05.
- Lesson 05 needs the three readable histories (`05_histories.paths.json`).
- Lesson 07 needs the Building B hotel fragment and the Building A expansion fragment
  ([#214](https://github.com/daniel-fink/rangekeeper/issues/214)).

## Changes from the ADR-020 sketches

The sketches in ADR-020 were not binding. The cells differ from them here:

- Growth is a profile, `rk.flow.Flow.from_profile(rk.profile.Compounding(...), ...)`,
  not `rk.flow.Flow.grow` (D12). This amends
  [ADR-010](../../../docs/decisions/010-layers-and-packages.md) and
  [ADR-012](../../../docs/decisions/012-naming-and-glossary.md), which put growth in
  `finance`.
- Policies use `Specification.decide(key, ...)` (D9), not `base.policy(...).when(..., do=...)`.
- Lesson 06 declares the rollup as a Value (D3), not `edit().fix_from(...)`.
- Lesson 07 uses separate Model revisions for options (D10), not
  `edit().variant(...)`.
