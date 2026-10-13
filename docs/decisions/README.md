# Decisions and implementation records

Use the [current guides](../README.md) for instructions. These records explain why
contracts and ownership boundaries exist. An implemented decision can remain
current after its execution plan moves to history.

| Decision | Status | Scope |
| --- | --- | --- |
| [ADR-001: document roots](001-document-roots.md) | Implemented | Model, Specification and finalized Run responsibilities |
| [ADR-002: records and identity](002-records-and-identity.md) | Implemented | Schema authority, immutable content and exact revision references |
| [ADR-003: computation and evidence](003-computation-and-evidence.md) | Implemented | Known-data calculations, passive formulations, source evidence and independent acceptance |
| [ADR-004: package and project ownership](004-package-and-project-ownership.md) | Implemented | Domain packages, `src/grasshopper`, examples, tools, docs and local verification |
| [ADR-005: Flux and Stream implementation](005-flux-and-stream-implementation.md) | Implemented; locally verified | Discoverable mathematical parameter names, Stream DX, `model.flux`, Span methods, Polars calculations, acausal formulations, hierarchy, Specification roles and acceptance |
| [ADR-006: Walkthrough curriculum](006-walkthrough-curriculum.md) | Notebooks 01–03 locally accepted; later lessons planned | Six lessons combining the legacy property graph, SFFA inverse solving, Garden City uncertainty/flexibility and two-pad decision lessons |
| [ADR-007: Three repository refactor](007-three-repository-refactor.md) | Implemented; local validation recorded | RK modelling and local display; MCP ingestion; Viewer advanced browsing; zero compatibility APIs and predecessor runtimes |

The first three records summarize decisions already supported by the linked
implementation history. They do not invent an earlier approval date. ADR-004 also
records the source-project placement selected during this documentation pass.
Relationships are explicit links; a decision can affect several owners.

ADR-006 includes the [notebook 02 outline and visual requirements](006-notebook-02-outline.md).
Its [project brief and pinned source package](../guides/mixed-use-project.md) are
prepared. Notebook 02 is authored, executed and locally reviewed, including its
geometry viewer, interactive graphs and themed Plotly charts. The
[notebook 03 outline](006-notebook-03-outline.md) is also implemented and locally
verified: a dated development plan, SFFA role changes and construction funding
checks. Notebooks 04–06 still need authoring and acceptance.

## Implementation history

- [RF-001–RF-023](../history/plans/REFACTORING_PLAN.md): coordinated domain refactor,
  implemented at `5a111b0` with its recorded local acceptance and scope limits.
- [RF-024–RF-034](../history/plans/REFACTORING_FOLLOWUP_PLAN.md): ownership and
  consolidation, implemented at `08aac85` with its recorded local acceptance.
- [Documentation and repository organization](../history/plans/DOCUMENTATION_PLAN.md):
  current pass, including the accepted Grasshopper location and verification record.

## Work that remains explicit

- The [first walkthrough migration](../research/basic-dcf-2026-10-08/README.md) follows the completed [Flux and Stream codebase acceptance](../research/flux-stream-2026-10-08/README.md). The [agreed curriculum](006-walkthrough-curriculum.md) consolidates the other six source notebooks into five further lessons. It owns the teaching sequence, preparation decisions and capability dependencies. Notebooks 01–03 have local acceptance; notebooks 04–06 still need execution and rendered acceptance.
- [ADR-007](007-three-repository-refactor.md) records the implemented three-repository
  split and the paused sessions' restart points. It replaces Windows-dependent
  predecessor retention with a clean break. See the [validation record](../research/three-repository-refactor-2026-10-13/README.md)
  and [retirement status](../contributing/legacy-retirement.md).
  [Windows/Rhino/connector acceptance](../contributing/windows-acceptance.md) remains
  open for the active canonical connector; removal does not establish platform support.
- [Verification](../contributing/verification.md) is run explicitly by developers
  and agents. The GitHub workflows are removed; platform and service acceptance
  still require their own recorded results.
- Building a walkthrough does not publish it. Follow the
  [walkthrough procedure](../guides/walkthroughs.md) for the local build boundary.

Apply the [documentation lifecycle](../contributing/documentation.md) when a plan
is implemented or superseded. Transfer unfinished work, retain identifiers and
rationale, and update both navigation and successor links in the same change.
