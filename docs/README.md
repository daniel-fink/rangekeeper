# Rangekeeper documentation

Start with the task below. Current instructions describe this checkout's pre-1.0
API. Historical records retain the contracts and results from their recorded date.

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
| Execute the notebooks or build their site | [Walkthroughs](guides/walkthroughs.md) |
| Inspect the continuing walkthrough project and its source package | [Mixed-use project brief](guides/mixed-use-project.md) |
| Build the native components and check a Rhino model | [Grasshopper](guides/grasshopper.md) |
| Migrate an earlier consumer or document | [Upgrading](guides/upgrading.md) |

## Look up a contract

| Area | Reference |
| --- | --- |
| Common record rules | [Records](reference/records.md), [identity and revisions](reference/identity.md) |
| Immutable Model and investigation delivery | [Bundle candidate](reference/bundle.md) |
| Document roots | [Model](reference/model.md), [Specification](reference/specification.md), [Run and storage](reference/run-and-storage.md) |
| Mathematics | [Expressions](reference/expressions.md), [calculations](reference/calculations.md), [execution](reference/execution.md) |
| Futures and choices | [Scenarios and policies](reference/scenarios-and-policies.md) |
| Structure and projection | [System views and reductions](reference/system.md), [tables](reference/tables.md) |
| Design transport | [Canonical envelope](reference/design-transport.md) |

## Repository and walkthrough status

Use the single RK working folder and the
[contributor branch procedure](contributing/README.md#working-folder-and-branches).
Reviewed library and documentation work is on `develop`. The
[17 October delivery](https://github.com/daniel-fink/rangekeeper/commit/ae51f11485fbc3ae3061406cbcba94b03aab4430)
includes the standalone documentation cleanup and schema presentation. The
unfinished walkthrough remains on `codex/walkthrough-acausal`; publication is
separate.

The [single-folder consolidation record](history/handoffs/2026-10-14-single-folder-consolidation.md)
records preservation and verification. The earlier
[branch-split record](history/handoffs/2026-10-14-repository-and-walkthrough.md)
retains the former worktree layout as history, not the current working procedure.

## Contribute a change

Start with [development and conventions](contributing/README.md). Agents and
developers apply [documentation upkeep](contributing/documentation.md) in the
same change, including plan status, archiving and navigation.

- [Verification](contributing/verification.md): test, build and evidence boundaries.
- [Releasing](contributing/releasing.md): release lines, tags, the release workflow and its setup.
- [Schema development](contributing/schema.md): generation, typing and conformance.
- [Windows acceptance](contributing/windows-acceptance.md): the open Rhino/connector gate.
- [Legacy retirement](contributing/legacy-retirement.md): held source and removal requirements.

## Inspect a decision or historical result

Use the [decision index](decisions/README.md) for accepted choices, their rationale,
implementation records and remaining work. The
[decisions accepted for 1.0](decisions/README.md#accepted-for-10) define the target
architecture and release plan. The active
[walkthrough curriculum](decisions/006-walkthrough-curriculum.md) defines the six
lessons and their preparation and capability dependencies. [History](history/README.md) contains
completed plans and dated narratives. [Research](research/README.md) retains
captured experiments and verification evidence. A local result does not establish
remote CI, Windows host or service acceptance.
