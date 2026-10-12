# ADR-006 Walkthrough curriculum and implementation plan

Status: agreed curriculum; notebooks 01–02 accepted locally; later lessons planned. Recorded 2026-10-12.

Retain the accepted Basic DCF notebook and build five further lessons around one
continuing project. Use the legacy Rangekeeper mixed-use property for its objects,
relationships and geometry; Garden City for the development and uncertainty
framework; and SFFA for forward and inverse financial questions. Carry forward
the decision and funding lessons from the two-pad proposal.

This record owns the curriculum, teaching objectives and remaining work. It does
not establish acceptance of new notebooks or authorize all required library
changes. The [walkthrough guide](../guides/walkthroughs.md) owns execution and
local publication. The [execution reference](../reference/execution.md) and
[scenario and policy reference](../reference/scenarios-and-policies.md) own current
capability limits.

## Accepted scope

- Six lesson notebooks in total, including the existing notebook 01.
- Notebook 01 remains the accepted small DCF example. It does not become a model
  of the mixed-use property merely by changing its labels.
- Notebooks 02–06 use the same property and introduce complexity in small steps.
- Move the design material earlier so later financial and policy questions refer
  to objects the reader already understands.
- Place forward/inverse solving in notebook 03, after the project introduction.
  This replaces the earlier suggestion for a separate inverse-solving notebook 02.
- Use the six other existing notebook sources as teaching references. Consolidate
  their useful lessons into five new chapters rather than migrate them one for one.
- Publish each accepted chapter locally through Jupyter Book 2. Public publication
  and retirement of legacy material remain separate work.

## Project and conceptual continuity

The continuing project is the legacy mixed-use property: two buildings, a shared
basement plinth and shared building services. Retain Building A's hotel,
residential, retail and parking components; Building B's residential, retail and
parking components; and the actual containment and service relationships.

Preserve source identities. Distinct objects can have the same human-readable
name. Keep spatial containment, functional grouping and service relationships
separate. A service link is not a cost allocation rule. Specify allocations and
contributor selection so shared costs enter project totals only once.

The completed property design is the physical reference. The development schedule,
funding arrangements, interim site use and flexibility provisions are additional
teaching assumptions. Record their provenance and do not present them as facts
from the legacy graph or transfer Garden City or two-pad numbers without explanation.

A short book introduction establishes the following terms. It is not a seventh
lesson notebook.

| Term | Meaning |
| --- | --- |
| Base plan | What is proposed, in what sequence, and when |
| Base case | Financial results of that plan under stated reference assumptions |
| Market scenario | A possible history of external conditions |
| Flexibility strategy | Choices preserved, their costs, and rules for exercising them |
| Realised development | What is built and when after applying the rules to a scenario |

Keep a common starting state, evaluation horizon and valuation convention when
comparing strategies. Declare changes in capacity, use, cost or design as explicit
variants. Include a meaningful wait or do-nothing baseline and any retained asset
value without counting terminal value twice.

## Lesson sequence

| Notebook | Theme and question | Added Rangekeeper depth |
| --- | --- | --- |
| 01 Basic discounted cash flow | What is this income stream worth? | Flow, Span, projections, Stream, aggregation and discounting |
| 02 From design to property economics | Where do income, costs and value come from? | Entities, typed relationships, views and graph aggregation |
| 03 A development plan and its financial limits | What does this plan require, and what can the market support? | Relations, Specifications, known/unknown roles and inverse solving |
| 04 One plan, many market futures | How does the same committed plan perform in different markets? | Scenarios, market paths and repeatable evaluation |
| 05 When to commit | When should we start each part of the project? | State, observations, decision rules and commitments |
| 06 Which choices are worth preserving? | Is it worth paying now to retain a later choice? | Design alternatives, strategy comparison and robustness |

### 01 Basic discounted cash flow

Retain [basic_dcf.ipynb](../../examples/walkthrough/basic_dcf.ipynb) as the numerical
foundation. The reader constructs dated amounts, projects income and expenditure,
combines line items, calculates sale proceeds and discounts cash flows.

**Objectives.** Understand amounts, units, periods and frequencies; display,
resample and aggregate flows with minimal configuration; distinguish operating
income, capital expenditure, sale proceeds and present value; explain the forecast
period beyond the holding period.

**Teaching material.** Retain the reference table image, small code blocks, native
Polars displays and short checks tied to the lesson. End with the bridge from
valuing specified flows to deriving those flows from property objects. Explain that
numerical Flow operations do not themselves declare an acausal model.

**Status.** Accepted with [notebook evidence](../research/basic-dcf-2026-10-08/README.md),
[native display evidence](../research/native-polars-display-2026-10-08/README.md)
and [local book evidence](../research/jupyter-book-2-2026-10-08/README.md).

### 02 From design to property economics

The [detailed chapter outline](006-notebook-02-outline.md), condensed to eight
sections on 2026-10-13, records the agreed
section sequence, narrative, code tasks and required visual aids. The
[project brief](../guides/mixed-use-project.md) separates verified source facts
from teaching assumptions and links the complete pinned source package. Source
preparation is [verified](../research/notebook-02-source-2026-10-12/README.md);
[notebook execution and local rendering](../research/notebook-02-2026-10-12/README.md)
are now verified. The hosted Speckle version is expired; a local Speckle SDK viewer
reads the captured archive instead.

Introduce the property visually, then inspect its graph. Work from one floor to
all relevant floors, then to buildings, shared infrastructure and the whole property.

**Worked problems.** Identify the objects and relationships; calculate one floor's
income from area and use assumptions; apply the rule across the appropriate
objects; add operating and capital costs; assemble building and property pro formas.

**Objectives.** Choose a relationship view for a particular question. Trace a total
to its contributors. Preserve identity despite repeated labels. Distinguish a
physical dependency from a reporting group or allocation rule. Count shared costs
once, including costs on objects that have no operating income.

**Rangekeeper depth.** Introduce Model content, entity selection, graph views and
hierarchical reductions. Show one transparent calculation before generalising it.

**Teaching material.** Adapt legacy `load_design` and `drive_model_from_design`.
Pair the property view with a simplified graph. Reveal one relationship type at a
time. Use an area sunburst and a corresponding financial breakdown.
Let the reader change one use assumption and trace its effect while geometry stays fixed.

### 03 A development plan and its financial limits

Turn the proposed completed property into a development problem. Begin with fixed
construction and opening dates for the shared works and the two buildings.

**Worked problems.** Build the base plan and dated base-case cash flows. Then ask
the SFFA-style forward question: given costs, finance assumptions and required
returns, what income is required? Reverse it: given market-supported income, what
cost or land price is supportable? Finally, examine too many unknowns and
incompatible requirements.

**Objectives.** Declare financial relations once and change the Specification's
known and unknown roles. Distinguish required rent from controllable rent, financial
value from funding feasibility, and an underdetermined problem from an infeasible
or unsupported one. Explain why the simplified SFFA snapshot and dated DCF need
not produce identical results.

**Rangekeeper depth.** Introduce passive equations, explicit lock/unlock choices,
immutable Specifications and reported execution outcomes. Keep initial rates and
coefficients fixed so the proposed inverse problems remain affine. Continuous
solving does not choose a discrete design or invert arbitrary Python builders.

**Teaching material.** Show a construction timeline, the same relation diagram
with different variables marked known or unknown, a forward/inverse comparison,
and a funding balance including committed costs still to be paid. Establish the
wait/do-nothing baseline explicitly; do not assume an existing parking business.

### 04 One plan, many market futures

Keep the development plan fixed while external conditions change.

**Worked problems.** Compare reference, stronger and weaker conditions. Build one
market path, then related markets for the project's uses, and finally an ensemble
of paths. Recalculate the same plan across those futures.

**Objectives.** Distinguish sensitivity cases from stochastic histories. Separate
assumptions, observations and modelling errors. Explain correlated use markets and
the difference between expected assumptions and a distribution of project outcomes.
Avoid applying the same market growth twice.

**Rangekeeper depth.** Introduce explicit scenario identity, sampling assumptions,
repeatable generation, saved paths and comparable evaluations. Keep seeds and
provenance with the scenario set used later.

**Teaching material.** Combine legacy `deterministic_scenarios` and
`market_dynamics`. Place each driver beside its chart before showing the combined
effect. Show aligned market and cash-flow charts, a small scenario table and an
NPV cumulative distribution. Include funding shortfall alongside value. Put detailed
cycle, noise and shock models in optional sections.

### 05 When to commit

Allow timing decisions to respond to observed conditions. Start with a few readable
histories: early recovery, prolonged downturn, and a brief recovery followed by
deterioration. These precede the larger simulation.

**Worked problems.** Compare the fixed base plan, delayed initial commitment, and
phasing that retains a choice over the next commitment. Apply the alternatives to
the same market histories.

**Objectives.** Use only information available at the decision date. Distinguish
calendar time, construction progress and time since commitment. Track irreversible
commitments, costs to complete, deferred income and costs of waiting. Check physical,
service and funding feasibility before an action can be selected.

**Rangekeeper depth.** Introduce observations, state-dependent actions, decision
rules and traces. The shared basement and services make the dependencies concrete.
Identify and cost any added capacity or separate servicing needed to permit phasing.

**Teaching material.** Carry forward the responsive-model progression from legacy
`flexibility_intro`, using construction decisions as the main case. Align a timeline
of observations, decisions and construction with a funding chart. Provide a short
trace of what was observed, what was feasible, what was chosen, and why. Follow with
paired comparisons on the saved market histories.

**Dependency.** The full sequential behaviour needs the capability work below.

### 06 Which choices are worth preserving?

Introduce a paid design provision that preserves a later choice. The intended
case is a bounded alternative use for Building B, alongside its residential base
use. The alternative and its physical requirements remain to be specified.

**Worked problems.** Compare the fixed base design, timing flexibility, a design
prepared for later use choice, and combined timing/use flexibility. Include the
upfront provision cost even on histories where the choice is never exercised.
Return to inverse reasoning: what maximum premium is justified under the stated
evaluation criterion?

**Objectives.** Separate option availability, decision rule, rule parameters and
realised action. Account for geometry, services, capacity, programme and costs;
changing a rent label is not a use conversion. Compare delivered projects as well
as financial results. Explore whether conclusions survive changed assumptions.

**Rangekeeper depth.** Introduce explicit design variants and their realised
structures, complete strategy definitions and paired evaluations. Keep finite
alternative evaluation distinct from global optimisation. A premium calculation
must state whether the policy is fixed or changes with the premium; it is not
automatically one affine inverse solve.

**Teaching material.** Adapt legacy `flexibility_under_uncertainty`: paired NPV
differences, outcome distributions, funding exposure, completion dates and use
mixes. Explain selected realised histories beside the summary charts. A small
extension can select thresholds on one scenario set and test on a separate set.
Call a winner the best strategy tested unless global optimality is established.

**Dependency.** Structural changes and sequential decisions need capability work.

## Teaching and presentation conventions

Use a repeated sequence: pose a project question, ask for a prediction, explain the
relationship, show a short calculation, inspect the result, change one assumption,
then explain what changed.

- Put short explanations before code and interpretation after outputs. Prefer
  several focused cells to a large opaque builder or incremental class mutation.
- Use explicit keyword arguments where they help readers understand a call.
  Reuse accepted Flux/Stream terminology and native Polars table display.
- Show one object's calculation before a bulk operation. Shared helpers may load
  data or remove repetitive setup; keep the relations and rules being taught visible.
- Use tables for exact values, charts for behaviour and diagrams for relationships.
  Keep names, colours and units consistent across the series.
- Use interaction for selection, inspection or comparison. Preserve a useful saved
  default view in the local book, without requiring a live kernel or service login.
- Redraw legacy concept diagrams where current model semantics differ. Do not
  mistake illustrative diagrams for the exact project graph.
- Retain suitable reference figures and attribution. Use the existing reference
  table and model-progression imagery where they support the lesson.
- Tie checks to claims: shared costs counted once, inverse values reproducing a
  target, decisions respecting observation dates, and commitments fitting funding.
- Keep substantial derivations, stochastic detail and policy searches in optional
  sections. IRR can be supplementary; report failures rather than inventing returns.

## Shared data and source references

Prepare one pinned, complete export of the actual legacy property, including the
geometry and measure attributes needed by the lessons. The
[saved property graph](../../examples/walkthrough/_static/property.html) helps
inspect relationships but does not replace the full source model. Do not silently
substitute the existing small synthetic design fixture for this project.

Keep a source manifest, explicit teaching assumptions and saved market scenarios
with the example. Each notebook must run from a fresh kernel without executing an
earlier notebook. Common definitions should be reused without hiding the lesson's
mathematics or introducing a second authoritative model.

| Source | Use in this curriculum |
| --- | --- |
| [Legacy walkthroughs at main checkpoint 6732e83](https://github.com/daniel-fink/rangekeeper/tree/6732e83d277c8de81f3dec2906e06d0e75d3b6fa/walkthrough) | Narrative sequence, reference figures, small calculations, graph views, area charts, market paths and paired comparisons |
| [Legacy property notebook at the same checkpoint](https://github.com/daniel-fink/rangekeeper/blob/6732e83d277c8de81f3dec2906e06d0e75d3b6fa/walkthrough/drive_model_from_design.ipynb) | Project objects, source identifiers, geometry-derived quantities and financial interpretation |
| [Flexibility and Real Estate Valuation under Uncertainty](../../examples/walkthrough/resources/deNeufvilleGeltnerValuationUnderUncertainty.pdf), Garden City material in chapters 16 onward | Base plan/base case, market uncertainty, delay, use choice and phasing framework |
| User-supplied `ch16.xlsx`, `ch17.xlsx`, `ch18.xlsx`, `ch20ta.xlsx`, `ch20to.xlsx`, `ch21.xlsx`, `ch22.xlsx`, `ch23.xlsx` and companion slides | Traceable worked assumptions and comparison of fixed and flexible strategies; record precise sheet/cell and slide references during lesson preparation |
| Geltner et al., supplied `Commercial Real Estate_Geltner.pdf`, Exhibits 28-4 and 28-5, printed pages 771–773 | SFFA front-door and back-door questions for notebook 03 |
| [Historical two-pad proposal](../history/PROJECT_DEFINITION_AND_POLICY_EXAMPLE.md) | Paid provisions, feasible actions, committed funding, readable histories, decision traces and limits on optimisation claims |

Preserve intent rather than inherited defects. Reconcile capital costs on
service-only objects and aggregation conventions before accepting financial totals.
Legacy output values are not automatically golden results for the new model.

## Capability boundaries

The current executor supports relevant affine scalar and finite-flow equations.
It rejects nonlinear unknown products/divisors, ordered optimisation objectives and
structural interventions. A Specification's change of known/unknown roles must
still leave the selected problem within the supported mathematics.

Current policy support includes finite exogenous evaluation before compilation.
Endogenous sequential policies and multistage optimisation are rejected. Thus the
full behaviour planned for notebooks 05–06 needs a separate implementation design
and acceptance effort. Do not conceal it behind notebook helpers or present an
illustrative Python loop as an accepted canonical execution capability.

Define that work against concrete lesson cases: dated observations; feasible
actions and dependencies; state and commitment updates; future funding obligations;
bounded design alternatives; traceable resulting structures; and replayable outcomes.
Keep simulation, inverse solving, and policy search distinct. Review the current
references again before implementation because these limits can change.

## Preparation decisions still open

| Decision | Required before |
| --- | --- |
| Base dates, construction and opening sequence, quantities and cost assumptions | Authoring notebook 03 |
| Starting site condition, interim use, wait baseline, funding and valuation conventions | Authoring notebook 03 |
| Selected market drivers, correlations, calibration and shared scenario set | Authoring notebook 04 |
| Feasible phase boundaries, shared infrastructure requirements and commitment rules | Authoring notebook 05 |
| Building B alternative use, required provisions, premium and conversion constraints | Authoring notebook 06 |
| Sequential and structural execution contracts and their independent acceptance | Claiming library support in notebooks 05–06 |

These are preparation tasks, not changes to the agreed six-lesson progression.
Record each resolved assumption beside its source and propagate it consistently.

## Delivery and acceptance

1. Prepare the project brief, source manifest and complete pinned model. Confirm
   identities, containment, use mix, geometry-derived measures and shared services.
2. Develop notebook 02's detailed cell outline and transparent calculations. Keep
   notebook 01 accepted and available during later work.
3. Implement and verify any required library changes before relying on them in a
   chapter. Develop the later capability work separately from notebook prose.
4. Author each chapter, execute it from a fresh kernel and inspect saved outputs.
   Check the financial claims, graph contributions and relevant failure cases.
5. Build and inspect the local book using the
   [walkthrough procedure](../guides/walkthroughs.md). Review prose, citations,
   images, native tables, graph/Plotly assets and navigation. Chapter 01's acceptance
   does not establish later interactive-asset acceptance.
6. Add each chapter to [myst.yml](../../examples/walkthrough/myst.yml) only after its
   code, teaching content and rendered output are accepted. Record evidence and
   update this plan's status. Preserve useful legacy sources until replacement is
   verified.

| Deliverable | Recorded status |
| --- | --- |
| Six-lesson curriculum and source roles | Agreed; recorded in this plan |
| Notebook 01 and local introduction | Accepted; evidence linked above |
| Notebook 02 detailed outline and visual requirements | Agreed; recorded in the linked chapter outline |
| Project brief and complete pinned source model | Prepared and locally verified on 2026-10-12; source and geometry-summary checks recorded |
| Notebook 02 | Authored, executed and locally reviewed; evidence linked above |
| Notebooks 03–04 | Planned; detailed outlines, authoring and acceptance pending |
| Sequential and structural capability work | Design and acceptance pending |
| Notebooks 05–06 | Planned; dependent on capability work |
| Complete local book | Pending chapter-by-chapter acceptance |
| Public publication | Outside this delivery scope |
