# Glossary

This page defines the words that Rangekeeper uses. Each word has one meaning. The
**Owner** column gives the 1.0 package ([ADR-010](../decisions/010-layers-and-packages.md)).
The **Current name** column shows a different name used until the 1.0.0a2 rename
pass ([ADR-012](../decisions/012-naming-and-glossary.md)).

## Documents

| Term | Meaning | Owner | Current name |
| --- | --- | --- | --- |
| Document | A stored, immutable, versioned root record with metadata and validation | — | — |
| Model | Project knowledge: definitions, system, provenance and an optional geometry pin | `model` | — |
| Specification | An investigation of one Model revision: fixed and free values, estimates, bounds, objectives, policies, includes and cases | `specification` | — |
| Run | Finalized evidence of one attempt or batch: status, report, output Models and child Runs | `run` | — |
| Market paths (`rk.market.Paths`) | A captured, replayable set of market paths with its capture record | `market` | `MarketPaths`; `ScenarioRealization` inside Model provenance |
| Bundle | A delivered set of documents with their exact dependencies | `io` | — |
| Revision | One immutable version of a document, identified by its Metadata UUID | `schema` | — |

## Inside a Model

| Term | Meaning | Owner | Current name |
| --- | --- | --- | --- |
| Definitions | Reusable declarations: Measures, Taxonomies and Functions | `model` | — |
| Measure | A named dimension with units, for example GFA in square metres | `model` | — |
| Taxonomy | A tree of Classifications | `model` | — |
| Classification | One category in a Taxonomy, such as floor or retail | `model` | — |
| Sub-type | A Classification below another in its Taxonomy | `model` | — |
| Function | A declared mathematical function that equations can use | `model` | — |
| System | The Entities, Assemblies, Relationships and Formulations of a Model | `model` | — |
| Entity | One thing in the project, such as a floor or a building | `model` | — |
| Assembly | An Entity that groups member Entities | `model` | — |
| Relationship | A typed, classified link between two Entities | `model` | — |
| Characteristics | The Values, Labels and properties that an Entity owns | `model` | — |
| Value | One owned datum: a Measurement, a Flow or Content | `model` | — |
| Key | The name of a Value, unique within its owner | `model` | — |
| Code | A catalogue identifier, such as a Classification code | `model` | — |
| Label | A Classification attached to an Entity in addition to its main Classification | `model` | — |
| Formulation | A named set of equations over Values. It does not say which values are known | `model` | — |
| Equation | One relation that must hold between values: an equality, or a bound such as `b_start >= shared_start + 1 year`. It is written as text or in Python with `rx` (`rangekeeper.expressions`), and stored as a Constraint over Expressions in a Formulation. It has no calculation direction | `model` | — |
| Expression | One mathematical expression in an equation | `model` | — |
| Provenance | Sources, Claims and Facts that support recorded content | `model` | — |
| Geometry pin | An exact link to native geometry files and their Entity mappings | `model` | — |

## Values and time

| Term | Meaning | Owner | Current name |
| --- | --- | --- | --- |
| Quantity | A magnitude with units; `rk.Quantity` at the root | `quantity` | `model.measure.Quantity` |
| Units | A unit string, such as `AUD per year` | `quantity` | — |
| Unit system | The curated registry that parses, checks and converts units; a Model records its own as `Model.unit_system`. See [units](../reference/units.md) | `quantity` | `UnitSystem`; a parameter is sometimes called `units` |
| Frequency | A calendar step, such as a month or a year | `duration` | — |
| Period | One half-open time interval with `start` and `end` | `duration` | — |
| Periods | An ordered, gap-free sequence of Periods with one frequency; an argument that takes one is named `periods=` | `duration` | `tuple[Period, ...]`; `PeriodIndex` in 0.8 |
| Span | A named half-open range of time | `duration` | — |
| Never | `rk.duration.NEVER`: a date value meaning "the event does not happen"; also `NEVER` in equation text. Not `None`, which means missing | `duration` | `"never"` string |
| Profile | How an amount develops over Periods: growth from an initial amount, or distribution of a total | `profile` | `calculations.projection` (`Extrapolation`, `Distribution` projections) |
| Movement | One dated or period-based amount | `flow` | — |
| Flow | An ordered series of Movements in one unit | `flow` | `model.flux.Flow` |
| Stream | A set of named Flows that operations treat together | `flow` | Line names called `labels` |

## Investigation and evidence

| Term | Meaning | Owner | Current name |
| --- | --- | --- | --- |
| Role | What a Specification says about a value: fixed, free, decided, estimate or bound. `Specification.roles` lists them | `specification` | — |
| Fix | Supply a known value for an investigation (an Assignment) | `specification` | `lock` |
| Free | Make a value an unknown that the solve finds. A value that is not fixed is free | `specification` | `unlock` |
| Estimate, bound, objective | A starting value, a limit, or a quantity to optimise | `specification` | — |
| Composition | The effective investigation after included Specifications are combined | `specification` | — |
| Case | One entry in a batch Specification, for example one market path | `specification` | — |
| Policy | The rules of a Specification, in order. Each rule uses only information available at its review date | `specification` (declarations), `execution` (evaluation) | `specification.policy` |
| Rule | A declaration that decides one value during the solve: `decide(key, when=, review=, window=, otherwise=)` ([ADR-021](../decisions/021-sequential-decisions.md)) | `specification` | `Decision`, `Rule` and `Action` records |
| Decided | A role beside fixed and free. A rule fixes the value on its decision date | `specification` | Policy control |
| Review date, window | A date on which a rule tests its condition; the half-open range that contains them | `specification` | Decision date |
| Alternative, choice key | A design option as a Model revision; the Specification value that selects one ([ADR-022](../decisions/022-design-alternatives.md)) | `specification` | — |
| Paired comparison | The difference between two Outcomes on the same MarketPaths, path by path | `execution` | — |
| Availability | The earliest date at which a value can be observed | `specification` | — |
| Solve | Calculate an `Outcome` without writing to a store | `execution` | Part of `Executor.execute` |
| Execute | Solve and then publish to a store | `execution` | `Executor.execute` |
| Affine problem | The linear problem that a backend receives | `execution` | `Compiled` request |
| Backend | A registered solver implementation | `execution` | — |
| Termination | How a backend finished: feasible candidate, proven infeasible, limit, error or unknown | `execution` | Pyomo status strings |
| Verification | Independent check of a candidate against the original equations | `execution` | Acceptance |
| Outcome | The result of a solve: status, values, evidence, Run and outputs | `execution` | — |
| Underdetermined | A result with free unknowns that the equations do not fix | `execution` | Feasible with a warning |
| Report | Diagnostics, trace, settings, fingerprints and decision traces in a Run | `run` | Policy outcomes |
| Diagnostic | One coded finding with structured fields | `shared` | Also `findings` and `issues` |
| Fingerprint | A digest that identifies an implementation and its import closure | `shared` | — |

## Analysis and market paths

| Term | Meaning | Owner | Current name |
| --- | --- | --- | --- |
| View | A selection of Entities and Relationships from a Model | `model` | — |
| Hierarchy | A tree built from Relationships or memberships | `model` | — |
| Rollup | Totals of values over a Hierarchy | `model` | `Reduction` |
| Rollup result | The value and coverage of a rollup | `model` | `model.system.reduction.Aggregation` |
| Flow aggregate | The result of aggregating Flows, with coverage | `flow` | `calculations.series.Aggregation` |
| Coverage | Which contributors had a value, and which did not | `model`, `flow` | Four different types |
| Pivot | A cross-tab of rollup results by rows and columns | `model` | — |
| Filter | A declarative selection by classification, labels, number comparisons and presence | `model` | Classification and exact label criteria only |
| Path | One possible history of external conditions: named Flows with availability | `market` | Scenario |
| Path generator | A registered method that makes market paths from parameters, and a seed when the dynamics are random (`rk.market.Dynamics`) | `market` | `ScenarioPlan` method; `MarketDynamics` |

## Authoring

| Term | Meaning | Owner | Current name |
| --- | --- | --- | --- |
| Draft | A mutable set of additions or changes to a Model, from `model.edit()`. `commit()` checks it once and returns a new revision | `model` | Builder |
| Namespace | A UUID that makes the IDs of a Model and its drafts deterministic | `model` | — |
| Handle | A draft's reference to an object, such as an entity, that does not have a UUID yet. A value's handle also builds equations with Python operators | `model`, `expressions` | — |
| Expressions (`rx`) | The Python form of equations: `import rangekeeper.expressions as rx`. It mirrors the equation functions of the text form and makes the same records | `expressions` | Nested `equal(left=..., right=add(...))` constructors |

## Words with one meaning only

| Word | Use only for |
| --- | --- |
| Target | `Reference.target`, the UUID of a referenced Value or Movement |
| Accept, acceptance | Not a term for result checks. Use "verify" for the independent check of a solved candidate. The plain sense, such as "a reader accepts a format", is permitted |
| Projection | Not used. Use "profile" (growth or distribution) for time shapes and "table" for exports |
| Scenario | Not used for generated futures. Use "path" |
| Measure | Only the Measure record. Use "count steps" for calendar counting |
