# Rangekeeper documentation

Rangekeeper separates project facts and equations (`Model`), investigation choices
(`Specification`), and finalized execution evidence (`Run`). The package uses
immutable records, exact revision references and explicit execution boundaries.

## Package ownership and imports

`Model`, `Specification` and `Run` remain available from the package root. Import
other capabilities from their owner:

| Package | Responsibility and common imports |
| --- | --- |
| `rangekeeper.schema` | Generated records and enums, structural validation, record runtime and revision indexes; `Metadata` |
| `rangekeeper.shared` | Explicit leaf modules for `table.Table`/`Row`, `units`, `references`, `diagnostics`, `errors` and validation mechanics |
| `rangekeeper.model` | Model declarations and validation; `system.View`/`Hierarchy`, `duration` calendars, `scenario` capture/replay, `expression` analysis and `formulation` builders |
| `rangekeeper.specification` | Investigation requirements and composition; `policy` declarations, observation and causal evaluation |
| `rangekeeper.run` | Finalized reports and validation; `execution.Executor` for solving and independent acceptance |
| `rangekeeper.calculations` | Known-data calculations, account conventions and deterministic `dynamics` functions |
| `rangekeeper.workflow` | Source configuration, Evidence operations, Model composition and builds; lightweight `evidence` and `operation` contracts |
| `rangekeeper.adapters` | File, service and presentation boundaries |
| `rangekeeper.io` | Explicit JSON/YAML codecs and append-only revision stores |

```python
from rangekeeper import Model, Specification, Run
from rangekeeper.schema import Metadata
from rangekeeper.shared.table import Table, Row
from rangekeeper.model.system import View, Hierarchy
from rangekeeper.model.duration import Period, Span, make_periods
from rangekeeper.model.formulation import flow
from rangekeeper.run.execution import Executor
from rangekeeper.workflow.evidence import Evidence, Claim
```

`Table` and `Row` retain their names and contracts. The former root utility,
`graph`, `duration`, `formulations`, `scenarios`, `policies`, `execution` and
`evidence` paths have no compatibility aliases. Workflow configuration is separate
from a mathematical `Specification`. Importing record or source contracts does not
load the workflow runner or numerical solvers.

## Guides

Start with [architecture](LIBRARY_ARCHITECTURE.md), then use the guide for your task:

| Guide | Purpose |
| --- | --- |
| [Object model](MODEL_SPECIFICATION_RUN.md) | Why the three roots and their ownership boundaries exist |
| [References and identity](REFERENCES.md) | UUIDs, revision scope, Flow copying and draft upgrades |
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

The [refactoring register](REFACTORING_PLAN.md) and
[follow-up register](REFACTORING_FOLLOWUP_PLAN.md) record the implementation intents
and their verification requirements. These maintained guides describe the current
package structure.

Dated plans are in [history](history/README.md). Captured results are in
[research](research/README.md); neither overrides the current guides.
