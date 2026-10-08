# Project definitions, execution, and policy optimization

> Historical redevelopment proposal. Its scope and unimplemented examples describe the original design discussion. Use the [current guides](../README.md) for runtime contracts.

Status: agreed design direction and representative example, recorded 2026-09-22;
equation-oriented modelling and progressive examples agreed 2026-09-23; aligned
with the immutable Model/Specification/Run contract on 2026-09-24.
The example is not implemented or numerically validated. Scalar Model,
Specification, and Run record contracts are drafted in LinkML; richer policy and
temporal schemas and their runtime interfaces remain to be specified. The financial
figures below are illustrative inputs, not calibrated estimates or predicted results.

The current object-model reference is
[Model, Specification, and Run: object model and requirements](../concepts/model-specification-run.md).
This note retains the representative policy example and its provisional assumptions.
The 2026-10-01 [scenario and policy composition sketches](../concepts/model-specification-run.md#scenarios-and-policy)
clarify that one Specification and Run can evaluate multiple futures and alternative
complete policies, publishing multiple Model outputs. Additive `includes` assemble
one investigation; `cases` specify separate investigations, recorded by ordinary
child Runs. Policy alternatives remain distinct from cooperating subordinate policies.
Scalar Specification composition and finalized Run records are drafted; direct
subordinate executions use `Run.spawns`. This policy example remains unimplemented.
The 2026-10-01 [execution priorities](../reference/execution.md#supported-mathematics)
and [scenario distinctions](../concepts/model-specification-run.md#scenarios-and-policy)
clarify the route to this example: deterministic valuation under supplied markets,
evaluation on saved futures, committed decisions across those futures, and then
adaptive policies. Algebraic inversion of market generation is a separate capability.
It is a design reference, not documentation of an implemented RK API.
The current bounded ingestion workflow is documented separately in
[Format-independent workflow execution](../reference/workflow.md).

## Purpose and sequence

The longer-term aim is to define a project, its available design choices, and its
management policies as inspectable, portable data; execute those definitions under
different market scenarios; and compare the resulting physical projects and
financial outcomes. Users should eventually be able to search for policies suited
to their anticipated markets, site, permitted uses, design constraints, and objectives.

The current [library plan](../concepts/architecture.md) retains LinkML and builds the
canonical core directly in the library. The agreed sequence is:

1. Use the completed [domain migration map](DOMAIN_MIGRATION_MAP.md), then implement the minimal
   schema-backed records, validation, and immutable storage in the library.
2. Execute the scalar forward/inverse model with Pyomo/HiGHS, then formulate and
   implement progressively richer tests, culminating in the two-pad policy example.
3. Validate the policy example with readable scenarios before evaluating and
   optimizing policies across larger scenario ensembles.
4. Subsequently connect the approach to EstateMaster reconstruction and Twenty
   browsing. Neither integration is a prerequisite for specifying the example.

Backwards compatibility is not a binding constraint on this design. Existing RK
and Mark8 work can supply useful concepts and implementations without determining
the new boundaries.

## Agreed architectural direction

1. **A Model is an immutable graph of declarations, expressions, and relations,
   including their properties and recorded resolutions.** Loading or displaying it
   does not execute it.
2. **Resolution preserves symbolic meaning.** A resolved value is not a new permanent
   constraint and does not replace its declaration or governing equations. Rich
   domain definitions remain distinct from their resolved values within the graph.
3. **A Specification specifies the investigation.** It supplies inputs, fixed/unknown roles,
   targets, objectives, additional definitions, interventions, and policies as needed.
   A particular management policy belongs to the Specification, directly or by reference.
4. **A Run can produce multiple new Model snapshots.** Each outcome identifies its
   scenario and complete policy configuration. Its content can differ in resolution
   properties, project structure, or both. Inputs remain unchanged. Failed or partial
   resolution must be explicit; exact lifecycle rules are proposed in the core note.
5. **Execution is traceable.** The Run records input/output Models, the exact Specification,
   runtime identity, actual inputs, diagnostics, decisions, and generated content.
6. **Dependencies and executable behaviour are explicit.** Generated definitions are
   data until an explicit validation and evaluation stage uses them. Their presence
   does not cause automatic or unbounded policy reapplication.

Conceptually:

```text
Model₀ + Specification → Run → {Model₁, …, Modelₙ}
```

The [core specification](../concepts/model-specification-run.md) defines the root
responsibilities and drafted scalar child schemas. Richer policy/temporal
extensions and the migration from existing RK classes still require implementation
design; the current scalar root names and field contracts are already defined.

The project graph, equation structure, and execution plan have different semantics.
The equation structure relates quantities to equations and need not be a DAG. The
runtime derives an execution plan for a particular Specification, potentially scheduling
simultaneous solution blocks within a DAG. These are views and derived plans, not
three independently authored models. One definition system can operate on many
domain value types without making every value the same kind of spatial `Entity`.

For the policy example, the Model and Specification together describe the project,
possible interventions, and decision behaviour. Each scenario/policy evaluation
produces its own Model. Calling it a future-history requires explicit temporal
content: existence, availability, construction, effective relationships, and financial
movements must remain distinguishable. Those temporal contracts are not yet defined;
"history" is not a separate schema class or a guarantee of the current Value draft.
An ensemble retains distinct conditional outcomes, not predictions asserted to be certain.

The initial execution model should use finite collections, a finite simulation
horizon, and explicitly bounded solvers where required. A DAG alone does not prove
termination of arbitrary Python operations. Any unrestricted Python extension would
need a separately defined execution contract; timeout enforcement is not a proof of
successful termination.

## Equation-oriented modelling

The definition should support declaring mathematical relationships without assigning
every quantity a permanent input/output direction. A suitable declared quantity may
be fixed in one Specification and unknown in another. Genuine constants and structural
declarations may remain fixed by definition.

For example, these same equations can support valuation, required-rent calculation,
or an implied capitalization rate:

```text
NOI = homes * annual_rent_per_home - annual_operating_cost
capital_value * capitalization_rate = NOI
```

The capitalization rate here converts capital value into annual income; its units
and annual convention must be explicit. The equations are equalities, not ordered
assignments. A numerical solver may evaluate residuals without symbolically
rearranging every equation.

This capability does not promise that every inverse problem has a unique solution,
or that a selected solver can find it. Underdetermination, inconsistency, multiple
solutions, discrete restrictions, and numerical failure require distinct treatment.
Equal numbers of equations and unknowns do not establish independence or uniqueness.
Failure to converge must not be reported as proof of infeasibility.

A quantity's domain meaning is separate from its role in a solve. An implied rent
can be an unknown without becoming controllable by a development policy. Policy
optimization must not alter the supplied market scenarios or exploit unobservable
future information. Inferred values are run outputs, not replacements for source
observations. Exact bindings, uncertain observations, defaults, and initial guesses
must remain distinguishable.

For graph generation, start with bounded candidate structures such as a finite set
of development templates for each pad. Solving their selection or dimensions can
precede materializing the selected project entities. Arbitrary Python callbacks and
unbounded graph generation do not automatically become invertible; they need a
declared supported interface or an explicit outer search procedure.

## Proposed starting specification

The top-down root contracts, child-schema proposals, validity rules, and staged
acceptance examples now live in
[Model, Specification, and Run: object model and requirements](../concepts/model-specification-run.md).
They distinguish value/entity/component declarations, expressions, domain
relationships, mathematical constraints, bindings, resolutions, and Specification-owned
policies. Scalar record names and shapes are drafted in LinkML; richer extensions
remain proposals, and the schema-backed runtime API is not yet implemented.

Begin with the scalar forward/inverse example there while reviewing a small
entity/component/overlapping-Assembly example on paper. Richer RK types follow
as subsequent stages require them.

### Proposed progression of examples

| Stage | Example | What it reveals |
| --- | --- | --- |
| 0 | One building, one valuation component, two overlapping Assemblies, initially on paper | Identity, property bindings, and distinct domain/computational relationships. |
| 1 | One static valuation model with forward and inverse Specifications | The same equations can be reused with different fixed/unknown roles. Keep dwelling count fixed initially. |
| 2 | A simultaneous equation block and underdetermined/inconsistent cases | Cycles can be valid; model diagnostics and solve statuses are part of the contract. |
| 3 | Time-indexed cash flows and an inverse target | Indexing, dates, aggregation, units, and reproducible valuation conventions. |
| 4 | A bounded choice of developments and integer quantities | Discrete feasibility, constraints, and generation of project entities from selected templates. |
| 5 | Sequential policy decisions on specified market paths | Commitments, state transitions, information limits, and graph histories. |
| 6 | Policy search across scenario ensembles | Objectives, paired comparisons, held-out evaluation, and limits on optimality claims. |

At each stage, first specify the Model, Specification variants, expected outcomes, and
failure cases; then implement and validate that stage. The full two-pad example
below remains the destination and a check against designing a scalar-only dead end.
LinkML and Pyomo with HiGHS are selected for the scalar stage. Richer-stage
execution capabilities remain to be established as their examples are specified.

## Representative example: two-pad carpark redevelopment

### Decision being investigated

Is it worth paying upfront to preserve a choice of uses, and which decision rules
best exploit that flexibility under uncertain markets and limited capital?

There are two distinct choices:

- An initial design/approval arrangement determines which later actions are possible.
- A policy determines when and how to exercise those available actions as observations
  arrive.

### Site and development templates

The site contains two pads, each providing 40 public parking spaces and initially
earning AUD 60,000 per year after operating expenses. Each pad can retain that use
or receive one of the following development templates.

All amounts are illustrative real AUD at initial market factors of 1.0.

| Per-pad development | Housing | Workspace |
| --- | --- | --- |
| Product | 20 rental homes | 1,500 square metres of workspace |
| Construction cost | AUD 6 million | AUD 4 million |
| Construction duration | 2 years | 1 year |
| Initial annual net operating income, excluding public parking | AUD 550,000 | AUD 400,000 |
| Public parking restored at completion | 40 spaces | 40 spaces |

Each development template includes its required private parking and servicing.
The restored public parking income must be accounted for separately from the
building income above, without double counting. Exact operating-income treatment
and temporal conventions are among the details still to specify.

### Site, capital, and commitment constraints

- At least 40 public parking spaces remain operational at all times.
- Construction closes the spaces on its pad, so only one pad may be under
  construction at a time. Completing that phase restores the parking capacity
  needed to start work on the other pad.
- The first development requires AUD 800,000 of shared infrastructure.
- AUD 9 million of additional equity is available. Operating income can be reinvested;
  funding required to finish already committed construction must remain covered.
- A phase's use becomes fixed when construction starts, and that phase must complete.
  Waiting between phases is allowed; pausing or switching a committed phase is not
  part of this initial example.
- Construction prices vary before commitment. For the initial example, the contract
  price is fixed when a phase starts.

These are synthetic project rules, not statements of actual planning requirements.

### Horizon and initial flexibility choice

The simulation uses 48 quarterly periods over 12 years. New construction may start
through year 8. A common terminal valuation convention applies at year 12 to both
completed developments and any retained parking. Precise boundary timing remains
to be specified before implementation.

Compare:

- **Committed uses:** select each pad's intended use at the outset.
- **Flexible uses:** pay AUD 250,000 upfront for the design, approvals, and servicing
  provisions that allow each pad's use to be chosen at its construction start.

The flexibility premium is incurred even if the later option is never used. Keep
timing flexibility and product flexibility separately identifiable in comparisons.

## Markets, information, and the policy

### Scenario inputs

Begin with three uncertain drivers: housing rents, workspace rents, and construction
prices before commitment. Housing and workspace markets are imperfectly correlated.
Keep capitalization rates and discount conventions fixed and explicitly declared
initially. Their numerical values and the stochastic processes are not yet agreed.

Generate and identify exogenous market paths independently of policy execution.
Every competing policy sees the same paths. Record the effective paths or sufficient
generation details to reproduce them. A policy's actions must not accidentally change
the random market draws supplied to another policy.

The simulator may have the full path available, but the policy may receive only
observations available by the decision time. It must not receive future realizations
or hidden market-generator state as if those were observed information.

### Observations, feasible actions, and decisions

At each decision time the policy receives:

- Project state: remaining pads, completed buildings, and construction underway.
- Financial state: cash, available equity, and outstanding commitments.
- Current and past market observations.
- Actions permitted by the design arrangement and project constraints.

Its action is one of:

```text
Wait
Start housing on an available pad
Start workspace on an available pad
```

Existing construction proceeds according to its commitment. Constraint enforcement
and state transitions should be explicit, so policy search cannot improve results
by choosing physically or financially inadmissible actions.

### Initial policy family to evaluate

For each feasible development, estimate:

```text
score = estimated incremental NPV over retaining parking
        / additional capital required
```

This estimate includes construction, foregone parking income, applicable shared
infrastructure, and the remaining evaluation horizon. It uses a declared forecasting
rule based on available observations. Carrying currently observed market levels
forward is a candidate starting rule, not yet a finalized valuation specification.

The policy starts the feasible use with the highest score if its score exceeds that
use's threshold for the required number of consecutive observations; otherwise it
waits. The initial parameters to search are:

- Housing threshold.
- Workspace threshold.
- Confirmation period.

Tie-breaking, the confirmation rule when feasibility changes, and the parameter grid
remain to be specified. A small transparent grid search is sufficient for the first
experiment. Its winner is the best tested policy within that family and market model,
not a claim of optimality over every possible policy.

## Evaluation and expected trade-offs

| Strategy | Question it isolates |
| --- | --- |
| Retain both carparks | What is the outcome of doing nothing? |
| Fixed uses; start as soon as feasible | What does a committed development strategy achieve? |
| Fixed uses; policy-controlled timing | What is the value of waiting and phasing? |
| Flexible uses; policy-controlled timing | What additional value comes from choosing uses later, net of the flexibility premium? |

All strategies obey the same site and capital constraints. A baseline that cannot
start immediately must follow its declared feasible-start rule rather than receive
extra funding or an exemption from constraints.

The initial objective is expected incremental NPV relative to retaining parking,
subject to the hard constraints. Also report:

- The full outcome distribution and probability of loss relative to that baseline.
- Average outcome in the worst 10% of scenarios.
- Peak equity required and the cash/commitment history.
- Uses, quantities, and completion dates actually delivered.
- Paired outcome differences between strategies on the same scenarios.

Choose policy parameters using one scenario set and evaluate them on an independent
set. Then vary market assumptions, such as cross-market correlation, to assess
robustness. Do not optimize a different policy after seeing each scenario's future.

The example is intended to reveal several competing effects, not assume their winner:

- Workspace costs less and completes sooner, potentially funding later housing.
- Housing produces more initial annual income but consumes more capital and time.
- Waiting preserves parking income and choice while exposing later construction
  to changing costs and potentially missing attractive market conditions.
- The first phase pays for infrastructure that also benefits the second.
- Product flexibility may be valuable when markets diverge and less useful when
  they move together; its upfront cost can outweigh its benefit.

A later extension can add a target such as delivering at least 20 homes by year 8.
That target is not a baseline requirement; it tests how changing objectives and
constraints changes the preferred policy.

## Execution and retained outcomes

There are two explicit loops:

```text
Within one scenario/policy evaluation:
observe -> choose action -> update project and cash -> advance one quarter

Within an ensemble investigation:
evaluate candidate policies across shared scenarios -> compare
-> select a policy only if selection is part of the investigation
```

An action produces the appropriate graph changes and flows: buildings and units,
construction and operating spans, changes to parking availability, infrastructure
relationships, capital expenditure, operating income, and terminal proceeds.
Existing entities' histories remain inspectable when their use ends or changes.

One Run can publish the Model snapshots from many evaluations, retaining the exact
Specification and each output's complete policy configuration, scenario identity, actual
inputs, implementation versions, financial diagnostics, and decision trace.
The current design uses explicit concrete Specifications for each case and ordinary
spawned Runs for their executions, referenced through `spawns`. Shared requirements and supplied futures are additive
Specification contributions; batches do not implicitly pass requirements to cases.
A complete policy may coordinate several subordinate policies without producing one output
Model for each subordinate policy or every internal transition.
The trace links observations and feasibility checks to the selected action and its
generated content. Queries over contextualized output Models derive chosen metrics,
distributions, and paired comparisons; distributions are not mandatory Run outputs.
Different policies or scenarios can produce different Models without changing the
input Model or other evaluations. Recorded resolutions do not
become permanent constraints in subsequent Specifications.

For eventual Twenty publication, each upload creates an entirely new project.
Exported snapshots are independent; there is no merge or synchronization back into
the originating CRM project. Twenty is expected to serve primarily as a viewer of
the published definition and selected run outcomes.

## Questions to settle in the schema and test specification

| Area | Remaining decisions |
| --- | --- |
| Definition/value representation | Exact types for declarations and their resolution properties, templates, operations, and Run records within the agreed immutable-snapshot contract. |
| Equation/Specification boundary | Fixed and unknown quantities, constants, units, domains, expressions, relations, targets, objectives, and observation semantics. |
| Solution diagnostics | Structural validity, unsupported problem classes, residuals and scaling, tolerances, multiple solutions, and distinctions between numerical failure and proven infeasibility. |
| References and ownership | Stable identities, reference scope, output selection, and whether definitions are associated with entities or project-level containers. |
| Temporal state | Existence versus construction versus availability; effective periods of relationships; representation of planned, committed, and completed objects. |
| Quarter ordering | Observation time, decisions, payments, completions, income recognition, deadline inclusivity, and the terminal valuation point. |
| Capital accounting | Equity draw rules, payment profiles, reinvestment, funding reservations, infrastructure cost timing, and the definition of peak equity. |
| Valuation | Discount and capitalization rates, NOI forecasts, retained parking income/value, sale costs, and consistent treatment of the common starting site. |
| Policy semantics | Specification-owned intervention/policy records; exact score, forecasts, thresholds, confirmation, tie-breaking, and handling unavailable inputs or an empty feasible-action set. |
| Scenario generation | Processes, parameters, correlation, observable information, seeds/path identities, and training/evaluation separation. |
| Generated identity and lineage | How generated entities are identified within a run and traced to their definitions; which graph snapshots or changes must be retained. |
| Schema tooling | How to express and validate the same semantics across Python, portable files, and eventual app adapters. JSON Schema, LinkML, and CUE remain candidates, not selections. |

Generic `Feature` replacement, `Event`/`Expression` categorization, and moving all
domain types into `rk.graph` are not agreed implementation decisions. Use the
example to assess those choices rather than treating them as prerequisites.

## Checks to formulate after the schemas

First formulate the small forward, inverse, simultaneous, and diagnostic examples
above. For the later policy model, use five readable market stories: sustained
housing strength, sustained workspace strength, a slump followed by recovery, an
early boom followed by a crash, and a construction-cost surge. Specify their values
and expected behaviour before using them as executable fixtures.

The later test should establish:

- **No future information:** scenarios with identical observation histories produce
  identical decisions until their observations diverge, for the same policy and
  initial state.
- **Definition preservation:** save/load does not execute a definition, and runs do
  not mutate it or the inputs/results of other runs.
- **Snapshot and resolution semantics:** scenario/policy outputs are new Model revisions;
  recorded values do not silently become fixed constraints in a subsequent Specification;
  partial, failed, or stale results are not presented as valid current resolutions,
  and intended evaluations remain accounted for even if no valid output is available.
- **Feasibility:** public parking, funding coverage, construction commitments, use
  restrictions, and the agreed time boundaries are respected.
- **Consistent generation:** entities and relationships are created once when
  appropriate, with stable within-run identity and traceable origins.
- **Consistent finance:** cash movements reconcile with commitments and equity;
  income starts and ends at the specified times; terminal value is counted once.
- **Fair comparison:** policies share market paths, horizon, starting conditions,
  and valuation conventions, with the correct design and flexibility costs.
- **Reproducibility:** repeating the same definition, inputs, paths, and pinned
  implementation reproduces decisions and outcomes within specified tolerances.
- **Honest optimization:** held-out evaluation is distinct from policy selection;
  no policy advantage, numerical result, or global optimum is assumed in advance.

These are intended acceptance properties, not reports of tests already performed.

## References and precedents

- [Flexibility under uncertainty notebook](../../examples/walkthrough/flexibility_under_uncertainty.ipynb):
  the stop-gain policy responds to the first qualifying pricing-factor observation
  above 1.20, adjusts the holding period, and compares flexible and inflexible outcomes
  on common market scenarios. It is a conceptual reference, not the implementation
  of the proposed two-pad example.
- Geltner and de Neufville, [Flexibility and Real Estate Valuation under Uncertainty:
  A Practical Guide for Developers](../../examples/walkthrough/resources/deNeufvilleGeltnerValuationUnderUncertainty.pdf)
  (2018): Chapter 9, especially printed p. 65, for paired scenario comparisons;
  Chapters 18-19 and Box 18.1 on printed p. 133 for decision rules and information
  limits; Chapter 21, printed pp. 160-161, for product mix; Chapter 22, printed
  pp. 173-174, for sequential phasing and commitment to finish a started phase.
- [Current Policy implementation](https://github.com/daniel-fink/rangekeeper/blob/5a111b00bb4990a883af08d6ccbc7561b4bab445/src/rangekeeper/policies/observation.py): a pair of arbitrary
  Python callbacks. Its current API does not enforce the proposed information,
  immutability, or termination boundaries.
- [Bazel actions](https://bazel.build/extending/rules#actions): separating a declared
  input/output dependency from execution.
- [MLIR language reference](https://mlir.llvm.org/docs/LangRef/): typed operations,
  values, and explicit dependencies as a common computational representation.
- [CEL](https://cel.dev/): a precedent for deliberately bounded expression semantics.
  These execution precedents are not selected implementation dependencies.
