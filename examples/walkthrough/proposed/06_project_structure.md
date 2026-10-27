# Lesson 06: Project structure (proposed cells)

Issue: [#208](https://github.com/daniel-fink/rangekeeper/issues/208). Plan:
[ADR-020 §06](../../../docs/decisions/020-walkthrough-plan-v2.md#06-project-structure).
API conventions and the gap list: [README](README.md).

Decision used here (D3 in the [README](README.md#decisions)): a rollup declares a
Value, and equations refer to it by key.

## Goals box

> **Question.** Where do the income, costs and value of lessons 02–05 come from?
>
> **You will learn to:**
>
> 1. inspect entities, relationships and classifications, and choose a view for each
>    question: spatial, service or grouping;
> 2. select objects with a filter, and roll up quantities over a hierarchy;
> 3. pivot results by building and use, and count shared items once;
> 4. trace a total to its contributors, and keep identities when names repeat;
> 5. derive lesson 02's reference income from the floors, and get the same answer.
>
> **Before you start.** Lesson 02. Lessons 03–05 help, but you do not need them.
>
> **Time.** 60 minutes core, 20 minutes optional.
>
> **Not in this lesson.** Changing the structure (lesson 07).

## 1. The property as a graph

Narrative: in lessons 02–05 the property was one asset with totals. Lesson 02 showed
its design as one picture. Here is the same property as a graph: 50 objects, with
spatial, service and grouping relationships. Each object has its own geometry.

```python
# cell 1
import rangekeeper as rk
import helpers
```

```python
# cell 2
graph = rk.io.load(path=helpers.data_path(name="mixed_use_property.model.json"))
graph.summary()  # counts of entities, relationships and classifications
```

```python
# cell 3
helpers.show_geometry(model=graph, color_by="classification")
```

## 2. Entities, values and relationships

Narrative: an entity is one thing in the project. It has a code, a name, a
classification and its own values. Look up one floor by its code.

```python
# cell 4
graph.entities()  # code, name, classification and labels
```

```python
# cell 5
floor = graph.entity(code="a_hotel_floor_1")
floor.values  # gfa, perimeter, floor-to-floor height, level
```

```python
# cell 6
graph.relationships(entity=floor)  # contained by its space; served by cores and plant
```

## 3. One graph, three views

Narrative: each question needs its own relationships. "What does Building A
contain?" is a spatial question. "What does the shared plant serve?" is a service
question. A service link is not a cost allocation.

```python
# cell 7
spatial = graph.view(over="spatiallyContains")
helpers.show_graph(view=spatial)
```

```python
# cell 8
services = graph.view(over="serves")
helpers.show_graph(view=services)
```

## 4. Select with a filter

Narrative: a filter is a declarative selection. It tests classifications, labels
and values with units. A missing value never passes a test. The view shows the
objects that a filter selects, coloured by their `use` label.

```python
# cell 9
floors = graph.find(filter=rk.model.Filter(classification="floor"))
helpers.show_geometry(model=graph, highlight=floors, color_by="use")  # 33 floors
```

```python
# cell 10
graph.find(
    filter=rk.model.Filter(
        classification="floor", labels={"use": "residential"}, where="gfa >= 1500 sqm"
    )
)
```

## 5. Roll up, one building first

Narrative. **Predict:** the gross floor area of Building A. A rollup adds a value
over the contributors under a root, through one kind of relationship. Its result
has a value and a coverage: which contributors had the value, and which did not.

```python
# cell 11
a_gfa = graph.rollup(
    of="gfa",
    over="spatiallyContains",
    root="building_a",
    contributors=rk.model.Filter(classification="floor"),
)
a_gfa.value, a_gfa.coverage
```

```python
# cell 12
gfa = graph.rollup(
    of="gfa",
    over="spatiallyContains",
    root="property",
    contributors=rk.model.Filter(classification="floor"),
)
gfa.pivot(rows="building", columns="use")
```

## 6. Shared items, counted once

Narrative: the plinth plant serves both buildings. Roll up the plant volume that
serves each building, then for both together. The plant appears in both buildings,
but the total counts it once.

```python
# cell 13
served = graph.rollup(of="volume", over="servedBy", roots=["building_a", "building_b"])
# each building includes the plant; the total does not repeat it
served.by_root(), served.value
```

```python
# cell 14
assert served.by_root().sum() > served.value
served.coverage.shared  # contributors reached from more than one root
```

## 7. Trace a total

Narrative: a total is only as good as its contributors. Trace Building B's area to
its floors, with the path from the root to each floor.

```python
# cell 15
gfa.trace(root="building_b")
```

## 8. Names repeat; identities do not

Narrative: two spaces in the source are both named `buildingAretail`. They are two
different entities with different codes. A lookup by name refuses to guess, and a
lookup of an unknown code says what it looked for.

```python
# cell 16
graph.find(filter=rk.model.Filter(name="buildingAretail")).table("code", "name", "id")
```

```python
# cell 17
try:
    graph.entity(name="buildingAretail")
except rk.errors.AmbiguousReferenceError as error:
    print(error.requested, error.candidates)  # two codes
try:
    graph.entity(code="building_c")
except rk.errors.MissingReferenceError as error:
    print(error.requested, error.candidates)  # the nearest codes
```

## 9. Lesson 02's income from the floors

Narrative: in lesson 02 the reference income came from totals by use. Now declare
it on each floor and roll it up. First, the same six equations as lesson 02, word
for word.

```python
# cell 18
draft = graph.edit()
site = draft.entity(code="property")
site.value(key="land_cost", units="AUD")
site.value(key="works_cost", units="AUD")
site.value(key="leverage", units="ratio")
site.value(key="mortgage_constant", units="% pa")
site.value(key="coverage", units="ratio")
site.value(key="operating_cost", units="AUD pa")
site.value(key="rent_factor", units="ratio")
```

```python
# cell 18b
site.equations(
    "total_cost = land_cost + works_cost",
    "mortgage = leverage * total_cost",
    "debt_service = mortgage_constant * mortgage",
    "noi = coverage * debt_service",
    "effective_income = noi + operating_cost",
    "effective_income = rent_factor * reference_income",
)
```

Narrative: rates by use are keyed values: one value with one member for each use.
A floor equation reads the member of its own `use` label. The same equations apply
to every floor.

```python
# cell 19
site.value(key="efficiency", units="ratio", by="use")
site.value(key="rent", units="AUD per sqm pa", by="use")
site.value(key="vacancy", units="ratio", by="use")
draft.equations_for(
    filter=rk.model.Filter(classification="floor"),
    equations=[
        "nla = efficiency[use] * gfa",
        "income = nla * rent[use] * (1 - vacancy[use])",
    ],
)
```

Narrative: the reference income is now a rollup of floor income. The rollup
declares a value; lesson 02's equation uses it by key.

```python
# cell 20
site.rollup(
    key="reference_income",
    of="income",
    over="spatiallyContains",
    root="property",
    contributors=rk.model.Filter(classification="floor"),
)
model = draft.commit()
```

## 10. The back door again

Narrative. **Predict:** does the supportable land price change? Fix the same
inputs as lesson 02, with the rates by use in place of the totals. The mortgage
constant comes from the loan payment, as in lesson 02.

```python
# cell 20b
monthly = rk.duration.Frequency.MONTH
payment = rk.finance.payment(
    principal="1 AUD", rate="6 % pa", term="20 years", frequency=monthly
)
constant = (payment / rk.Quantity(text="1 AUD")).to(units="% pa")
```

```python
# cell 21
data = helpers.load_property(snapshot=2032)
back = (
    model.specify(name="Back door from floors")
    .fix(works_cost=data["works_cost"], operating_cost=data["operating_cost"])
    .fix(leverage="65 %", coverage=1.25, mortgage_constant=constant)
    .fix(efficiency=data["efficiency"], rent=data["rent"], vacancy=data["vacancy"])
    .fix(rent_factor=1)
)
outcome = rk.execution.solve(specification=back)
outcome["land_cost"]
```

```python
# cell 22
lesson_02 = rk.io.load(path=helpers.data_path(name="02_back_door.specification.json"))
lesson_02.roles  # the totals by use that lesson 02 fixed
before = rk.execution.solve(specification=lesson_02)
assert rk.quantity.isclose(actual=outcome["land_cost"], expected=before["land_cost"])
```

```python
# cell 23
outcome.rollup(key="reference_income").pivot(rows="building", columns="use")
```

## Optional: an edit that breaks a reference

Narrative: remove a floor and roll up again. The rollup's coverage changes; an
equation that names the floor by code fails at `commit()` with a named error.

```python
# cell 24
draft = model.edit()
draft.remove(entity="a_hotel_floor_1")
try:
    draft.commit()
except rk.errors.MissingReferenceError as error:
    print(error.requested, error.referenced_by)
```

## Exercises

**Try it 1: area by building and use.** Pivot the net lettable area of the solved
model by building and use. Which use has the most area in Building B?

```python
# solution
nla = outcome.model.rollup(
    of="nla",
    over="spatiallyContains",
    root="property",
    contributors=rk.model.Filter(classification="floor"),
)
nla.pivot(rows="building", columns="use")
```

**Try it 2: one use only.** Roll up the residential income alone. Check that the
three uses add up to the total.

```python
# solution
total = rk.Quantity(text="0 AUD pa")
for use in ("hotel", "residential", "retail"):
    income = outcome.model.rollup(
        of="income",
        over="spatiallyContains",
        root="property",
        contributors=rk.model.Filter(classification="floor", labels={"use": use}),
    )
    print(use, income.value)
    total = total + income.value
assert rk.quantity.isclose(actual=total, expected=outcome["reference_income"])
```

**Try it 3: the rent that Building B needs.** Fix the land at 20 million AUD and free
the rent factor. Then trace the required income to Building B's floors.

```python
# solution
front = back.fix(land_cost="20e6 AUD").free("rent_factor")
rk.execution.solve(specification=front).rollup(key="reference_income").trace(
    root="building_b"
)
```

## Checks and recap

```python
# cell 25 (checks)
assert len(floors) == 33 and gfa.coverage.complete
assert rk.quantity.isclose(
    actual=gfa.value, expected=sum(gfa.pivot(rows="building").values())
)
assert served.coverage.shared == {"plinth_plant"}
```

**Recap.**

1. The project is a graph. Each question chooses its view: spatial, service or
   grouping.
2. A total is a rollup over chosen relationships and contributors. It counts shared
   items once, and its coverage shows what was missing.
3. A rollup declares a value, so the equations of lesson 02 work unchanged, and the
   answer now traces to floors.

**Next.** Lesson 07 lets policies change the graph itself.

## Cell budget

25 core code cells, 1 optional cell and 1 check cell (budget 20–25), 3 exercise
solutions. The longest cell has 11 lines (cell 19). Cells follow `ruff format` (D15).

## Rule check

| Cell | Rules | Result |
| --- | --- | --- |
| 2 | 1, 10 | G26; G35: `Model.summary()` |
| 3, 7–9 | 10 | Helpers draw. `show_geometry(model=, highlight=, color_by=)` draws the objects that a filter selects ([#87](https://github.com/daniel-fink/rangekeeper/issues/87), [#88](https://github.com/daniel-fink/rangekeeper/issues/88)) |
| 4–6 | 4, 7 | Lookups by code ([#156](https://github.com/daniel-fink/rangekeeper/issues/156), [#160](https://github.com/daniel-fink/rangekeeper/issues/160)). G36: `entities()`, `Entity.values`, `relationships(entity)` tables |
| 7–8 | 7 | G37: `Model.view(relationship_classification)` |
| 9–10 | 7 | `Filter` ([#121](https://github.com/daniel-fink/rangekeeper/issues/121)). G38: `where=` string comparisons with units |
| 11–12 | 7, 8 | Rollups ([#158](https://github.com/daniel-fink/rangekeeper/issues/158)), pivots ([#159](https://github.com/daniel-fink/rangekeeper/issues/159)). G39: `Model.rollup(key, over=, root=, contributors=)` facade; pivot rows by ancestor classification |
| 13–14 | 7 | G40: several roots, `by_root()`, `coverage.shared` |
| 15 | 7 | G41: `RollupResult.trace(root)` |
| 16–17 | 4, 9 | G42: `AmbiguousReferenceError`; error fields `requested`, `candidates` ([#156](https://github.com/daniel-fink/rangekeeper/issues/156)) |
| 18 | 3 | Lesson 02's strings, unchanged |
| 19 | 2, 3 | G43: keyed values (`by="use"`), label indexing in equations, `equations_for(filter=, equations=)` |
| 20 | 2, 7 | G44: entity `rollup(key=, ...)` declares a Value (decision D3) |
| 21 | 2, 5 | G45: `fix` takes keyed values as mappings |
| 22 | 8 | G26 |
| 23 | 7, 8 | G46: `Outcome.rollup(key)` and `Outcome.model` |
| 24 | 9 | G27 (`remove`); [#156](https://github.com/daniel-fink/rangekeeper/issues/156) with `referenced_by` |
| 25 | 8 | G39–G40 |

## Data preparation (not API gaps)

- Entities need readable, unique codes (for example `a_hotel_floor_1`) and `use`
  labels on floors in the 1.0 data package ([#210](https://github.com/daniel-fink/rangekeeper/issues/210)).
- The data package needs `02_feasibility.model.json` and `03_base_plan.model.json`.
  CI writes them from lessons 02 and 03 with a namespace and checks that they have
  not changed.
