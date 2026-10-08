# Rangekeeper documentation

Start with the task below. Current instructions describe this checkout's pre-1.0
API. Historical records retain the contracts and results from their recorded date.

## Understand the framework

- [Model, Specification and Run](concepts/model-specification-run.md): facts and
  equations, investigation choices, and finalized evidence.
- [Architecture](concepts/architecture.md): package ownership, imports, repository
  structure and dependency boundaries.
- [Source workflows](concepts/source-workflows.md): source interpretation,
  provenance and reproducible builds.

## Use a capability

| Task | Guide |
| --- | --- |
| Install this checkout and choose extras | [Installation](guides/installation.md) |
| Run an example or inspect a wire fixture | [Examples](guides/examples.md) |
| Execute the notebooks or build their site | [Walkthroughs](guides/walkthroughs.md) |
| Build and review a source workflow | [Source workflows](guides/source-workflows.md) |
| Build the native components and check a Rhino model | [Grasshopper](guides/grasshopper.md) |
| Migrate an earlier consumer or document | [Upgrading](guides/upgrading.md) |

## Look up a contract

| Area | Reference |
| --- | --- |
| Common record rules | [Records](reference/records.md), [identity and revisions](reference/identity.md) |
| Document roots | [Model](reference/model.md), [Specification](reference/specification.md), [Run and storage](reference/run-and-storage.md) |
| Mathematics | [Expressions](reference/expressions.md), [calculations](reference/calculations.md), [execution](reference/execution.md) |
| Futures and choices | [Scenarios and policies](reference/scenarios-and-policies.md) |
| Structure and projection | [System views and reductions](reference/system.md), [tables](reference/tables.md) |
| Source interpretation | [Workflow](reference/workflow.md), [evidence](reference/evidence.md), [Excel](reference/excel.md) |
| External presentation and transport | [Viewer and layout](reference/viewer.md), [design transport](reference/design-transport.md) |

## Contribute a change

Start with [development and conventions](contributing/README.md). Agents and
developers apply [documentation upkeep](contributing/documentation.md) in the
same change, including plan status, archiving and navigation.

- [Verification](contributing/verification.md): test, build and evidence boundaries.
- [Schema development](contributing/schema.md): generation, typing and conformance.
- [Layout acceptance](contributing/layout-acceptance.md): pinned engines and strict checks.
- [Windows acceptance](contributing/windows-acceptance.md): the open Rhino/connector gate.
- [Legacy retirement](contributing/legacy-retirement.md): held source and removal requirements.

## Inspect a decision or historical result

Use the [decision index](decisions/README.md) for accepted choices, their rationale,
implementation records and remaining work. [History](history/README.md) contains
completed plans and dated narratives. [Research](research/README.md) retains
captured experiments and verification evidence. A local result does not establish
remote CI, Windows host or service acceptance.
