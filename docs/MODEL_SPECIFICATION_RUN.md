# Model, Specification and Run

The three roots separate declared project knowledge, an investigation, and evidence
of what happened. Each root has revision metadata. UUID references identify exact
revisions; a display name never resolves a document implicitly.

## Model

A Model declares Definitions, System content and Provenance. Definitions include
Measures, classifications and Functions. The System contains Entities, explicit
Assembly memberships, Relationships, Characteristics and mathematical Formulations.
Values belong to one owner and use keys local to that owner. Measurements retain
units; Flow Values retain dated or period-based Movements. Rich properties keep
their typed content and Claim references.

Equations state relationships. They do not choose which Value is fixed or unknown.
Recorded amounts are observations or prior results, not permanent assignments.
This is why the same Model can answer forward and inverse questions. Structural
ownership, graph relationships and mathematical constraints remain separate.

## Specification

A Specification selects an exact input Model and supplies assignments, unknowns,
estimates, bounds, objectives or policy requirements. `Reference` identifies
a Value or Movement by UUID. Includes compose additive
contributions; conflicting declarations fail. Cases describe separate attempts in
a batch. A partial contribution can exist before all external references resolve.

Composition builds a derived view without changing contributors. Validation checks
that view against its resolver. Execution support is narrower than the full schema:
the [executor](SCALAR_EXECUTION.md) supports finite affine feasibility, including
temporal equations and the supported exogenous policy slice. Declaring an objective
or nonlinear expression does not mean that executor can solve it.

## Run

A Run records one finalized attempt or batch, its Specification revision, accepted
output revisions, child Runs and a Report. Completion status and mathematical
solution status have different meanings. A deadline or backend error does not prove
infeasibility. A batch accounts for each direct case and the union of its outputs.

The Report retains diagnostics, runtime implementations and settings, trace steps
and policy decisions where applicable. Local construction checks the report.
Resolver-backed validation also checks document kinds, references, lineage and
permitted publication changes. It does not rerun mathematics. Independent numerical
acceptance occurs in execution before an output is published.

## Revisions and evidence

Records are immutable. Generated `replace()` builds another record while retaining
omitted/null/empty distinctions. `Model.revise()` and `Specification.revise()` apply
revision rules; metadata-only changes are not meaningful content revisions. Run has
no revise operation because it records a finalized event.

Each Model revision is a complete immutable snapshot. Creating M2 leaves M1 intact.
Unchanged declarations and changed amounts retain their Value and Movement UUIDs;
the new Model revision gets a new UUID. A Reference resolves against the Model that
contains it, or against the exact input Model selected by a Specification. A Run
keeps that Specification pin, so its evidence keeps the original meaning.
See [references and identity](REFERENCES.md) for copying and calculation rules.

Strict JSON/YAML codecs use an explicit root kind. Stores are append-only by UUID.
Reusing an ID for different content is an error. Source workflows retain Claims and
source addresses; dataframe and viewer projections are detached from this evidence.

## Scenarios and policy

A captured scenario records a realization, generator identity, versions and
availability. Replay uses captured values. A policy observes only information
available at the decision date, selects a declared action, and records its reason.
Financial observation formulas belong to the application policy; generic replay
owns causal availability and termination.

These contracts support comparing fixed strategies and adaptive choices on the same
captured futures. They do not promise general stochastic optimization, endogenous
policy search, nonlinear execution or arbitrary runtime Functions.

See [architecture](LIBRARY_ARCHITECTURE.md), [domain methods](DOMAIN_CORE.md),
[expressions](EXPRESSION_CONTRACT.md), [scenarios](SCENARIOS_AND_POLICIES.md) and
[Runs/storage](RUN_AND_STORAGE.md) for the detailed contracts.
