# Model, Specification, and Run: object model and requirements

Status: semantic specification with drafted scalar record contracts; implementation
plan updated 2026-10-03. Initially recorded 2026-09-24. The authoritative record
shapes are in `schema/`. Generated records and the
[Model/Specification library APIs](DOMAIN_CORE.md) and
[Run/storage APIs](RUN_AND_STORAGE.md), including final root exports, are implemented.
[Affine scalar execution](SCALAR_EXECUTION.md) and
[Model-backed graph selection/reduction](GRAPH_MODEL.md) are implemented.
Table, adapter and source-consumer migration follow. Historical updates below
explain how the current contract evolved.

**Agreed** records established semantics. **Proposed** and **Open** identify
extensions or unresolved implementation details; earlier proposals do not override
the drafted schemas and explicit later decisions.

**Current architecture decisions, 2026-10-02:** retain
[LinkML](research/current-schema-comparison/DECISION.md) as the record authority;
use Pyomo with HiGHS for the first affine scalar execution. The
[library architecture](LIBRARY_ARCHITECTURE.md) now incorporates the completed
[domain replacement map](DOMAIN_MIGRATION_MAP.md), followed by the minimal schema-backed core
directly in the intended library packages before implementing execution. Graph
algorithms and numerical routines are assessed for reuse; existing consumers
migrate incrementally. The earlier temporary repository executor and later
library-promotion sequence is superseded. Pyomo 6.10.1 and HiGHS 1.15.1 are now
pinned and verified through actual forward/inverse execution and installed-wheel checks.

**2026-09-29 update (corrected):** the agreed high-level Entity structure is `id`,
`code`, `name`, `classification`, and `characteristics`. The optional `code` is a
human-facing reference, not identity; it may change and is unique across Entities
and Assemblies within a Model when supplied. UUIDs retain stable identity.
**2026-09-30 reference update:** identified records designate their stable UUID
as the LinkML identifier. Classification, parent, Measure, membership, endpoint,
and provenance target references use that UUID through typed class ranges.
Definitions and Characteristics serialize as lists with explicit codes/local keys.
Codes remain case-sensitive and reject surrounding whitespace; dots are literal
characters, not reference syntax. Renaming codes or local keys preserves UUID
references. The earlier qualified-code resolver and code-keyed serialization have
been replaced in the schema examples and conformance checks. Characteristics contains `labels`
and named `values`; Values unify the earlier measurements/features categories.
Values may be simple or structured, including Dates, Spans, Flows, Streams, and
Accounts; definitions remain distinct from observations and calculated results.
The [LinkML draft](../schema/entity.yaml) defines this outer structure with
imported [Classification](../schema/classification.yaml) and
[Characteristics](../schema/characteristics.yaml) schemas. Characteristics groups
the labels/values collections, identified Values, and Label classification references.
Value has a UUID, local key, kind, and description. Measurement is the first
Value kind, with a required Measure and optional Quantity. A Quantity is embedded
content with a finite magnitude and explicit units compatible with the Measure.
An absent or null Quantity is unresolved; Facts and Claims explain recorded content. Recorded amounts do not
fix subsequent Specifications. The schema defines the intended contract; implementation
must conform to it. This supersedes the brief
proposal to put labels/values directly on Entity or absorb its classification
into labels. The older Component and property-binding decompositions below remain
proposals to reconcile as child schemas are developed, not additional required
Entity fields. Python integration should begin with the Characteristics/Value
contract. Runtime Measurement now permits unresolved quantities; the broader
Characteristics migration and schema serialization remain pending.

The structural checkpoint now includes [Relationship](../schema/relationship.yaml),
[Assembly](../schema/assembly.yaml), and [Provenance](../schema/provenance.yaml) schemas.
A [shared example](../schema/examples/structural-graph.json) checks overlapping
membership, unresolved/resolved Measurements, and UUID-targeted Facts against the
existing graph runtime. This is a bounded conformance fixture, not a Model executor
or a production interchange adapter.

**2026-09-30 execution schema update:** [expression.yaml](../schema/expression.yaml)
now defines Quantity/Boolean literals, Value UUID references, unary and
binary operators, Function calls, member/index selection, and graph Queries.
Date and string literal nodes are deferred pending concrete requirements,
potentially from Policies; date-valued references, selections, and calls remain
expressible under their content domains.
[function.yaml](../schema/function.yaml) specifies versioned signatures and argument/result
Domains; [query.yaml](../schema/query.yaml) specifies traversal, fixed metadata
filters, projection, and duplicate handling. Aggregations are calls over query
collections, preserving unresolved Values as symbols. The
[Expression contract](../schema/EXPRESSION_CONTRACT.md) records their semantics and
validation limits. Categorical choices use qualified `Kind` enums. `Domain`
describes permitted content: `Parameter.domain` and `Function.result` contain a
Domain, and collections recursively specify `item_domain`. `Value.kind`,
`Expression.kind`, and `Parameter.kind` describe their respective categories, not
recorded results or Specification roles. These schemas do not implement query execution or rich Value
content formats. Operands are nested, identified Expressions; comparison
predicates do not assert themselves. The
[valuation expressions](../schema/examples/valuation-expressions.yaml) are instance
data, not built-in equations or an executable Model envelope.
[constraint.yaml](../schema/constraint.yaml) now defines identified assertions with
required `id` and `predicate` fields and optional `code`, `name`, and `description`.
The predicate references an existing Boolean Expression by UUID; two Constraints
assert the valuation equations. Bounded checks validate references and Boolean
domains without evaluating satisfaction or solving. The Formulation schema now defines
mathematical containment; Model, Specification, and finalized Run envelopes are drafted.
General structural publication remains an extension beyond scalar quantity updates.
Separate Resolution records are no longer planned: Values hold recorded content,
provenance explains it, and Runs record
execution and validity diagnostics. Exact Run linkage and partial/stale-content
handling still need specification. Queries over output Models replace requested
results in the Specification. Specification fields are `assignments`, `unknowns`, `estimates`,
additional `formulations`, and `settings`, with ordered `objectives` when needed.
Fixed variables can become unknowns in another Specification; a hard target is a
Specification-specific assignment or constraint. These decisions supersede earlier field proposals.

**2026-10-01 Formulation draft:** [formulation.yaml](../schema/formulation.yaml) now defines explicit
mathematical containers before the Model envelope. It distinguishes Values,
mathematics, and editor components; it does not make every Flow or Mark8 block a
mathematical Formulation. Section 3.6 records the drafted fields and deferred reusable
template concept. Section 5.1 records the agreed execution priorities: deterministic
valuation under supplied scenarios first, followed by evaluation across scenarios,
committed choices, and adaptive policies. Market generation can remain numerical;
algebraic inversion of the generator is a separate, deferred capability. These are
design decisions and schema checks, not an implemented Formulation compiler or solver adapter.

**2026-10-01 Model draft:** [model.yaml](../schema/model.yaml) now groups `metadata`,
`definitions`, `system`, and `provenance`. System contains Entities, Relationships,
Assemblies, and `formulations`: explicit Formulation instances. Definitions now includes
Functions. Metadata owns the revision UUID, so native LinkML revision references
target Metadata; there is no second root ID. The complete example and generated
checks establish a serialization boundary, not persistence or execution.

**2026-10-01 Specification draft:** [specification.yaml](../schema/specification.yaml) pins the input Model
and specifies `assignments`, `unknowns`, `estimates`, optional `formulations`,
`objectives`, and `settings`. Metadata is shared through `common.yaml`. The examples
and bounded checks cover composition and role rules without executing a solve.

**2026-10-01 terminology update:** `Specification` replaces the former `Problem`
name for the declared question and conditions supplied to a Model. Draft `0.3.0`
renames the schema namespace and root class, preserving field semantics. This
document uses the current name throughout. A Specification is instance data;
the LinkML schema defines its structure. Study describes the broader process
of modelling, execution, and analysis, not an additional root class.

**2026-10-01 additive composition update:** Specification draft `0.4.0` adds
`includes` for contributions to one investigation and `cases` for separate
investigations. Contributions accumulate without overrides; partial records become
executable only after complete composition. Cases explicitly include shared
requirements. One exact included revision contributes once even through multiple
paths. The combined include/case graph is acyclic; revision history is separate.
The bounded checks exercise standalone/composed scalar examples, a batch, and native
serialization, without running a solver. Section 2.4 now uses recursive ordinary
Runs rather than a new Evaluation or Scenario object. Policy execution, sampling,
temporal content, and cross-Model analysis remain to be implemented.

**2026-10-01 Run draft:** [run.yaml](../schema/run.yaml), version `0.1.0`, records
finalized attempts with `spawns`, accepted Model outputs, and report status/runtime/
diagnostics/trace. Shared numerical [Settings](../schema/settings.yaml) retain their
existing fields. Synthetic records exercise scalar and batch publication contracts,
failure visibility, and serialization; no scheduler or solver has executed them.

This is the current reference for the object model. The
[two-pad policy example](PROJECT_DEFINITION_AND_POLICY_EXAMPLE.md) remains the
longer-term design test and source of illustrative project assumptions.

## 1. Key functionality and agreed decisions

```text
Model₀ + Specification → Run → {Model₁, …, Modelₙ}
```

**Agreed:** a Model is an immutable graph of declarations, expressions, and relations,
including their properties. A Run can produce multiple new Model snapshots;
one is the ordinary scalar case. Each output has an unambiguous evaluation context.
An output can differ only in recorded resolutions or contain changed project structure
and generated definitions. Input snapshots remain unchanged; unchanged content may
be shared without copying every object.

| ID | Agreed requirement |
| --- | --- |
| A1 | Loading, inspecting, or serializing definitions does not execute them. |
| A2 | A Run retains exact input Model and Specification references and publishes new immutable Model snapshots for its recorded outcomes. One investigation may have several outcomes; their scenario and policy contexts remain distinct. Failed non-batch attempts may have no output; accepted publication rules are defined below. |
| A3 | A recorded resolution is not a new permanent constraint. Symbolic definitions survive resolution. |
| A4 | A Specification determines what is fixed, unknown, constrained, or optimized. Suitable declared quantities can change roles between Specifications. Queries select information from output Models. |
| A5 | Policies and intervention choices belong to the Specification, directly or by reference to reusable definitions. A Specification may contribute declarations, expressions, and relations. |
| A6 | Domain entities, assemblies, values, and computational components can share reference machinery while retaining their distinct meanings. |
| A7 | Solver-visible declarations must expose supported mathematical members and relationships. Inverse solving is attempted, not guaranteed to exist, be unique, or succeed. |
| A8 | Generated definitions require an explicit validation and evaluation stage. Their appearance does not automatically cause execution. |
| A9 | Model structure, equation structure, and execution order are distinguishable. A Model is not required to be a calculation DAG. |
| A10 | Introduce functionality through progressively richer examples, retaining the two-pad policy experiment as the destination. |

A finalized Run is not necessarily a successful solve. Failures remain visible in
reports and spawned case records. Only accepted snapshots are published as outputs
in the initial Run contract; partial-snapshot publication remains an extension.
Schema conformance is not evidence that a runtime exists.

For eventual Twenty publication, every upload creates a new project; no merging
back into an originating CRM project is required. Text-based authoring and browsing
must preserve meaning, identities, and provenance. EstateMaster reconstruction and
Twenty integration are subsequent adapters, not prerequisites for the core model.

## 2. Root objects

Model, Specification, and Run have LinkML drafts and bounded conformance fixtures.
Execution adapters and the richer policy/temporal contracts remain to be implemented.

### 2.1 Model

| Field | Meaning |
| --- | --- |
| metadata | Required Metadata with revision `id` and `schema_version`; optional `name`, `description`, and `previous` revision reference. |
| definitions | Inline Taxonomies, Measures, and exact versioned Function contracts. |
| system | Inline Entities, Relationships, Assemblies, and `formulations` containing root Formulations. |
| provenance | Sources, Claims, and Facts supporting recorded content. |

The last three containers may be omitted when empty. System is an embedded
container, not a separate revision or reference scope. Assemblies are stored once
in their own collection and remain eligible targets of Entity references. Governing
Constraints live under `system.formulations`; there are no competing root Expression
or Constraint collections. Child Formulation ownership continues to use `Formulation.formulations`.

`metadata.id` is the snapshot identity. LinkML identifies the Metadata class directly;
the enclosing Model has no duplicate identifier. The optional `previous` field is a
native Metadata UUID reference representing the preceding Model revision. History
need not be bundled or imported for the current snapshot to be interpretable.
Self-predecessors and cycles in available history are invalid. Schema version is
separate from snapshot identity and from Function/evaluator/solver versions.
`Metadata` is shared in `common.yaml`; resolvers check document kind in addition
to UUID identity. Model draft `0.3.0` imports this common revision contract.

The [complete Model example](../schema/examples/model.yaml) combines domain objects,
provenance, valuation Formulations, and a Function call. It contains unresolved Values and
does not represent a solved Specification. Generated structural checks, bounded reference
checks, and Python serialization do not enforce persistent storage immutability.

A Model with unresolved declarations is still a Model. A resolved Model keeps its
symbolic content. Observations, intrinsic constants, mathematical constraints, and
recorded results must not become indistinguishable merely because all contain values.

An output Model must retain or pin the definitions required by its mathematical and
domain references, including definitions introduced by interventions. This does not
automatically promote a Specification's assignments, targets, objectives, or policy to
permanent Model constraints. Those remain traceable through the Specification and Run.

### 2.2 Specification

**Drafted in [specification.yaml](../schema/specification.yaml), version `0.4.0`:**

| Field | Meaning |
| --- | --- |
| metadata | Required immutable Specification revision identity and schema version; optional name, description, and previous Specification revision. |
| model | Optional exact Model revision assertion; required after composing a concrete investigation. A batch pin checks its cases without supplying their Model. |
| includes | Exact Specification revision references contributing requirements to one investigation. |
| cases | Exact Specification revision references for separate investigations in a batch; no implicit inheritance. |
| assignments | Explicit Value UUID and Quantity records whose supplied amounts are held fixed. |
| unknowns | Unique Value UUIDs that may vary, including intermediate unknowns needed by the equations. Output selection is a query concern. |
| estimates | Value UUID and Quantity records giving initial numerical estimates for unknowns, without imposing equality. |
| formulations | Specification-owned Formulations containing additional Values, Expressions, Constraints, and child Formulations. |
| objectives | Ordered scalar numerical Expression references with minimize/maximize senses, in decreasing order of preference. |
| settings | Optional relative convergence tolerance, iteration limit, and time limit in seconds. Actual mappings and effective settings belong to the Run. |

The first draft supports whole measurement Values. Each solve-relevant Value has
exactly one assignment or unknown role; unrelated Values require neither. Each
assignment or estimate collection has at most one record per target, and estimates
target unknowns. Stored quantities do not supply either role automatically. An
`Assignment` supplies content; a Formulation `Binding` supplies an alias to a symbol.

All Model Constraints and Specification Formulation Constraints apply together. Specification
additions share UUID reference scope with the pinned Model without duplicating or
shadowing its declarations. Root Formulation codes have separate owning collection
scopes. The input Model remains valid independently of the Specification. An exact target
can assign an existing Value; an inequality or composite condition belongs in a
Specification Formulation. There are no competing root Expression or Constraint collections.

An effective composition with no objectives specifies an equation/feasibility investigation; forward and
inverse roles do not require distinct mode flags. The schema does not assert
feasibility, uniqueness, boundedness, or solver capability. Relative tolerance is a
dimensionless numerical request whose convergence criterion and scaling must be
documented by the backend; it is not a universal absolute residual threshold.

Objectives express preferences without mandating a selection workflow. An
implementation may use Pareto filtering and user choice, or automatic selection
using list order. The order must survive serialization and changes the Specification
revision when reordered; it does not require strict lexicographic optimality.
No `handling` field is specified. Explicit weighted combinations remain individual
Expression-based objectives. The Run records the chosen solution and selection
basis, including method, automatic versus user selection, and outcome limitations.
The singular `objective` field is replaced by the ordered `objectives` list in draft `0.2.0`.

The [forward](../schema/examples/specification-forward.yaml),
[inverse](../schema/examples/specification-inverse.yaml),
[optimization](../schema/examples/specification-optimization.yaml), and
[ordered-objectives](../schema/examples/specification-objectives.yaml) records all pin the
complete Model example. They are validated definitions, not executed investigations.

Partial contributions need only Metadata structurally. Completeness and Model-dependent
reference checks apply to a concrete composition. One source supplies each assignment,
unknown role, estimate, and setting; even identical independent duplicates are errors.
One contributor supplies the whole nonempty objectives list. Missing fields and empty
collections are neutral, so an empty list cannot cancel included objectives. Repeated
Model pins must agree. Formulations accumulate with canonical ownership and a shared
reference scope. Included revisions are deduplicated by UUID, not by similar content.

A batch has nonempty cases and only Metadata, an optional Model assertion, and case
references with content. It cannot supply/include solve requirements or serve as an
included contribution. Cases may be nested batches; leaf cases explicitly include
shared requirements. Multiple paths through cases are separate planned occurrences.
Metadata.previous is lineage only. The [composition examples](../schema/README.md#additive-composition-and-batches)
show these rules using the existing forward and inverse investigations.

Policies, interventions, uncertain observations, rich Value/member assignments,
and reusable template instantiation remain extensions.
They retain the responsibilities described below. An intervention that changes
definitions will require explicit transformation semantics; Specification additions do
not silently rewrite a Model's intrinsic constraints.

### 2.3 Run

**Drafted in [run.yaml](../schema/run.yaml), version `0.1.0`.**

| Field | Contract |
| --- | --- |
| metadata | Required immutable record identity and schema version. |
| specification | Exact attempted Specification revision; includes pin its contributions and input Model. |
| spawns | Direct subordinate Run references, including failed/skipped cases. No concurrency or scheduling order is implied. |
| outputs | Unique accepted Model revision references; a batch collects the union of spawned outputs. |
| report | Required status and optional runtime, diagnostics, and ordered trace. |

`Report.status` separates completion from mathematical solution. Completion is
completed, limited, partial, failed, cancelled, or skipped. Solution is feasible,
infeasible, unknown, not_assessed, or not_applicable. Completed execution need not
be feasible; failed numerics do not establish infeasibility, and feasibility is not
an optimality claim. Batches use not_applicable and retain individual case conclusions.
The [schema guide](../schema/README.md#runs) records valid combinations and the
aggregate batch completion rule.

A batch accounts for every direct case exactly once by spawned Run Specification
reference. Nested batches recurse; the spawn graph is acyclic with one parent per
non-root Run in the execution tree. Repeated case paths have distinct executions.
Runs may contain subsidiary solves; reuse of another Run's result is not spawning.
Batch outputs collect existing child output references without copying Models.
Explicit retries, extra unpaired batch spawns, and reuse dependencies remain extensions.

Only finalized Run records are serialized. Live progress remains runtime state.
Skipped Runs have no Runtime; non-completed outcomes require explanatory diagnostics.
A failed non-batch execution may have no output. Only accepted Model snapshots appear
in outputs; partial or unvalidated snapshots are not accepted outputs in this draft.
A limited attempt may publish an accepted feasible candidate while recording its
limits. Failed/skipped cases remain visible in the batch's population.

Runtime records actual evaluator/compiler/solver names and versions, observed
start/finish times, and effective numerical Settings. Shared Metadata describes the
document revision, not the runtime. Changed or unapplied requests require diagnostics.
Timezone-qualified times describe execution, not simulated project time. Complete
backend-option, environment, and random-state manifests remain extensions.

Diagnostic and Step targets are qualified by their document revision. Numerical
diagnostics state residuals, tolerances, units, scaling, and acceptance conventions.
Trace Steps cover validation, formulation, solving, publication, and selection.
Optimization output requires selection evidence identifying its method, basis,
automatic versus user choice, and limitations; comparing a batch does not require
a winner. Detailed policy decisions and action effects remain to be specified.

Accepted scalar publication preserves input definitions and declaration identities,
records required quantities, and links the new Model revision to its input. Recorded
quantities do not become permanent assignments. Temporary Specification mathematics
is not silently installed as output governing constraints. General structural
publication and retention of Specification-local Values require further adapters.
Model provenance remains responsible for evidence about recorded content; the Run
links the exact Specification and published Model revisions. Full Fact/Claim-to-Run
linkage is not introduced by this envelope alone.

The [forward](../schema/examples/run-forward.yaml),
[inverse](../schema/examples/run-inverse.yaml), and
[batch](../schema/examples/run-batch.yaml) records and expected Model snapshots are
explicitly synthetic conformance fixtures. Failed/skipped fixtures and bounded checks
exercise unsuccessful outcomes, scope, timing, publication, and native serialization.
These records do not claim observed evaluation or numerical solver execution.

"Project history" is not a schema class. A Model can represent an entire simulated
timeline only when temporal Values and effective periods encode it. Document revision
history, simulated time, and execution trace remain distinct.

### 2.4 Scenario and policy composition sketches

**Updated direction, 2026-10-01.** Additive Specification composition is now drafted;
the following policy and Run sketches remain explanatory, not executable records.
They replace the earlier provisional `evaluations` arrays and output context records.
No dedicated Scenario or Evaluation class is introduced. Short tokens stand for exact
revision UUIDs. All contributions are ordinary Specifications. Policy and time-path
payloads still require contracts; no financial outputs or completed Runs are asserted.

#### Shared Model, scenarios, and policy alternatives

`M0` is the two-pad project definition. Both pads initially operate as carparks;
candidate development actions, capacity constraints, and commitments follow the
[representative example](PROJECT_DEFINITION_AND_POLICY_EXAMPLE.md). This is a
composition sketch, not a replacement for that example's numerical assumptions.
For the conflict example only, extend `M0` with an existing loan that permits
voluntary repayment. Its balance, repayment terms, and cash/reserve amounts must
be specified before execution. This is an explicit extension to the original
equity-funded example, not an assumption that it already contained such a loan.

| Scenario reference | Hand-authored story |
| --- | --- |
| S1 | Housing demand strengthens; construction costs remain stable. |
| S2 | Workspace demand strengthens while housing remains weak. |
| S3 | Both markets slump and later recover. |

These stories stand for future supplied paths whose numeric observations still need
specification. They are not sampled paths, calibrated probabilities, or executable
fixtures. All evaluations of a scenario use the same exogenous path and observation
schedule. A policy sees only observations available at its decision time. Scenario
identity must not let it inspect future outcomes or hidden generator state.

Two complete policy configurations reuse the same subordinate policies:

| Policy reference | Coordination rule when expansion and voluntary repayment compete |
| --- | --- |
| P_growth | Prioritize a qualifying feasible development commitment; use eligible remaining cash for voluntary debt repayment. |
| P_debt | Prioritize eligible voluntary debt repayment; undertake development only if the remaining funding covers its commitments. |

Both first protect mandatory payments, reserves, and existing commitments. Priority
never authorizes a constraint violation. They differ in deliberate management
behaviour, not solver settings or the external market. Their full parameters,
observation/forecast rules, and reusable action definitions must be pinned before
execution. It is not yet established whether either policy outperforms the other.

#### One composed policy: choice, handover, and conflict

The following subordinate roles form one complete policy configuration:

| Role | Proposed behaviour and handover |
| --- | --- |
| Review | At a quarterly review, propose the highest-scoring permitted housing or workspace start above its threshold; ties favour housing, then Pad A. If no opportunity qualifies, propose waiting. Funding is checked by the coordinator before commitment. |
| Retain | Operate undeveloped parking while waiting; return to Review at the next quarterly decision date. |
| Construct | After an accepted start, service the committed construction plan. On observed completion, activate Operate for that asset. Existing commitments continue even if later market observations deteriorate. |
| Operate | Operate completed assets. Completion can make the other pad eligible for development at a subsequent Review. |
| Repay | Propose voluntary repayment when debt is outstanding and the specified repayment conditions hold, using only uncommitted resources. |

The score and confirmation logic are the illustrative forecasting rules discussed
in the representative example, not realized future NPV. Exact thresholds and
repayment conditions remain to be specified. The tie rule above is a sketch choice,
not an agreed general policy default; the policy must reference the identified Pad A.

At each decision date, the proposed ordering is:

1. Account for due mandatory obligations and observed completions under the agreed
   temporal conventions; determine resources remaining after commitments/reserves.
2. Expose current/past observations. Review and Repay form recommendations against
   the same pre-action state, rather than independently mutating the project.
3. The coordinator chooses a jointly feasible action set using the configuration's
   priority. Recompute residual resource availability before admitting the next action.
4. Commit that set once, validate generated declarations and required mathematics,
   and record the transition. Advance to the next decision date; waiting cannot cause
   unbounded same-instant re-evaluation.

For example, starting Pad B and voluntarily repaying debt may each be feasible
alone but require the same cash. `P_growth` and `P_debt` arbitrate this differently.
Neither can consume funds reserved for Pad A's existing construction. If mandatory
obligations cannot be met, report that condition; do not silently call it a voluntary
"wait" decision. Detailed payment and income timing still require the temporal schema.

`Review recommends start`, `start is accepted`, and `construction completes` are
different events. A transition must identify its actual trigger, not use
`if(policy)` with unspecified truthiness. The Run's trace associates each decision
with its evaluation context, time, active policies, observations, proposals,
feasibility/coordination result, accepted actions, and generated or changed records.

This is one scenario execution even though several subordinate policies cooperate.
Internal policy transitions do not create a separate output for every active policy
or an alternative Model for every unchosen action. Optional checkpoints are separate
from the final output population. Intermediate algebraic solves may be required;
this coordination sketch does not make arbitrary policy logic solver-compatible.

#### Shared contributions

`Common` supplies the input Model and shared requirements. `Future1`, `Future2`, and
`Future3` will supply distinct exogenous input paths. `Growth` and `Debt` will each
select one complete policy configuration. Those path/policy payloads are deferred;
these are roles for Specifications, not new object types or schema fields.

```text
Spec1Growth.includes = [Common, Future1, Growth]
Spec2Growth.includes = [Common, Future2, Growth]
Spec3Growth.includes = [Common, Future3, Growth]
Spec1Debt.includes   = [Common, Future1, Debt]
Spec2Debt.includes   = [Common, Future2, Debt]
Spec3Debt.includes   = [Common, Future3, Debt]
```

All contributions are additive. Each numerical role/setting has one authoritative
contributor and one contributor supplies the complete nonempty objectives list.
Different policy selections will similarly require an explicit composition contract;
they must not be merged by priority or last-write-wins. Runtime coordination within
one complete policy is separate from Specification composition. Changing assumptions
or solve roles creates sibling compositions, not descendants that override inputs.

#### Sketch 1: one policy on one future

```yaml
specification:
  metadata: {id: Spec1Growth}
  includes: [Common, Future1, Growth]
expected_run:
  metadata: {id: R1}
  specification: Spec1Growth
  outputs: [M11]
```

One complete configuration on one supplied future produces one Model in this
successful-run sketch. The ordinary Model envelope must explicitly encode temporal
content; a future's story label does not determine its numerical results.

#### Sketch 2: the same policy on three futures

```yaml
specification:
  metadata: {id: GrowthComparison}
  model: M0
  cases: [Spec1Growth, Spec2Growth, Spec3Growth]
expected_run:
  metadata: {id: R2}
  specification: GrowthComparison
  spawns: [R21, R22, R23]
  outputs: [M21, M22, M23]
expected_spawns:
  - {metadata: {id: R21}, specification: Spec1Growth, outputs: [M21]}
  - {metadata: {id: R22}, specification: Spec2Growth, outputs: [M22]}
  - {metadata: {id: R23}, specification: Spec3Growth, outputs: [M23]}
```

Each case explicitly includes its shared requirements. The batch's Model pin is
an assertion, not inheritance. Child Runs are ordinary Run records, not Evaluation
objects. A future sampling operation can produce saved input contributions and
concrete cases before evaluation; its generator, dependency, RNG, and provenance
contracts remain deferred. Many random draws can form one future path.

#### Sketch 3: two policies compared on the same three futures

```yaml
specification:
  metadata: {id: PolicyComparison}
  model: M0
  cases: [Spec1Growth, Spec1Debt, Spec2Growth, Spec2Debt, Spec3Growth, Spec3Debt]
expected_run:
  metadata: {id: R3}
  specification: PolicyComparison
  spawns: [R31, R32, R33, R34, R35, R36]
  outputs: [M31, M32, M33, M34, M35, M36]
expected_spawns:
  - {metadata: {id: R31}, specification: Spec1Growth, outputs: [M31]}
  - {metadata: {id: R32}, specification: Spec1Debt, outputs: [M32]}
  - {metadata: {id: R33}, specification: Spec2Growth, outputs: [M33]}
  - {metadata: {id: R34}, specification: Spec2Debt, outputs: [M34]}
  - {metadata: {id: R35}, specification: Spec3Growth, outputs: [M35]}
  - {metadata: {id: R36}, specification: Spec3Debt, outputs: [M36]}
```

The six cases are explicit, with no implied Cartesian product, scheduling order,
or automatic winner. Both policies include the same exact Future revision for each
paired comparison. They do not combine conflicting alternatives into one investigation.
Each execution has isolated state; distinct Runs produce distinct output revision
identities even when content agrees. Retained declarations can keep their UUIDs.

#### Queries over the outputs

The output population is the collection of Model references associated with their
producing Runs and concrete Specifications. A query can select one policy's three
Models, calculate `q(Model)` for each, and summarize those values. For paired
comparisons, join on the shared Future contribution revision and
compare their metrics under the same valuation conventions. Do not pool the six
Models into one probability distribution without specifying what the policy axis means.

`q(Model)` might aggregate time-indexed cash flows into NPV or select homes delivered
by a specified date. A distribution is derived from the chosen metric and population,
not an intrinsic second output of every Run. Scenario weights, if supplied, apply
within the specified population; these three hand-authored stories do not themselves
establish probabilities. Missing or failed evaluations require explicit analysis
handling and must not be treated as zero or silently dropped.

The current Query contract is within one Model revision and returns symbolic Entity
or Value references. Cross-Model analysis must preserve `(Model revision, object UUID)`
context and distinguish reading recorded content from forming solver expressions.
Graph differences can require semantic selections instead of matching generated UUIDs.
The new query scope, temporal metrics, and any saved analysis artifacts remain future work.

Post-run exploration is user-directed. If a policy-search Specification uses an aggregate
such as expected NPV to make its choice, that metric, population, and weighting must
be specified for the investigation and evaluated during execution. Running an analysis
inside a Run does not change its reference scope or make every summary mandatory.

#### What these sketches settle and leave open

| Boundary | Direction demonstrated |
| --- | --- |
| Composition | One investigation accumulates compatible contributions through includes, without overrides. |
| Batching | Cases are separate concrete Specifications or nested batches, with ordinary child Runs. |
| Alternatives versus cooperation | Compare complete policy configurations; coordinate subordinate policies within each configuration. |
| Temporal meaning | Model content represents what is explicitly encoded; snapshots do not automatically preserve simulated histories. |
| Reporting | Queries select metrics and populations; Runs and Specification contributions identify each output's context. |
| Run root | metadata, specification, spawns, outputs, report; report groups status, runtime, diagnostics, and trace. |

The initial Run schema now specifies identity, direct-case accounting, pinned
references, status, and accepted-only output publication. Retry coordination and
partial/stale snapshot publication remain extensions. A failure stays visible even
without a valid output. General retention of Specification-local declarations must
not silently promote temporary constraints into the output Model. Policy conditions,
action effects, sampling, temporal Values, and cross-Model queries follow in stages.
The scalar composition fixtures validate the current contract; these policy and Run
sketches are not solver runs.

## 3. First-level child schemas

This section combines drafted scalar concepts with explicitly proposed richer
extensions. The schema files and root contracts above determine current fields;
these conceptual categories do not prescribe Python inheritance. Temporal,
policy, and reusable-template extensions remain deferred.

### 3.1 Declarations

A Declaration introduces a stable, scoped symbol for a value, domain object, or
computational definition/instance. Common concerns are identity, name, kind, type,
reference scope, applicable restrictions, and provenance.

| Kind | Distinct responsibility | Examples |
| --- | --- | --- |
| Value declaration | Declares a scalar or structured value, with relevant units, shape, and domain. Numeric variables are a case of this kind. | Rent, date, span, flow, stream |
| Entity declaration | Identifies a particular domain object and its properties/references. Domain identity is separate from the declaration and snapshot identities. | Building, parcel, organization, loan agreement |
| Assembly declaration | Specializes an Entity with explicit membership of domain objects/relationships. Membership can overlap. | Phase A, rental portfolio |
| Mathematical Formulation | Groups governing expressions and constraints, with references to shared Values and local declarations. Reusable templates are deferred. | Account calculation, rental valuation |
| Function declaration | Defines a callable signature and symbolic body or pinned implementation reference with declared capabilities. | Discount calculation, supported template constructor |

Assembly is therefore not simply a peer of Entity in an inheritance tree. Likewise,
an Account's structured content can be a Value, while its governing balance and
interest equations belong to a mathematical Formulation. A loan agreement is an Entity
that can be associated with both. A Formulation can relate Values from several Entities,
and an Entity can be associated with several Formulations.

Literals are expressions and need not be named declarations. A reusable function
definition is distinct from an expression calling it. Arbitrary Python functions
do not automatically have an algebraic translation or inverse-solving capability.

Assembly membership, spatial containment, computational scope, and mathematical
equality have separate semantics. Membership does not instantiate another copy of
an Entity or its calculations. Stable references must support shared membership.

### 3.2 Expressions

| Kind | Meaning |
| --- | --- |
| Literal | A typed value, with relevant units. |
| Reference | Refers to a declaration by stable identity in a defined scope. |
| Member/index selection | Refers to a typed field or indexed value, such as `loan.balance[t]`. |
| Operator application | Applies a declared arithmetic, comparison, or logical operator to ordered/named operands. |
| Function application | Applies a referenced function to specified arguments. |
| Query | Traverses relationships or Assembly membership, filters fixed metadata, and projects Entity or Value identities. |
| Aggregation | A Function call over a collection, with explicit empty-input and multiplicity semantics. |
| Conditional expression | A later extension for branches with explicit evaluation and solver semantics. |

An inequality such as `cost <= budget` is a Boolean expression. Merely including
that expression in a Model does not assert that it must hold. It could instead be
a policy guard or a reported comparison. Equality expressions similarly have no
permanent calculation direction. Argument order is significant: `a / b` and `b / a`
cannot be distinguished by an unordered set of dependency edges.

### 3.3 Relations: relationships versus constraints

We have used "relation" in two senses. The draft separates two record kinds:

| Kind | Shape | Meaning |
| --- | --- | --- |
| Relationship | `source`, `target`, `classification`, applicable characteristics | An explicit domain connection, such as membership or spatial containment. |
| Constraint | `id`, `predicate` referencing a Boolean Expression UUID; optional `code`, `name`, `description` | Asserts a mathematical condition that must hold where the Constraint is imposed. |

Thus `Source / Target / RelationType` describes a binary Relationship, but does not
by itself encode a mathematical equation involving several declarations. A Constraint
can reference `NOI == homes * rent - costs` as a structured predicate.

Example: `cost <= budget` as a predicate can be reused by a Constraint that requires
it or by a Policy that branches on it. These uses are not interchangeable.

Expression operands and references already determine their connectivity; a second
independently editable dependency-edge list must not compete with them. The initial
schema uses nested, identified Expression records. Relationships are stored in
`system.relationships`; Constraints are owned by Formulations under `system.formulations`
or `Specification.formulations`, according to where their requirements apply.
Their ownership and semantic roles remain distinct.

### 3.4 Inputs, resolutions, and references

| Concept | Proposed content |
| --- | --- |
| Assignment | Value UUID plus Quantity; fixes content in `Specification.assignments`, or initializes an unknown in `Specification.estimates`. The first draft accepts whole measurement Values. |
| Binding | A local name referring to a shared Value in a Formulation; does not supply or fix content. |
| Recorded content | Content on the Value in a Model revision, supported by provenance and Run diagnostics. No separate Resolution record is planned; precise partial/stale-state handling remains open. |
| Reference | Target identity plus any member/index selector and scope/revision context. Labels alone are not identities. |

A stored resolution never silently becomes a solver constraint. Previous resolutions
may be supplied explicitly as estimates. Reuse as a current result requires evidence
that the relevant definitions, inputs, and evaluation semantics are unchanged.
Changed dependencies must not leave stale values presented as valid current results.
Blank, missing, unknown, error, and zero remain distinguishable.

Declaring the same numerical value at two locations does not make them the same
symbol. Sharing one symbol by reference is distinct from constraining two symbols
to equal one another; the binding specification must make that choice explicit.

### 3.5 Policies and interventions

The Specification owns the selection/configuration of these objects, directly or by
reference. Available actions are a choice set; a Policy is the rule for choosing.
A prescribed action can be supplied without a general adaptive policy.
One complete Policy configuration may coordinate subordinate Policies through
conditional activation, timed handover, or concurrent recommendations with explicit
arbitration. Alternative configurations are compared in separate evaluations.
Section 2.4 sketches both uses; a bare Policy list does not distinguish them.

| Child | Proposed content |
| --- | --- |
| Intervention | Identity, action/template reference, target object references, argument expressions, and applicable preconditions. |
| Action/template definition | Parameters, admissibility rules, and declared effects on entities, values, expressions, relations, and effective periods. May be reusable. |
| Policy | Decision schedule, accessible observations/history, referenced interventions, selection rule, parameters, and tie/no-action behaviour. |
| Policy search specification | Admissible policy family, free parameters/choices, objective, constraints, and training/evaluation scenario sets. |

The policy can select `Convert(Space A, Residential, next_quarter)`; the conversion
definition describes its costs, timing, commitments, and generated content. Selection
does not confer permission to rewrite the rules used to evaluate the action.

Generated definitions must pass explicit validation before a subsequent evaluation
stage. Bounded choices can be represented ahead of time; template instantiation can
later produce new definitions. Unrestricted structural synthesis is a separate,
unimplemented capability, not an automatic consequence of algebraic solving.

Policies receive information available at their decision time. A market quantity
can be inferred by an inverse Specification without becoming controllable in policy
optimization. Forecasts and future realized observations must remain distinct.

### 3.6 Mathematical Formulations

**Agreed direction:** distinguish the following responsibilities:

| Concept | Responsibility |
| --- | --- |
| Value | Identified, typed content that may be unresolved, supplied, or calculated. Flow, Stream, and Account content remain future Value kinds. |
| Formulation | An explicit mathematical container for related expressions, constraints, local declarations, and references to shared Values. |
| Editor component | An authoring or inspection view. Mark8 chapters, blocks, and items do not determine mathematical ownership or solve semantics. |

The Formulation contract should align with the concepts of nested components and shared
references used by Pyomo, while leaving backend construction to the implementation.
It must not imply that arbitrary numerical code supports inverse solving.

Keep one canonical occurrence of each identified record in a Model snapshot.
Referencing an Entity's Value from a Formulation shares that symbol; it does not copy the
Value or give it another identity. A named interface binding is an alias to a Value,
not a fixed-value binding. Fixed/unknown roles, targets, and objectives belong to
the Specification. Recorded results do not change those rules.

**Drafted in [formulation.yaml](../schema/formulation.yaml), version 0.3.0:**

| Part | Draft content |
| --- | --- |
| Identity | Stable UUID, optional code, name, and description. |
| Interface | `bindings`: inline Binding records with required `name` and `value` fields. The latter references a Value UUID; the target declaration supplies its content contract. |
| Mathematics | Expressions and Constraints canonically owned by the Formulation. Other records refer to them by UUID. |
| Local declarations | `values`: canonically owned Values. Shared domain Values remain owned by their existing Entity or Relationship. Local does not mean private. |
| Composition | Owned child Formulations, with acyclic containment; mathematical references can still form simultaneous systems. |
| Reuse | Deferred. There is no template-reference field or template-instantiation mechanism in this draft. |

The Model envelope contains root Formulations in `system.formulations`, with one canonical
home for their mathematics. Entity views can discover relevant mathematics
through references. Formulation containment uses inline child records; UUID references
remain visible across the containing Model. Value keys, Binding names, Constraint
codes, and child Formulation codes are unique within their respective owner collections.
Binding names and Value keys can coincide because their collections are distinct.
Only a Formulation's UUID is required; empty Formulations and parents containing only children
are valid. Including a Formulation's mathematics imposes all descendant Constraints too.
Conditional activation and alternative branches remain deferred.

The Value schema now permits Formulation-local ownership alongside Entity/Relationship
Characteristics. A Binding neither changes ownership nor requires every expression
dependency to be listed in the interface. Reference existence, unique ownership,
scoped names, and Boolean Constraint predicates require semantic checks beyond
generated record validation.

`Binding` is now defined. Definitions contains Function contracts. `formulations`
names collections of Formulation instances, both in System and recursively within
Formulation. Version 0.2.0 replaces the earlier Block name and nested blocks field;
reusable templates and their parameter symbols remain deferred. A Function
call produces an expression result; a Formulation can introduce several related symbols
and constraints. Neither requires a separate schema class for every RK
projection, distribution, or account algorithm. Units, index conventions, domains,
and mathematical meaning must nevertheless be explicit contracts.

The [valuation Formulation fixture](../schema/examples/valuation-formulations.yaml) places the
existing two valuation equations in child Formulations, sharing one unresolved NOI Value
owned by their parent. It is a separate fixture scope from the earlier expression
example, not a second copy of mathematics within one Model. Generated structural
checks and Python round trips exercise this fixture; no equations are executed.
The [schema README](../schema/README.md#formulations) also sketches the future projected-flow
and account interfaces. Their richer payloads follow the scalar checkpoint.
Reusable Formulation templates can be introduced when repeated instantiation supplies a
concrete requirement. Any later generated equations must remain traceable to their
formulation, not competing independently editable copies.

## 4. Rich types and project identity

**Proposed extension points:** structured types, indexed values, reusable components,
and explicit domain bindings. Their detailed schemas follow the scalar examples.

| Concept | Semantics to preserve |
| --- | --- |
| Span | Endpoints, calendar/duration conventions, and boundary inclusivity. |
| Flow | Dated movement amounts; distinguish these from rates and stock balances. |
| Stream | Named constituent flows and explicit alignment/aggregation rules. |
| Account | Structured content for movements and balances; a mathematical Formulation supplies the governing balance, interest, and restriction equations. |
| Entity lifecycle | Existing, proposed, committed, and realized structure; identity can persist through changes of use. |
| Assembly | Shared membership with explicit traversal and aggregation rules; no implicit duplication or exclusive ownership. |

An Entity can be an input reference, a declared candidate, or a template-generated
object. The existence of its declaration is not proof of physical existence at all
times. A use change can preserve the physical Entity while changing its effective
use and associated components. Histories remain available through snapshots and
explicit effective periods.

## 5. Algebraic execution requirements

The proposed adapter contract is:

```text
Model₀ + Specification
    → validate and instantiate the relevant definitions
    → translate supported mathematical members and constraints
    → attempt evaluation/solution
    → map values and generated structure back to graph identities
    → publish Model₁ and the finalized Run record
```

The solver representation may be mutable internally. It is not the authoritative
Model, and its mutation must not affect the input snapshot. Requested outputs need
not be all the unknowns required to solve their governing equations.

Validation has four distinct responsibilities:

1. Document structure and reference integrity.
2. Types, units, indexing, domains, and scope.
3. Specification structure, available information, and backend capabilities.
4. Numerical results, residuals, bounds, and termination evidence.

Equation/unknown counts alone do not prove independence, uniqueness, or solvability.
Represent unsupported problems, underdetermination, inconsistency, numerical failure,
and proven infeasibility accurately. Do not claim uniqueness or optimality without
supporting analysis. A schema validator does not perform these mathematical checks.

**Implemented:** Pyomo 6.10.1 with HiGHS 1.15.1 for the affine scalar checkpoint,
with explicit capability checks and independent candidate acceptance. Scalar/indexed variables,
constraints, components, and finite choices have familiar mathematical representations;
arbitrary entity constructors do not automatically have one.

### 5.1 Execution priorities and capability boundary

**Agreed development direction, 2026-10-01:** start with fixed project structure,
fixed calendar/index sets, and supplied market scenarios. Eligible numerical Values
can change fixed/unknown roles between Specifications. Broaden the supported mechanics
only as the staged examples require them.

Compatibility is a property of a formulation under a particular Specification: its
unknown arguments, domains, indexing, and selected backend. For example,
`revenue = area * rent` is linear if either factor is fixed, but generally nonlinear
if both are unknown. A module-wide compatibility flag would hide that distinction.

| Priority | Mechanics | Initial boundary |
| --- | --- | --- |
| First | Scalar valuation, fixed-member Flow/Stream sums, recurring and straight-line flows, fixed allocation profiles, fixed-rate PV/NPV | Use explicit arithmetic and known coefficients; preserve units, alignment, missing-content rules, and timing conventions. |
| Next | Unknown growth/discount/capitalization rates and basic Account equations | Add bounded nonlinear formulations and initialization where necessary; start accounts with a specified interest regime. |
| Later | Full overdraft/threshold logic, min/max, variable timing, use choices, changing index sets or structure | Require explicit piecewise, discrete, or structural formulations and suitable backend support. |
| Separate numerical stage initially | Random draws and market-path generation; arbitrary policy callbacks | Supply saved scenarios to the valuation model. A callback is not automatically an algebraic formulation. |

The broader priorities above are mathematical assessments from source review.
Only the [bounded affine scalar subset](SCALAR_EXECUTION.md#supported-mathematics)
has executed solver evidence. Distribution-based allocation with fixed parameters can
provide deterministic weights even when sampling from that distribution remains
outside the algebraic solve. Precomputing a quantity that depends on an unknown
would incorrectly remove its dependency and is not an allowed shortcut.

Keep implementation mechanics in code. Supported formulations need symbolic
construction as well as numerical evaluation where both are offered; their agreement
must be checked on shared examples, with residuals and documented tolerances.
Unsupported argument roles or operations must be reported explicitly. The runtime
capability-registry format remains to be implemented. Pyomo with HiGHS is selected
for the affine scalar slice; backends for later nonlinear or discrete capabilities
require separate evidence and decisions.

### 5.2 Scenarios, inverse questions, and policy optimization

Preserve the distinction between these investigations:

| Investigation | What varies | Meaning |
| --- | --- | --- |
| Scenario screening | Supplied sampled futures | Evaluate each future and query which outcomes meet a target; no inverse solver is required. Frequencies or weighted shares are conditional on the assumed scenario distribution. |
| Inverse scenario analysis | One or a few market assumptions | Infer required rent, growth, or exit yield with other assumptions fixed. An inferred market quantity does not become controllable by a policy. |
| Whole-path inversion / reverse stress testing | An admissible trajectory or disturbance sequence | Many paths may meet one outcome target. Specify dynamics, bounds, dependencies, and an additional selection objective; finding a path does not establish its likelihood. |
| Calibration | Parameters of a model or market generator | Estimate against observations or other explicit statistical evidence. A desired project IRR alone does not identify a market distribution. |
| Policy optimization | Project actions or decision-rule parameters | Compare choices against the same externally supplied futures and probabilities; a policy uses only information available at its decision time. |

For a fixed target return, a break-even equation can use NPV at that target rate
instead of embedding an iterative IRR calculation inside each solve. Preserve
period-based versus dated discounting conventions. The usual hurdle-rate/IRR
interpretation needs conventional cash flows; multiple sign changes can produce
multiple or absent IRRs. Reporting IRR can remain a numerical postprocessing step.

The intended progression is one deterministic forward/inverse case, many saved
futures, committed decisions across those futures, then adaptive policies.
Separate per-future optimization with complete future knowledge is a
perfect-information benchmark, not an implementable policy. Retain reproducible
scenario identities, paired comparisons, and separate policy-search/evaluation
sets. Algebraic market-generator inversion is deferred; using and specifying the
generator for Monte Carlo evaluation is not.

## 6. Progressive specification and acceptance examples

S1 and the bounded affine portion of S2 now have [executed checks](research/scalar-execution/README.md).
The later stages remain proposed. At each new stage, first write the input Model,
Specification variants, expected output Model properties, and failure cases.
Then settle the required child schema and implement that stage.

| Stage | Example | Required evidence |
| --- | --- | --- |
| S0: structural review | One building, one valuation component, two overlapping Assemblies | Shared identity; explicit property bindings; membership distinct from scope and spatial relationships. A paper/schema example initially. |
| S1: scalar | One valuation model, forward and inverse Specifications | Model₁/Model₂ preserve equations; previous resolutions do not become fixed values. A1-A4, A7. |
| S2: simultaneous | Coupled equations plus underdetermined/inconsistent variants | Valid cycles, accurate diagnostics, immutable failed/partial outputs. A2, A7, A9. |
| S3: temporal | Indexed flows and an Account with a target balance | Typed member/index references, timing conventions, stock/flow distinction, and supported inverse members. A4, A6-A7. |
| S4: structure and intervention | One space, two uses, one decision date, explicit conversion costs/delay | Bounded alternatives, identity through time, then equivalent template-generated structure. A5-A8. |
| S5: sequential policy | Two-pad model on readable market paths | Commitment and feasibility rules; observations available at the decision time; traceable new Models. |
| S6: policy search | Compare policies across common scenario ensembles | Policy search distinct from scenario hindsight; independent evaluation and reproducible comparisons. |

### First numerical acceptance example

Keep the same equations in every snapshot:

```text
NOI = homes * annual_rent_per_home - annual_operating_cost
capital_value * capitalization_rate = NOI
```

Use units of dwellings, AUD/dwelling/year, AUD/year, AUD, and 1/year as appropriate.
The rate convention is annual, with a positive capitalization rate. These are
illustrative arithmetic inputs, not calibrated financial assumptions.

| Specification | Fixed values | Unknowns | Expected resolutions |
| --- | --- | --- | --- |
| P1 on Model₀ | homes = 20; rent = 30,000; operating cost = 50,000; cap rate = 0.05 | NOI, capital value | Model₁: NOI = 550,000; capital value = 11,000,000 |
| P2 on Model₁ | homes = 20; operating cost = 50,000; cap rate = 0.05; target capital value = 10,000,000 | rent, NOI | Model₂: rent = 27,500; NOI = 500,000 |

P2 must not inherit P1's fixed-rent role or enforce the previous NOI/value resolutions.
Model₀ and Model₁ remain unchanged. Declaration identities and symbolic equations
survive both Runs. The values above are now also observed results from the
implemented adapter, with genuine forward-output reuse and retained
[Run and Model evidence](research/scalar-execution/README.md).

## 7. Next implementation and later specification work

The scalar Entity, Value, Expression, Constraint, Formulation, Model,
Specification, and Run contracts have drafts and bounded conformance checks.
[LinkML is selected](research/current-schema-comparison/DECISION.md); completing
native CUE research is no longer a prerequisite.

Follow the [library migration sequence](LIBRARY_ARCHITECTURE.md#migration-checkpoints):

1. **Completed:** map replacement of the current graph domain core, defining canonical records,
   UUID resolution, generated-record access, immutability, public interfaces,
   and the consumers that must migrate. Distinguish reusable algorithms from
   obsolete data-model assumptions.
2. **Completed:** build the minimal schema-backed core directly in `src/rangekeeper/`: private
   generated records/validators, domain APIs, composition, codecs, and immutable
   revision storage. Check packaged use before relying on it for execution.
3. **Completed:** probe and pin Pyomo/HiGHS, then implement scalar execution in
   `rangekeeper.execution` against this core. Use the actual composed
   Specifications and declared expressions; independently verify candidates
   before publishing authentic forward/inverse Runs and new Model revisions.
4. **Completed for the affine slice:** reuse a genuine output with new solve roles; check failures, numerical limits,
   units, settings, provenance, and direct batch accounting. Temporary
   Specification mathematics does not become permanent Model mathematics.
5. **Next:** migrate graph operations and consumers incrementally; then add temporal and
   financial Value schemas, indexed formulations, scenario evaluation, committed
   choices, and policies in the order described in section 5.1. Reusable
   templates follow demonstrated requirements.

The generated-record/domain API boundary and initial unit policy are specified in
the migration map; production generation and verification are implemented.
Remaining design work includes additional unit profiles and backend capabilities,
rich Value payloads, policy/intervention
semantics, structural publication, and full derived-provenance linkage. Scalar
root names, UUID identity, Formulation ownership, and accepted-only output rules
are already defined and should not be presented as wholly open questions.

File schema version, Model revision, and evaluator/operator version have different
meanings. The earlier [schema tooling evaluation](SCHEMA_TOOLING_EVALUATION.md)
retains its historical comparisons; the accepted decision and architecture govern
current implementation.

## 8. Precedents and related documents

- [Pyomo parameters and variables](https://pyomo.readthedocs.io/en/stable/explanation/modeling/math_programming/parameters.html):
  fixed parameters and free variables have different solve semantics; a mutable
  parameter does not become an unknown merely because it can change between solves.
- [Pyomo.GDP](https://pyomo.readthedocs.io/en/stable/explanation/modeling/gdp/modeling.html):
  Boolean expressions, logical constraints, and alternatives containing constraints.
  This supports the proposed distinction between a predicate and its asserted use.
- [SciML interfaces](https://docs.sciml.ai/SciMLBase/stable/):
  separates numerical problems, algorithms, and solutions. Our graph snapshots and
  Run record are an RK design, not an implementation of a universal six-object standard.
- [Two-pad policy example](PROJECT_DEFINITION_AND_POLICY_EXAMPLE.md):
  longer-term example, provisional financial assumptions, literature, and policy checks.
- [Existing graph workflow](GRAPH_WORKFLOW_FORMATS.md):
  implemented ingestion concepts, separate from the proposed object model here.

The core contracts above supersede the earlier narrower use of Model as definitions
without resolution properties and placement of a particular management policy in
the baseline Model by default. The ensemble update supersedes the exactly-one-output
interpretation of Run; successful outcomes remain Model snapshots, while failure
publication and incomplete-execution rules are still open.
