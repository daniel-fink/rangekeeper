# Historical design and migration records

These documents explain earlier decisions and acceptance checkpoints. They are
not installation instructions or a statement of the current API. Test counts,
commit state, proposed APIs and remaining work apply to their recorded dates.

Use the [current documentation](../README.md) for package contracts and commands.
Detailed captured evidence remains in [research](../research/README.md).

Agents and developers must follow the
[plan lifecycle procedure](../contributing/documentation.md#plan-and-decision-lifecycle) when
archiving a record. Put newly archived implementation plans under `plans/`, retain
their identifiers and dated status, and link their successor and current guides.
Keep remaining work visible before moving a plan out of the current index.

## Completed plans and checkpoints

- [Single-folder consolidation](handoffs/2026-10-14-single-folder-consolidation.md): Bundle candidate integration, preserved trees, branch workflow and validation.

- [Repository and walkthrough split](handoffs/2026-10-14-repository-and-walkthrough.md): the 14 October branch, worktree and publication checkpoint.
- [ADR-005 implementation plan](plans/005-flux-and-stream-implementation.md): Flux and Stream design, naming inventory and acceptance.
- [RF-001–RF-023](plans/REFACTORING_PLAN.md): coordinated domain refactoring.
- [RF-024–RF-034](plans/REFACTORING_FOLLOWUP_PLAN.md): ownership and module consolidation.
- [Documentation structure](plans/DOCUMENTATION_PLAN.md): consolidation and native project placement.
- [Notebook 02 outline](plans/006-notebook-02-outline.md) and [notebook 03 outline](plans/006-notebook-03-outline.md): interim chapter plans under ADR-006, superseded by [ADR-020](../decisions/020-walkthrough-plan-v2.md).
- [Integration record](source-workflows/2026-10-08-integration-record.md): recorded integration scope and limits.
- [Windows provisioning](windows-provisioning.md): superseded Rhino 7 setup.

## Earlier design and migration records

- [Domain Migration Plan](DOMAIN_MIGRATION_PLAN.md)
- [Schema Tooling Evaluation](SCHEMA_TOOLING_EVALUATION.md)
- [Redevelopment and policy proposal](PROJECT_DEFINITION_AND_POLICY_EXAMPLE.md)

## Archived records

These records are at tag `archive/pre-1.0-evidence`. No current page depends on
them. They remain unchanged at the tag.

- [Acausal modelling handoff](https://github.com/daniel-fink/rangekeeper/blob/archive/pre-1.0-evidence/docs/history/handoffs/2026-10-02-acausal-modelling.md): the 2 October checkpoint.
- [Source-workflow foundations](https://github.com/daniel-fink/rangekeeper/blob/archive/pre-1.0-evidence/docs/history/source-workflows/2026-09-17-foundations.md): earlier APIs and validation results.
- [Graph coverage](https://github.com/daniel-fink/rangekeeper/blob/archive/pre-1.0-evidence/docs/history/graph-coverage.md): the earlier feature inventory.
- [Domain migration map](https://github.com/daniel-fink/rangekeeper/blob/archive/pre-1.0-evidence/docs/history/DOMAIN_MIGRATION_MAP.md): the Step 1 design for the domain migration.
- [Graph refactor implementation plan](https://github.com/daniel-fink/rangekeeper/blob/archive/pre-1.0-evidence/docs/history/GRAPH_REFACTOR_IMPLEMENTATION_PLAN.md)
- [Graph adapter review](https://github.com/daniel-fink/rangekeeper/blob/archive/pre-1.0-evidence/docs/history/GRAPH_ADAPTER_REVIEW.md)
- [Graph YAML workflow](https://github.com/daniel-fink/rangekeeper/blob/archive/pre-1.0-evidence/docs/history/GRAPH_YAML_WORKFLOW.md)
- [Full migration review](https://github.com/daniel-fink/rangekeeper/blob/archive/pre-1.0-evidence/docs/history/FULL_MIGRATION_REVIEW.md)
- [Full migration turn 1](https://github.com/daniel-fink/rangekeeper/blob/archive/pre-1.0-evidence/docs/history/FULL_MIGRATION_TURN1.md)
- [Full migration turn 2](https://github.com/daniel-fink/rangekeeper/blob/archive/pre-1.0-evidence/docs/history/FULL_MIGRATION_TURN2.md)
- [Full migration turn 3](https://github.com/daniel-fink/rangekeeper/blob/archive/pre-1.0-evidence/docs/history/FULL_MIGRATION_TURN3.md)
- [Full migration turn 4](https://github.com/daniel-fink/rangekeeper/blob/archive/pre-1.0-evidence/docs/history/FULL_MIGRATION_TURN4.md)
