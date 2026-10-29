# Glossary

This page defines the words that Rangekeeper uses. Each word has one meaning. The
**Owner** column gives the 1.0 package ([ADR-010](../decisions/010-layers-and-packages.md)).
The **Current name** column shows the name that the code uses now, where it is
different, and "—" when the code uses the term as written. "None (planned,
#NNN)" marks a 1.0 name that does not exist yet; the issue tracks it. The [rename map](../guides/upgrading.md#100a2-rename-map) gives each
move ([ADR-012](../decisions/012-naming-and-glossary.md)).

## Documents

| Term | Meaning | Owner | Current name |
| --- | --- | --- | --- |
| Document | A stored, immutable, versioned root record with metadata and validation | — | — |
| Model | Project knowledge: definitions, system, provenance and an optional geometry pin | `model` | — |
| Specification | An investigation of one Model revision: fixed and free values, estimates, bounds, objectives, rules, includes and cases | `specification` | — |
| Run | Finalized evidence of one attempt or batch: status, report, output Models and child Runs | `run` | — |
| Market paths (`rk.market.Paths`) | A captured, replayable set of market paths with its capture record | `market` | `rk.market.Paths`: none (planned, #298). Now `ScenarioPlan` and `ScenarioRealization`, inside Model provenance |
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
| Direction | Which way a traversal follows a Relationship: `rk.model.Direction.OUTGOING` or `INCOMING`. Each Relationship has one name; the other direction is `INCOMING`, not a second name | `model` | — |
| Characteristics | The Values, Labels and properties that an Entity owns | `model` | — |
| Value | One owned datum: a Measurement, a Flow, a date or Content | `model` | The `Value` record; its `kind` is a `ValueKind` (`MEASUREMENT`, `FLOW`, `DATE` or `PROPERTY` for Content) |
| Key | The name of a Value, unique within its owner | `model` | — |
| Code | A catalogue identifier, such as a Classification code. Not `rk.errors.Code`; see [words with one meaning only](#words-with-one-meaning-only) | `model` | — |
| Label | A Classification attached to an Entity in addition to its main Classification | `model` | — |
| Formulation | A named set of equations over Values, such as "Funding". It does not say which values are known. `project.add_formulation(name=)` makes one and `project.formulation(name=)` finds one; each takes `equations(...)` | `model` | The `Formulation` record. The handles: none (planned, #305) |
| Equation | One relation that must hold between values: an equality, or a bound such as `b_start >= shared_start + 1 year`. It is written as text or in Python with `rx` (`rangekeeper.expressions`), and stored as a Constraint over Expressions in a Formulation. It has no calculation direction | `model` | The `Constraint` record. `rx`: none (planned, #309) |
| Equation text | An equation written as a string: the Python form with `=` for equality, `and`, `or` and `not`, quantity literals such as `2 years`, and `NEVER`. Names are value keys, or `code.key` for a value of another entity. `project.equations("noi = coverage * debt_service")` reads it into Expression records | `model` | `EntityHandle.equations`. Equation functions and Flow methods: none (planned, #278) |
| Expression | One mathematical expression in an equation | `model` | — |
| Provenance | Sources, Claims and Facts that support recorded content | `model` | — |
| Geometry pin | An exact link to native geometry files and their Entity mappings | `model` | — |

## Values and time

| Term | Meaning | Owner | Current name |
| --- | --- | --- | --- |
| Quantity | A magnitude with units; `rk.Quantity` at the root | `quantity` | — |
| Units | A unit string, such as `AUD per year` | `quantity` | — |
| Currency amount | A magnitude whose units are one ISO 4217 code, held as a `Decimal` with at most 15 significant digits. See [currency amounts](../reference/units.md#currency-amounts) | `money` | — |
| Canonical text | The one decimal text of a currency amount, for example `"1.5"`, in records, JSON, YAML and Parquet | `money` | — |
| Boundary conversion | `to_number` from an amount to float64 for a calculation, and `to_amount` back at 15 significant digits | `money` | — |
| Unit system | The curated registry that parses, checks and converts units; a Model records its own as `Model.unit_system`. See [units](../reference/units.md) | `quantity` | `UnitSystem`; a parameter is sometimes called `units` |
| Frequency | A calendar step, such as a month or a year | `duration` | — |
| Grid | A division of the calendar into Periods of one frequency: `DayGrid`, `WeekGrid`, `MonthGrid` or `MultiYearGrid`. `containing_period(on=, grid=)` finds the Period of a date | `duration` | — |
| Period | One half-open time interval with `start` and `end` | `duration` | — |
| Periods | An ordered, gap-free sequence of Periods with one frequency; an argument that takes one is named `periods=` | `duration` | —; `PeriodIndex` in 0.8 |
| Span | A named half-open range of time | `duration` | — |
| Never | `rk.duration.NEVER`: a date value meaning "the event does not happen"; also `NEVER` in equation text. Not `None`, which means missing | `duration` | — |
| Profile | How an amount develops over Periods: growth from an initial amount, or distribution of a total | `profile` | — |
| Movement | One dated or period-based amount | `flow` | — |
| Flow | An ordered series of Movements in one unit | `flow` | — |
| Stream | A set of named Flows that operations treat together | `flow` | — |

## Investigation and evidence

| Term | Meaning | Owner | Current name |
| --- | --- | --- | --- |
| Role | What a Specification says about a value: fixed, free or decided. `Specification.roles` lists the role of each value. Estimates and bounds are not roles: an estimate is a starting value and a bound is an equation | `specification` | `Specification.roles`, `rk.specification.Role` (`FIXED`, `FREE`, `DECIDED`) |
| Fix | Supply a known value for an investigation (an Assignment) | `specification` | `Specification.fix` |
| Free | Make a value an unknown that the solve finds. A value that is not fixed is free | `specification` | `Specification.free` |
| Estimate, bound, objective | A starting value, a limit, or a quantity to optimise | `specification` | — |
| Composition | The effective investigation after included Specifications are combined | `specification` | — |
| Case | One entry in a batch Specification, for example one market path. Its key is its Metadata name | `specification` | `Specification.cases`, `Specification.case`, `Outcome.case` |
| Rule | A query that fixes one value during the solve: the first date in a `Window` when a condition holds, or a default, written `window.where(condition=...).first(otherwise=...)` and fixed by key ([ADR-021](../decisions/021-sequential-decisions.md)). All of a Specification's rules are `spec.rules`; a Specification with rules is a strategy. The word "policy" is not used | `specification` | `RuleSet`, with `Decision`, `Rule` and `Action` records, in `specification.rule` |
| Decided | A role beside fixed and free. A rule fixes the value on its decision date | `specification` | A target of the `RuleSet` |
| Window | The dates on which a rule may act: by default, each date on which a value that its condition reads becomes known, or the first day of each of its `Periods`; between optional `earliest` and `latest` bounds | `specification` | None (planned, #300). Now each `Decision` record has one date (`at`) |
| Decision result | The result of one check of a rule: `rk.execution.DecisionResult` (`DECIDED`, `NOT_MET`, `SKIPPED` or `OTHERWISE`). `DecisionResult.of(evidence)` reads it from recorded rule evidence | `execution` | Checks on each window date: none (planned, #300) |
| Alternative, choice key | A design option as a Model revision; the Specification value that selects one ([ADR-022](../decisions/022-design-alternatives.md)) | `specification` | None (planned, #302) |
| Paired comparison | The difference between two Outcomes on the same cases, case by case: on the same MarketPaths, path by path | `execution` | `execution.compare(outcomes=, keys=, baseline=)` returns a `Paired`, which pairs cases by case key; without `baseline`, a `SideBySide`. Pairing by path follows with paths (#138) |
| Availability | The earliest date at which a value can be observed | `specification` | — |
| Solve | Calculate an `Outcome` without writing to a store | `execution` | `execution.solve` |
| Execute | Solve and then publish to a store | `execution` | `execution.execute` |
| Affine problem | The linear problem that a backend receives | `execution` | `AffineProblem`: variables, rows with relations, bounds and the rank analysis |
| Backend | A registered solver implementation | `execution` | — |
| Termination | How a backend finished: a feasible candidate, proven infeasible, limited, failed or unknown. It uses the words of Status for the same ideas | `execution` | `execution.backends.Termination`, in a `BackendResult` |
| Verification | Independent check of a candidate against the original equations | `execution` | `execution.verify`, which returns a `Verification` |
| Status | What an Outcome found, in one word: feasible, underdetermined, infeasible, unsupported, invalid, limited or failed | `execution` | `rk.execution.Status`, from `Outcome.status` |
| Run status | The completion and the solution that a Run report records, each in its own enum. It is a record, not a Status | `run` | `rk.run.RunStatus`, at `run.report.status` |
| Outcome | The result of a solve: status, values, evidence, Run and outputs | `execution` | `Outcome`: `outcome["key"]`, `status`, `raise_for_status()`, `free_unknowns`, `evidence`, `run`, `outputs` and `cases` |
| Underdetermined | A result with free unknowns that the equations do not fix, with or without bounds | `execution` | `Status.UNDERDETERMINED`, with `Outcome.free_unknowns` |
| Report | Diagnostics, trace, settings, fingerprints and decision traces in a Run | `run` | — |
| Diagnostic | One coded finding with structured fields | `shared` | Also `findings` and `issues` |
| Fingerprint | A digest that identifies an implementation and its import closure | `shared` | — |

## Analysis and market paths

| Term | Meaning | Owner | Current name |
| --- | --- | --- | --- |
| View | A selection of Entities and Relationships from a Model | `model` | — |
| Hierarchy | A tree built from Relationships or memberships | `model` | — |
| Rollup | Totals of values over a Hierarchy: `QuantityRollup` and `FlowRollup`, with one `Reducer` enum | `model` | — |
| Rollup definition | `rk.model.Rollup(of=, over=, roots=, contributors=)`: what a rollup adds up, over which relationship, from which roots and contributors. `value(..., rollup=)` declares a value with it | `model` | None (planned, #285) |
| Rollup result | The value and coverage of a rollup | `model` | — |
| Rollup error | A rollup or pivot that cannot give a meaningful result: `RollupError`, code `rollup` | `model` | — |
| Flow aggregate | The result of aggregating Flows, with coverage | `flow` | — |
| Coverage | Which contributors had a value, and which did not | `model`, `flow` | Four different types |
| Pivot | A cross-tab of rollup results by rows and columns | `model` | — |
| Filter | A declarative selection by classification, labels, number comparisons and presence | `model` | — |
| Path | One possible history of external conditions: named Flows with availability | `market` | Scenario |
| Path generator | A registered method that makes market paths from parameters, and a seed when the dynamics are random (`rk.market.Dynamics`) | `market` | `ScenarioPlan` method; the kernels in `market.dynamics` |

## Authoring

| Term | Meaning | Owner | Current name |
| --- | --- | --- | --- |
| Draft | A mutable set of additions or changes to a Model, from `model.edit()`. `commit()` checks it once and returns a new revision | `model` | `ModelDraft` |
| Namespace | A UUID that makes the IDs of a Model and its drafts deterministic | `model` | `rk.Model(namespace=)` derives the IDs that a draft makes; the tested contract and stored namespace are planned (#146, #147) |
| Handle | A draft's reference to an object, such as an entity or a value, by its UUID. A value's handle also builds equations with Python operators | `model`, `expressions` | `EntityHandle` and `ValueHandle`; operators are planned (#309), and Formulation handles (#305) |
| Expressions (`rx`) | The Python form of equations: `import rangekeeper.expressions as rx`. It mirrors the equation functions of the text form and makes the same records | `expressions` | None (planned, #309). Now equation text, or the provisional record constructors in `rangekeeper.model.expression.authoring` |

## Words with one meaning only

| Word | Use only for |
| --- | --- |
| Target | The record that a reference, a diagnostic or an error is about, by its UUID: `Reference.target` (a Value or Movement), `Diagnostic.target`, and the `targets` of an `Issue` or a `RangekeeperError` (for example a Constraint or an Entity). Not the goal of a solve |
| Code | A catalogue identifier, such as a Classification or Entity code. `rk.errors.Code` is a different thing: the enum of diagnostic and error codes on a `Diagnostic` or a `RangekeeperError`. Say "error code" or "diagnostic code" for it |
| Accept, acceptance | Not a term for result checks. Use "verify" for the independent check of a solved candidate. The plain sense, such as "a reader accepts a format", is permitted |
| Projection | Not used. Use "profile" (growth or distribution) for time shapes and "table" for exports |
| Scenario | Not used for generated futures. Use "path" |
| Measure | Only the Measure record. Use "count steps" for calendar counting |
