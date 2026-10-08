# Documentation structure and consolidation plan

Status: implemented; local verification passed on 2026-10-08.
See the [implementation record](#implementation-record-2026-10-08) below.

This is the original planning record, archived on 2026-10-08. The selected native
project location is `src/grasshopper`, as recorded in
[ADR-004](../../decisions/004-package-and-project-ownership.md). The adapter-location
option below records the earlier alternatives; its Python-package exclusions do
not apply to the selected sibling project. Current instructions live in the
[documentation index](../../README.md) and [upkeep procedure](../../contributing/documentation.md).

## Original planning record

Status: proposed content pass. The repository relocation puts maintained guides
under `docs/`, examples under `examples/`, and the C# host project under
`adapters/grasshopper/`. This document proposes the next organization of the
guides. It does not claim that the content consolidation or its checks are complete.

Created: 2026-10-08.

## Purpose and boundaries

Make it easy to find what Rangekeeper means, how to use it, why a decision was
made, and how to change it. Give each contract one maintained owner. Prefer links
to repeated descriptions. Preserve useful explanations, examples and historical
evidence when combining pages.

The current guides retain their filenames at the top of `docs/`. Apply the target
directories below during one coordinated content pass, with all affected links.
This is a documentation change. It does not reopen completed refactoring intents,
alter runtime contracts, or close an external acceptance gate.

Keep the root `README.md`, root `CONTRIBUTING.md` and `examples/README.md` as short
entrypoints to the maintained guides. A notebook's Markdown cells and
`examples/walkthrough/intro.md` remain executable tutorial/book source beside the
notebooks. Schema descriptions remain in their authoritative YAML sources.

Developer programs stay outside the guides: `tools/schema` owns generation and
schema verification, `tools/layout` owns solver installation and strict acceptance,
and `tools/docs/build_book.py` owns the maintained book build. Example programs
belong in `examples`; reusable example builders form the separate
`rangekeeper_examples` package there. Neither example code nor developer programs
become a second source of documentation policy.

## Target navigation

Use the reader's task as the main navigation. Use domain names within the
reference section. Keep the existing history and research directories separate
from instructions for the current checkout.

```text
docs/
  README.md                       start here; tasks and reading order
  concepts/
    model-specification-run.md     purpose and domain boundaries
    architecture.md                package ownership and repository map
    source-workflows.md            source interpretation and reproducibility
  reference/
    records.md                     generated records and local behavior
    identity.md                    references, revisions and comparison rules
    model.md                       Model authoring, lookup and validation
    specification.md               contributions, composition and validation
    run-and-storage.md             finalized evidence, codecs and stores
    expressions.md                 syntax, domains, queries and Constraints
    calculations.md                Flow, calendars, arithmetic and accounts
    scenarios-and-policies.md      captured futures, availability and outcomes
    execution.md                   supported mathematics and acceptance
    system.md                      Model views, membership and reductions
    tables.md                      detached Table, projections, Polars and CSV
    workflow.md                    source configuration, catalog and builds
    evidence.md                    Claims, Evidence and tabular operations
    excel.md                       snapshots, inspection and extraction
    viewer.md                      graph presentation and layout contracts
    design-transport.md            canonical envelope and adapter boundaries
  guides/
    installation.md
    examples.md                    example index, including wire examples
    walkthroughs.md
    source-workflows.md             running and reviewing a source build
    grasshopper.md
    upgrading.md                   old-to-current API and wire changes
  contributing/
    README.md                      development workflow and conventions
    documentation.md               how to add, change and retire a page
    verification.md
    schema.md
    layout-acceptance.md
    windows-acceptance.md
    legacy-retirement.md
  decisions/
    README.md                      status, scope and supersession index
    ...                            enduring decisions and active plans
  history/                         superseded plans and dated narratives
    plans/                         implemented, superseded or withdrawn plans
  research/                        preserved experiments and captured evidence
```

The main index should offer five routes: understand the framework, use a
capability, look up a contract, contribute a change, and inspect a decision or
historical result. It should link directly to the relevant page. Do not add an
index file to every directory unless it improves navigation.

The architecture page owns the package map, dependency direction and repository
map. Root entrypoints and other guides link to that map. The reference pages
describe behavior and its limits; guides provide the steps to use it. A small
code illustration can remain beside its contract, but a complete runnable example
has one maintained source under `examples/`.

## Current-to-target map

Names in the first column are relative to `docs/`. Multiple destinations require
content extraction, not copies of the complete page. Keep existing headings and
anchors where practical; update every maintained caller when an anchor changes.

| Current page or group | Target and treatment |
| --- | --- |
| `README.md` | Keep; replace repeated contracts with task-based navigation. |
| `MODEL_SPECIFICATION_RUN.md` | `concepts/model-specification-run.md`; retain the three roots and their reasons. |
| `LIBRARY_ARCHITECTURE.md` | `concepts/architecture.md`; authoritative package and repository map. |
| `GRAPH_ADAPTER_GUIDE.md`, `ingestion-workflow.md` | Merge current rationale and reproducibility rules into `concepts/source-workflows.md`; place operation/API details in `reference/workflow.md`; retain dated narrative in history. |
| `RECORD_BOUNDARY.md` | `reference/records.md`; generated fields, presence, immutability, replacement and intrinsic methods. |
| `REFERENCES.md` | `reference/identity.md`; exact revision scope, UUID preservation and equality contracts. Migration instructions link to upgrading. |
| `DOMAIN_CORE.md` | Split at existing Model and Specification sections into `reference/model.md` and `reference/specification.md`; link to shared record/identity rules. |
| `RUN_AND_STORAGE.md` | `reference/run-and-storage.md`; retain local versus resolved checks and publication failure semantics. |
| `EXPRESSION_CONTRACT.md` | `reference/expressions.md`; distinguish represented domains from implemented execution. |
| `CALCULATIONS.md` | `reference/calculations.md`; retain account, coordinate, missing-value and timing contracts. |
| `SCENARIOS_AND_POLICIES.md` | `reference/scenarios-and-policies.md`; retain separate declaration, observation, evidence and replay contracts. |
| `SCALAR_EXECUTION.md` | `reference/execution.md`; move the complete example instructions to `guides/examples.md`, linking its source. |
| `GRAPH_MODEL.md` | `reference/system.md`; use current Model terminology and retain explicit hierarchy and coverage rules. |
| `CONSUMER_MIGRATION.md` | Extract current Table/projection/Polars/CSV contracts to `reference/tables.md`; workflow contracts to `reference/workflow.md`; run/export steps to `guides/source-workflows.md`; retired-name mappings to `guides/upgrading.md`. |
| `GRAPH_WORKFLOW_FORMATS.md` | `reference/workflow.md`; capability ownership, configuration versions, implementation identity and publication behavior. Contribution steps can remain a linked section here because they depend on these contracts. |
| `ingestion-evidence.md`, `tabular-operations.md` | Combine current Evidence and transformation contracts in `reference/evidence.md`; remove obsolete APIs from current instructions; preserve dated foundation results in history. |
| `excel-ingestion.md` | `reference/excel.md`; keep unique snapshot, request, identity and diagnostic contracts. Move September validation narrative to history. |
| `VIEWER.md` | `reference/viewer.md`; combine the presentation and layout contracts extracted from `INTEGRATIONS.md`. |
| `INTEGRATIONS.md` | Extract workbench contracts to `reference/workflow.md`, layout to `reference/viewer.md`, transport to `reference/design-transport.md`, and C#/host instructions to `guides/grasshopper.md`. Preserve dated project acceptance as history. |
| `INSTALLATION.md` | `guides/installation.md`; move contributor-only workflow details to `contributing/README.md`. |
| `EXAMPLES.md`, `SCHEMA_EXAMPLES.md` | `guides/examples.md`; one index of runnable examples, tutorial sources and wire fixtures. Link to the single example source instead of duplicating YAML. |
| `WALKTHROUGHS.md` | `guides/walkthroughs.md`; fresh kernels, example modes, resource paths and book build. |
| `WORKFLOW_EXAMPLES.md` | Fold into `guides/source-workflows.md`; link to accommodation and equipment sources under `examples/`. |
| `GRASSHOPPER.md` | `guides/grasshopper.md`; current .NET build, authoring, identity and cross-language instructions. |
| `LEGACY_UPGRADE_GUIDE.md` | `guides/upgrading.md`; retain explicit compatibility breaks and migration order; link to current contracts instead of repeating them. |
| `CONTRIBUTING.md`, `RK_NAMING.md` | Contributor rules and general naming rules go to `contributing/README.md`; scenario-specific names and examples go to `reference/scenarios-and-policies.md`; add `contributing/documentation.md` from the rules below. |
| `VERIFICATION.md` | `contributing/verification.md`; current commands and evidence limits, not accumulated historical counts. |
| `SCHEMA.md` | `contributing/schema.md`; source authority, generation and conformance procedure; link to record and expression references for meaning. |
| `LAYOUT_TOOLCHAIN.md` | `contributing/layout-acceptance.md`; preserve pinned toolchain, installer and strict acceptance procedure. |
| `WINDOWS_DEVELOPMENT.md` | `contributing/windows-acceptance.md`; retain the current gate. Extract superseded Rhino 7/.NET Framework provisioning material to history. |
| `LEGACY_ISOLATION.md`, `LEGACY_PYTHON.md`, `LEGACY_GRASSHOPPER.md`, `LEGACY_TESTS.md` | Consolidate in `contributing/legacy-retirement.md`; one current hold/removal procedure, preserving each unique warning and retained-file rule. |
| `REFACTORING_PLAN.md`, `REFACTORING_FOLLOWUP_PLAN.md` | Classify their remaining work first. Move fully implemented records to `history/plans/` after current contracts and any carried-forward acceptance work have an explicit owner. Preserve RF identifiers, rationale, baselines and acceptance limits; link from the decision index. Keep a plan active if it still owns unresolved work. |
| `DOCUMENTATION_PLAN.md` | Active planning record under `decisions/` during the content pass. After implementation and verification, archive it under `history/plans/` using the contributor lifecycle procedure. |
| `handoffs/2026-10-02-acausal-modelling.md` | `history/handoffs/`; mark its continuation instructions historical. |
| `history/**`, including `graph-coverage.md` | Keep historical scope and status; add navigation from the decision index. Do not present removed Graph APIs as current instructions. |
| `research/**` | Keep captured files unchanged and at their existing paths. Link to evidence from decisions and dated history. |

## Consolidation rules and review findings

**Separate current contracts from old milestones.** The ingestion pages contain
useful API detail beside deferred-work statements, removed Table/Graph/pandas APIs,
and September test results. Extract current contracts before retiring the source
pages. An introductory warning alone does not make contradictory instructions
safe to follow. Preserve the dated results as dated results.

**Separate record, revision and execution rules.** `records.md` owns local
construction and field-presence rules. `identity.md` owns reference scope,
revision identity and exact versus schema-equivalent comparison. `run-and-storage.md`
owns allowed publication changes and stored evidence. `execution.md` owns numerical
acceptance. Cross-reference these rules instead of maintaining several copies.

**Keep source workflows distinct from mathematical investigations.** The workflow
concept page explains why source snapshots, interpretation and builds are
separate. The workflow reference owns `WorkflowSpec`, catalog wiring, invocation
records and workbench publication. Evidence owns cell-to-Claim agreement and
transformations. `Specification` and `Run` keep their mathematical meanings.

**Remove host status from timeless contracts.** The review found stale statements
about unavailable MiniZinc and a stock-native terminal Action loader limitation.
Use current verification procedures and dated acceptance records. Likewise, the
old handoff's uncommitted-state and resume instructions belong to its checkpoint.
Do not convert a local pass into a claim about remote CI or Windows acceptance.

**Check examples against the current API.** The review found a string day-count
argument where `series.integrate` requires a `DayCount` member, and obsolete owner
paths in module tables. Verify snippets after extraction. Distinguish unavailable
structured Function/member contracts from already implemented Flow Value content;
do not carry broad old "rich Values are deferred" claims into the new reference.

**Retain useful scope limits.** An example is not proof of a service integration;
a wire fixture is not a solver result; C# local validation is not complete Python
semantic validation. Keep these distinctions with the relevant operations rather
than repeating broad warnings on every page.

## Decisions and history

Use a decision index with explicit links. Decisions can affect several modules,
so their relationships form a graph rather than a strict tree. A small table is
sufficient; no new documentation framework is needed.

Each enduring decision records:

- Stable identifier, title, date, status and affected owners.
- The concrete problem and the accepted choice.
- Alternatives considered and the reason for the choice.
- Consequences, explicit limits and implementation/reference links.
- `supersedes` and `superseded by` links where applicable.
- Verification evidence or an explicitly open acceptance gate.

Use statuses such as proposed, accepted, implemented and superseded consistently.
Do not infer approval from a prototype or a passing test. The index can group
decisions by domain and show dependencies without rewriting their chronology.

Start with decisions already supported by the repository: the three document
roots; schema-generated immutable records; exact revision references; separation
of source evidence from solver evidence; known-data calculations versus passive
formulations; and the current package hierarchy. Extract their rationale from the
existing records. Do not invent missing historical reasons or create one new
decision file for every implementation helper.

The RF registers retain their original identifiers. Short enduring decisions link
to relevant RF sections. Active plans stay in the current index; implemented,
superseded and withdrawn plans move to `history/plans/` once their current
contracts and remaining work have explicit owners. Enduring decision records
keep a stable location in `decisions/`, including when superseded. This keeps
execution history separate from the reasons for an architectural choice.
Historical logs and archived source remain unchanged.

## How contributors extend the docs

The [routine upkeep and lifecycle procedure](../../contributing/documentation.md#routine-upkeep-for-agents-and-developers)
is authoritative for agents and developers. Apply it during each authorized
change, including plan archiving and navigation updates. During consolidation,
move that procedure into `contributing/documentation.md` and update its incoming
links. Keep one copy of the procedure.

1. Find the page that owns the subject. Extend it when the new behavior belongs
   to that contract. Add a page only for a distinct reader task or responsibility.
2. Use concepts for reasons, reference for contracts, guides for steps, and
   contributing for development procedures. Put a durable architectural choice
   in decisions; put checkpoint narratives and captured results in history and
   research respectively.
3. State prerequisites, inputs, results, errors and side effects where relevant.
   Identify a capability as deferred or limited where the reader would use it.
   Use ASD-STE100 principles, allowing technical terms where they improve clarity.
4. Keep complete runnable examples under `examples/`. Link to those sources from
   guides and use small illustrative snippets in references. Keep test fixtures
   identified as fixtures and preserve their validation purpose.
5. Add the new page to `docs/README.md` and link it from its owner or task guide.
   Use repository-relative links and stable descriptive headings. Check both
   incoming and outgoing links when moving or renaming a page.
6. Change schema descriptions in their YAML source and regenerate affected
   artifacts. Do not hand-edit generated API documentation or record fields.
7. Record verification against a source revision and environment. Current guides
   own repeatable commands; dated records own observed counts and outcomes.
8. When superseding a contract, update its maintained reference, migration guide
   and decision links together. Preserve historical evidence without rewriting
   it to appear current. Archive superseded plans only after linking their
   agreed successors and transferring unfinished work; follow the contributor
   lifecycle rules for implemented, partially replaced and withdrawn plans.

## Execution order and acceptance

1. Record the current doc inventory and preserve unrelated edits. Classify each
   page and each mixed-status section using the map above. Confirm every unique
   contract has a destination before deleting a duplicate page.
2. Consolidate current contracts and extract historical sections. Correct stale
   instructions against the source. Keep behavior unchanged; report any newly
   discovered runtime discrepancy separately.
3. Apply the target moves and update maintained links, root entrypoints, example
   links, package metadata and documentation checks that refer to filenames.
   Keep `research/` files and their recorded paths intact.
4. Build the task index, decision index and documentation contribution guide.
   Remove replaced pages after their useful content and incoming links are handled.
5. Check repository links and anchors, current API names, command working
   directories, and the executable examples affected by the edits. Run schema
   checks that extract Markdown examples after changing their source location.
   Build the walkthrough site through `tools/docs/build_book.py` when book links
   or source configuration change. Check the built navigation as well as the
   Markdown sources.
6. Review the result for duplicate authority, orphan pages, unexplained acronyms
   and old "current" or "next" claims. Record completed checks and any external
   limits; then mark this content pass implemented. Archive this plan under
   `history/plans/`, preserve its identifiers and evidence, and update its links.

Acceptance requires every maintained page to have one clear purpose and a route
from the main index. Current commands and examples must use current paths and
contracts. No unique contract, contributor convention or retirement requirement
may be lost. Historical evidence must remain identifiable and unchanged. No new
runtime package, compatibility alias or documentation tool framework is required.

## Adapter location option

The current move places the C# solution at `adapters/grasshopper/`. This keeps a
separate .NET build outside the Python package tree. It is a repository layout
choice, not a domain ownership requirement.

A single adapter location at `src/rangekeeper/adapters/grasshopper/` is also valid.
The move changes repository and build paths. It does not change wire fields,
Python APIs, .NET namespaces, component IDs or project-to-project references.
The C# Model project retains its language boundary at the shared location.

| Area | Concrete change and purpose |
| --- | --- |
| Python package discovery | In `src/pyproject.toml`, exclude `rangekeeper.adapters.grasshopper` and `rangekeeper.adapters.grasshopper.*`. Current setuptools discovery accepts implicit namespace directories, so omitting `__init__.py` does not exclude the C# project. Keep normal discovery for the Python adapters. |
| Python distribution contents | Add an explicit source-distribution exclusion, such as `prune rangekeeper/adapters/grasshopper` in `src/MANIFEST.in`. Build a fresh source archive and wheel, then inspect their contents to confirm that C# sources, the Rhino script and native build outputs are absent. Package discovery alone is not the source-archive policy. |
| Installed-package verification | Update `tools/schema/verify_install.py` to copy the manifest into its isolated build and avoid copying native build caches into the staging tree. Verify a direct project build as well, so staging filters cannot conceal a missing distribution exclusion. |
| Python-only checks | Exclude this exact host-project subtree from the runtime inventory in `tools/schema/typecheck.py` and audit the canonical-source scan in `src/tests/test_legacy_boundary.py`. The relevant Python file is `Tests/accept_rhino.py`, which runs inside Rhino and imports `clr`, `Rhino` and `Grasshopper`; it is not a CPython library module. C# files are already outside the `*.py` selection. Retain the C# and Rhino checks. |
| C# generation | Change `DEST` in `tools/schema/generate_csharp.py` to `src/rangekeeper/adapters/grasshopper/Model/Generated`. Regenerate and check the manifest because it hashes the generator. Schema and record output content should remain unchanged. |
| Builds and host loading | Update repository-root commands and any configured plugin/build paths. The `.sln` and `.csproj` references within the moved tree stay relative to the same sibling projects. Build outputs now occur under the new location. |
| Acceptance paths | Update the host script's path from the C# project root to `examples/grasshopper`, the path used to launch `Tests.dll`, and current docs. Keep the Rhino/GHX examples together at their existing root `examples` location so their relative source reference remains valid. |

Acceptance covers fresh Python distribution contents and imports, typing, C#
generator freshness, the .NET build and Python/C# round trips. A local build does
not close the external Windows/Rhino/connector acceptance gate. This table records
the work required; it does not claim that the second Grasshopper move is complete.


## Implementation record: 2026-10-08

Source: `acausal-modelling` at `08aac85`, plus the uncommitted repository
organization and documentation changes. This record describes local acceptance;
it does not identify a new commit or a published site.

The content pass consolidated 41 former page paths into their maintained owners
or archived records. The main index now gives five routes through 38 current
pages. Current references retain the Model–Specification–Run boundaries, exact
revision rules, source Evidence, independent numerical acceptance and explicit
publication failures. Workflow and calculation examples use current APIs.

The Grasshopper solution is at `src/grasshopper`. Python adapters retain their
existing package. The C# generator, generated manifest, commands and host example
paths use the selected location. No Python packaging or runtime-scan exclusion
is needed for this sibling project. The earlier alternatives above remain as
planning history; [ADR-004](../../decisions/004-package-and-project-ownership.md)
is the accepted ownership decision.

The two completed RF plans and the dated handoff are archived beside this record.
Their open Windows, connector, retirement and remote-check work has current
owners under [contributing](../../contributing/README.md). Superseded source-workflow
and Windows narratives have dated history records. Only navigation links changed
within the 1,271 preserved research files; captured data, logs, source and outputs
retain their bytes.

Three YAML fragments moved from prose into `examples/schema/` without content
changes. Conformance now reads those files directly. Example builders remain the
separate local `rangekeeper_examples` package. Root entrypoints, package metadata,
example guides, schema checks and maintained links use the final paths.

[Documentation upkeep](../../contributing/documentation.md) now owns the agent/dev
procedure, plan lifecycle and evidence rules. `tools/docs/check.py` checks local
links, anchors and current-page reachability without an added dependency.
`tools/docs/build_book.py` retains bibliography extensions while removing unused
Thebe support. The bibliography now encodes a DOI as an identifier and removes a
publisher PDF URL that the renderer incorrectly treated as an arXiv identifier.

### Local acceptance

Runtime checks used Python 3.10.19. Schema tools used the pinned requirements in a
Python 3.12.12 environment. The native solution built for .NET 8; its console
round trip ran with a .NET 8 runtime. The commands and prerequisites are maintained
in [verification](../../contributing/verification.md),
[schema](../../contributing/schema.md), [Grasshopper](../../guides/grasshopper.md)
and [walkthroughs](../../guides/walkthroughs.md).

| Check | Observed result |
| --- | --- |
| `python tools/docs/check.py` | 64 current/history/navigation pages checked; all 38 current pages reachable; no missing local file or Markdown anchor. Negative probes rejected missing files, missing anchors and orphan pages. |
| Python and C# generator `--check` | Both pass; Python verifies six artifacts and 72 schema classes. |
| Schema conformance | All seven suites pass: structural validation, native round trip, expressions, formulations, Models, Specifications and Runs. The three extracted YAML fragments match their original blocks exactly. |
| `python tools/schema/typecheck.py` | 209 valid sources pass; all 38 intended static errors are detected. |
| Native solution build and Python → C# → Python | Build passes with zero warnings/errors; content, presence, identity and ordered mathematics round-trip. |
| Direct clean Python distributions | Wheel contains 245 files; source archive contains 347 entries. Neither includes native solution files or example code. Required schema assets remain present. |
| Installed candidate wheel | Minimal imports, records, codecs, stores, graph/table/viewer assets, process-isolated forward/inverse execution and XLSX workflow checks pass outside the checkout. |
| Extracted documentation examples | Six core reference snippet groups, the equipment workflow and both ingestion examples pass. Seven workflow Python snippets parse. |
| Walkthrough build and navigation | Build passes without warnings. All seven chapters are linked; 721 local links and 242 HTML fragment links pass. Bibliography entries, citation targets and the normalized DOI are present. |
| Research preservation and diff | All 1,271 research files checked; only 20 Markdown navigation files changed, with recorded bodies unchanged. `git diff --check` passes. |

The first direct wheel check exposed removed modules in an old `src/build` cache.
The cache and failed artifact were preserved in the temporary acceptance folder.
A clean direct rebuild passed. The current packaging instructions explain that
cache boundary. No runtime compatibility alias or package exclusion was added.

The book uses the seven fresh-kernel outputs from the immediately preceding
repository relocation pass: 91 executed cells. Their input cells were compared
with the current notebooks and match exactly. The notebooks were not executed
again for these prose and bibliography changes. Their tracked historical build
outputs were preserved; the new site is a separate local build.

Temporary logs, artifact inventories and the accepted book are under
`/private/tmp/rk-docs-implementation-20261008/`; they are local diagnostic outputs,
not a published or permanent evidence store. The complete Python test suite was
not rerun during the content pass. No remote CI, new Rhino host session, Windows
connector publication/receive check or site publication was performed. Follow
[Windows acceptance](../../contributing/windows-acceptance.md) and
[legacy retirement](../../contributing/legacy-retirement.md) before closing their
held gates. Changes remain uncommitted at this checkpoint.
