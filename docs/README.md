# Rangekeeper documentation

Rangekeeper separates project facts and equations (`Model`), investigation choices
(`Specification`), and finalized execution evidence (`Run`). The package uses
immutable records, exact revision references and explicit execution boundaries.

Start with [architecture](LIBRARY_ARCHITECTURE.md), then use the guide for your task:

| Guide | Purpose |
| --- | --- |
| [Object model](MODEL_SPECIFICATION_RUN.md) | Why the three roots and their ownership boundaries exist |
| [Records and methods](RECORD_BOUNDARY.md) | Generated fields, immutable replacement and intrinsic behavior |
| [Domain operations](DOMAIN_CORE.md) | Authoring, lookup, revision, composition and validation |
| [Calculations](CALCULATIONS.md) | Movement, Flow, calendar, unit and missing-value rules |
| [Expressions](EXPRESSION_CONTRACT.md) | Mathematical syntax, references, Functions, queries and constraints |
| [Execution](SCALAR_EXECUTION.md) | Affine feasibility, deadlines, independent acceptance and publication |
| [Scenarios and policies](SCENARIOS_AND_POLICIES.md) | Temporal formulations, captured futures and causal policy replay |
| [Runs and storage](RUN_AND_STORAGE.md) | Finalized reports, strict codecs and immutable revision stores |
| [Graph operations](GRAPH_MODEL.md) | Views, membership, hierarchy and explicit reductions |
| [Tables and consumers](CONSUMER_MIGRATION.md) | Polars, CSV, source workflows and evidence boundaries |
| [Workflow formats](GRAPH_WORKFLOW_FORMATS.md) | Format-independent source execution |
| [Workflow rationale](GRAPH_ADAPTER_GUIDE.md) | Evidence, operations and ownership |
| [Integrations](INTEGRATIONS.md) | Workbench, design transport, C# and host boundaries |
| [Names](RK_NAMING.md) | Domain nouns, operations and naming rules |
| [Upgrade guide](LEGACY_UPGRADE_GUIDE.md) | Deliberate pre-1.0 API changes |
| [Verification](VERIFICATION.md) | Reproducible checks and their limits |

The [schema guide](../schema/README.md) owns schema files and generation commands.
The [Python README](../src/README.md) owns installation and extras.
The [walkthroughs](../walkthrough/README.md) provide executable examples.
The [viewer](../src/rangekeeper/adapters/cytoscape/README.md) and
[strict layout procedure](../tools/layout/README.md) cover offline presentation.

The official Windows connector acceptance gate remains open. The isolated
predecessor trees remain for that gate; see [legacy isolation](LEGACY_ISOLATION.md)
and the [Windows procedure](../grasshopper/WINDOWS_DEVELOPMENT.md).

Dated plans are in [history](history/README.md). Captured results are in
[research](research/README.md); neither overrides the current guides.
