# Rangekeeper documentation

Start with the task below. Current instructions describe the API in this checkout.
Historical records retain the contracts and results from their recorded date.

## Understand the framework

- [Schema presentation](schema-presentation.html): interactive diagrams, original
  LinkML explanations, and a searchable reference. See the
  [presentation guide](guides/schema-presentation.md) for use and rebuilding.
- [Model, Specification and Run](concepts/model-specification-run.md): facts and
  equations, investigation choices, and finalized evidence.
- [Architecture](concepts/architecture.md): principles, the accepted 1.0 layers and
  the current package map.
- [Glossary](concepts/glossary.md): one meaning for each Rangekeeper term.
- [Source interpretation](concepts/source-workflows.md): source decisions,
  provenance and reproducible builds.

## Use a capability

| Task | Guide |
| --- | --- |
| Install this checkout and choose extras | [Installation](guides/installation.md) |
| Run an example or inspect a wire fixture | [Examples](guides/examples.md) |
| Execute the lessons, or use the chart, graph, geometry and design-transport helpers | [Walkthroughs](guides/walkthroughs.md), [helpers](../examples/walkthrough/helpers/README.md) |
| Inspect the continuing walkthrough project and its source package | [Mixed-use project brief](guides/mixed-use-project.md) |
| Build the unsupported C# and Grasshopper example | [Grasshopper example](../examples/grasshopper/README.md) |
| Migrate an earlier consumer or document | [Upgrading](guides/upgrading.md) |

## Look up a contract

| Area | Reference |
| --- | --- |
| Common record rules | [Records](reference/records.md), [identity and revisions](reference/identity.md) |
| Immutable Model and investigation delivery | [Bundle](reference/bundle.md) |
| Document roots | [Model](reference/model.md), [Specification](reference/specification.md), [Run and storage](reference/run-and-storage.md) |
| Mathematics | [Expressions](reference/expressions.md), [units](reference/units.md), [calculations](reference/calculations.md), [execution](reference/execution.md) |
| Futures and choices | [Market paths and rules](reference/market-paths-and-rules.md) |
| Structure and projection | [System views and reductions](reference/system.md), [tables](reference/tables.md) |

## Branches

Reviewed library, documentation and walkthrough work is on `develop`; `main` holds
releases. The walkthrough lessons are in `examples/walkthrough`. Converting the
lessons for the docs site does not publish them. See the
[walkthrough procedure](contributing/walkthrough-branch.md).

## Contribute a change

Start with [development and conventions](contributing/README.md). Agents and
developers apply [documentation upkeep](contributing/documentation.md) in the
same change, including plan status, archiving and navigation.

- [Verification](contributing/verification.md): test, build and evidence boundaries.
- [Releasing](contributing/releasing.md): release lines, tags, the release workflow and its setup.
- [Walkthrough branch](contributing/walkthrough-branch.md): draft work, library updates and publication.
- [Schema development](contributing/schema.md): generation, typing and conformance.
- [Legacy retirement](contributing/legacy-retirement.md): held source and removal requirements.

## Inspect a decision or historical result

Use the [decision index](decisions/README.md) for accepted choices, their rationale,
implementation records and remaining work. The
[decisions accepted for 1.0](decisions/README.md#accepted-for-10) define the target
architecture and release plan. The active
[walkthrough plan](decisions/020-walkthrough-plan-v2.md) defines the seven
lessons and their preparation and capability dependencies. [History](history/README.md) contains
completed plans and dated narratives. [Research](research/README.md) retains
captured experiments and verification evidence. A local result does not establish
remote CI, Windows host or service acceptance.
