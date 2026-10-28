# Decisions and implementation records

Use the [current guides](../README.md) for instructions. These records explain why
contracts and ownership boundaries exist. An implemented decision can remain
current after its execution plan moves to history.

Write a new record from the [decision template](template.md). The template defines
the sections and the Status line; the Status column below uses the same words.

| Decision | Status | Scope |
| --- | --- | --- |
| [ADR-001: document roots](001-document-roots.md) | Implemented | Model, Specification and finalized Run responsibilities |
| [ADR-002: records and identity](002-records-and-identity.md) | Implemented | Schema authority, immutable content and exact revision references |
| [ADR-003: computation and evidence](003-computation-and-evidence.md) | Implemented | Known-data calculations, passive formulations, source evidence and independent acceptance |
| [ADR-004: package and project ownership](004-package-and-project-ownership.md) | Implemented | Domain packages, `src/grasshopper`, examples, tools, docs and local verification |
| [ADR-005: Flux and Stream implementation](005-flux-and-stream-implementation.md) | Implemented | Stream as the flow interface, `model.flux`, Polars calculations, role-named equation builders and the two collection routes; the [implementation plan](../history/plans/005-flux-and-stream-implementation.md) is archived |
| [ADR-006: Walkthrough curriculum](006-walkthrough-curriculum.md) | Superseded by ADR-020 | Six lessons combining the legacy property graph, SFFA inverse solving, Garden City uncertainty/flexibility and two-pad decision lessons |
| [ADR-007: Library boundary and API retirement](007-library-boundary-and-api-retirement.md) | Implemented; external host acceptance remains separate | Public API moves, native authoring, walkthrough preservation and runtime retirement |
| [ADR-008: Rangekeeper Bundle contract](008-rangekeeper-bundle-contract.md) | Accepted; candidate implemented, full conformance open; amended by ADR-017 | Main Model plus selected Models/Specifications/finalized Runs and exact dependencies; Model-owned Geometry; Parquet IO; standalone canonical IO; earlier SQLite proof retained |
| [ADR-009: Classification filters include sub-types](009-classification-sub-types.md) | Implemented | `View.filter` and the `classified` contributor rule match a Classification and its descendants; `exclusive=True` matches exactly |

## Accepted for 1.0

ADR-010 to ADR-020 were accepted on 2026-10-26, and ADR-023 on 2026-10-27.
1.0.0a2 implements ADR-010, ADR-011, ADR-012 and ADR-023, and parts of ADR-013
and ADR-016 to ADR-018; the Status column shows what is pending. The
[Rangekeeper project](https://github.com/users/daniel-fink/projects/8) tracks the
implementation as epics with sub-issues, milestones 0.8.72 to 1.0.0 and
blocked-by links. The
[architecture](../concepts/architecture.md) shows the target, and the
[glossary](../concepts/glossary.md) defines its terms.

| Decision | Status | Scope |
| --- | --- | --- |
| [ADR-010: Layers, packages and public namespaces](010-layers-and-packages.md) | Accepted for 1.0; library boundary and layers implemented | Library boundary, layer order, ownership rules, public namespaces and the move map |
| [ADR-011: Records, behaviour and validation](011-records-and-validation.md) | Accepted for 1.0; implemented in 1.0.0a2 | Data-only generated records, owner subclasses, document facades, generated runtime and validation tiers |
| [ADR-012: Naming convention, glossary and rename pass](012-naming-and-glossary.md) | Accepted for 1.0; rename pass implemented in 1.0.0a2 | Naming rules, agreed renames, initial rename map and the single 1.0.0a2 codemod pass |
| [ADR-013: Execution pipeline and extension points](013-execution-and-extensions.md) | Accepted for 1.0; extension points implemented, pipeline pending | Pure `solve`, `execute`, `Outcome`, backend contract, worker, registry pattern and fingerprints |
| [ADR-014: Market paths and path generators](014-market-paths.md) | Accepted for 1.0; package move done in 1.0.0a2, implementation pending | Path generators, the MarketPaths document and `Specification.across` |
| [ADR-015: Authoring with builders, equations and identities](015-authoring.md) | Accepted for 1.0; implementation pending | Document builders, operator and string equations, deterministic builds and quantity parsing |
| [ADR-016: Safety defaults](016-safety-defaults.md) | Accepted for 1.0; units, diagnostics and errors implemented, dimensional checks and the underdetermined outcome pending | Curated units, dimensional checks, the underdetermined outcome, structured diagnostics and errors |
| [ADR-017: Public API, stability and data formats](017-api-and-formats.md) | Accepted for 1.0; format reset and money implemented, freeze pending | Semantic versioning, the 1.0.0 format reset, format changes before the freeze, Bundle format 1 and money |
| [ADR-018: Release lines, versioning and engineering practice](018-release-and-engineering.md) | Accepted for 1.0; implemented except docs site publication | `support/0.8`, pre-releases, versions, changelog, Python support, tooling, CI, tests and the docs site |
| [ADR-019: Walkthrough direction for 1.0](019-walkthrough-direction.md) | Accepted for 1.0; walkthrough plan v2 is ADR-020 | All lessons for 1.0, proposed cells first, helpers, CI execution and sources |
| [ADR-020: Walkthrough plan v2](020-walkthrough-plan-v2.md) | Accepted for 1.0; proposed cells recorded; authoring pending | Seven lessons by principle, reader types, book outcomes, developer-experience principles, teaching conventions and source rights; supersedes ADR-006 |
| [ADR-023: Decimal currency amounts](023-decimal-money.md) | Accepted for 1.0; implemented in 1.0.0a2 | Currency amounts as Decimal, float64 calculation boundaries, JSON, YAML and Parquet encodings, solver evidence and tolerances, and minor-unit rounding; the design of ADR-017's Money section |

The first three records summarize decisions already supported by the linked
implementation history. They do not invent an earlier approval date. ADR-004 also
records the source-project placement selected during this documentation pass.
Relationships are explicit links; a decision can affect several owners.

[ADR-020](020-walkthrough-plan-v2.md) defines the seven lessons for 1.0. The
[project brief and pinned source package](../guides/mixed-use-project.md) stay
current. ADR-006's [notebook 02 outline](../history/plans/006-notebook-02-outline.md)
and [notebook 03 outline](../history/plans/006-notebook-03-outline.md) are archived
as source material. Notebooks 02 and 03 were authored and locally reviewed on the
interim API; all lessons are rebuilt for 1.x.

## Executor designs for lessons 05 and 07

These records design the executor features that walkthrough lessons 05 and 07
need ([ADR-019](019-walkthrough-direction.md)). ADR-021 and ADR-022 were accepted on
2026-10-27, and ADR-024 on 2026-10-28.
#215 and #216 implement them.

| Decision | Status | Scope |
| --- | --- | --- |
| [ADR-021: Decide values by rules over market paths](021-sequential-decisions.md) | Accepted for 1.0; implementation pending | Rules that decide one value, observations and availability, evaluation order, staged solves for each path, decision traces, replay and paired comparison; amends ADR-013 and ADR-014 |
| [ADR-022: Choose between design alternatives with rules](022-design-alternatives.md) | Accepted for 1.0; implementation pending | Alternatives as Model revisions, choice keys, realised structure for each path, strategy comparison and the premium question; amends ADR-001 |
| [ADR-024: Search as a query over a range of cases](024-search-as-query.md) | Accepted for 1.0; implementation pending | A range of one value as a source of cases, deferred Outcomes, the by-case table as a query, the exact and bracketed plan, and no range over a rule's inputs; amends ADR-021 and ADR-022 |

## Implementation history

- [ADR-005 implementation plan](../history/plans/005-flux-and-stream-implementation.md):
  Flux and Stream design detail and acceptance criteria, implemented on 2026-10-08.
- [RF-001–RF-023](../history/plans/REFACTORING_PLAN.md): coordinated domain refactor,
  implemented at `5a111b0` with its recorded local acceptance and scope limits.
- [RF-024–RF-034](../history/plans/REFACTORING_FOLLOWUP_PLAN.md): ownership and
  consolidation, implemented at `08aac85` with its recorded local acceptance.
- [Documentation and repository organization](../history/plans/DOCUMENTATION_PLAN.md):
  current pass, including the accepted Grasshopper location and verification record.

## Work that remains explicit

- The [first walkthrough migration](../research/basic-dcf-2026-10-08/README.md) follows the completed [Flux and Stream codebase acceptance](../research/flux-stream-2026-10-08/README.md). [Walkthrough plan v2](020-walkthrough-plan-v2.md) replaces the earlier curriculum with seven lessons. It owns the teaching sequence, preparation decisions and capability dependencies. All lessons need proposed cells, authoring and CI execution on the 1.x API.
- The [Windows/Rhino/connector gate](../history/windows-acceptance.md) is retired:
  the envelope is a walkthrough helper and the Grasshopper solution is an
  unsupported example ([ADR-010](010-layers-and-packages.md)). The [retirement guide](../contributing/legacy-retirement.md) records removed
  APIs; their removal does not establish platform support.
- [Verification](../contributing/verification.md) is run explicitly by developers
  and agents. The [Tests workflow](../contributing/README.md#continuous-integration)
  runs only the Python test suite on pull requests; platform and service acceptance
  still require their own recorded results.
- Building a walkthrough does not publish it. Follow the
  [walkthrough procedure](../guides/walkthroughs.md) for the local build boundary.

Apply the [documentation lifecycle](../contributing/documentation.md) when a plan
is implemented or superseded. Transfer unfinished work, retain identifiers and
rationale, and update both navigation and successor links in the same change.

Bundle conformance, walkthrough authoring and native-host acceptance are separate
tracks. Public reader or schema changes require a verified distribution before
consumers adopt them. A development merge does not publish a package or site.
