# Three repository refactor

**Status: implemented; local validation and open gates are recorded below.**

**Decision date: 13 October 2026.** Rangekeeper owns modelling and simple local
display. Whirlwind MCP owns ingestion. Whirlwind Viewer owns advanced browsing
and visualisation. The target is zero legacy APIs, runtimes, aliases or automatic
fallbacks in the supported packages.

This plan replaces the earlier proposal to keep a frozen predecessor inside the
new ingestion package. It also replaces the requirement to retain predecessor
code until Windows connector acceptance. Canonical Windows acceptance remains
open and controls the platform support claim. It does not require the excluded
predecessor implementation.

The three feature sessions remain paused while this refactor is planned and
implemented. Their next steps are retained below. This document does not start
those sessions or authorize publication, source interpretation decisions, or
external service writes.

## Owners and dependencies

| Repository | Owns | Boundary |
| --- | --- | --- |
| Rangekeeper | Canonical Model, Specification and Run; schemas; units; validation; calculations; execution; canonical provenance records; native IO; simple local charts, tables, graphs and geometry display; portable C# model library and generic Grasshopper modelling components | No ingestion workspaces, source interpretation engine, Rhino source reader, MCP server, application browser or predecessor runtime |
| Whirlwind MCP | Source acquisition and inspection; interpretation rules and decisions; transient Evidence; recipes; deterministic ingestion builds; workspace lifecycle; Python API; MCP tools and resources; plugin packaging; service access and authorisation; optional Rhino/Grasshopper source integration | Calls public RK APIs. Core ingestion runs without Rhino, Grasshopper, an LLM, MCP transport, Node, Payload or Viewer process |
| Whirlwind Viewer | Shared tree, graph, 3D, inspector and table components; full standalone browser; focused ChatGPT resources; browser host adapters; projections and browsing indexes; advanced graph layouts; buildable static display assets | Consumes exact canonical artifacts. It cannot change source decisions or canonical records through a projection |

Repository roots are:

- Rangekeeper: `/Volumes/Data/Projects/Rangekeeper`
- Whirlwind MCP: `/Volumes/Data/Projects/Whirlwind/whirlwind-mcp`
- Whirlwind Viewer: `/Volumes/Data/Projects/Whirlwind/whirlwind-viewer`

The runtime direction is Whirlwind MCP to RK. Viewer consumes the RK artifact
contract and, when connected, the MCP service contract. RK imports neither
Whirlwind package. MCP does not require Viewer to inspect, build or export a
Model. Viewer can open a retained artifact without a live MCP session.

There is one build-time exception: Viewer produces a versioned static geometry
bundle that RK packages for local display. RK consumes the built files and their
manifest. Building or installing RK must not clone Viewer, run npm, or fetch an
unpinned bundle. This is asset distribution, not a Python runtime dependency.

## Current baseline

These are starting points, not acceptance evidence for the refactor.

| Repository | Inspected revision | Current work to preserve |
| --- | --- | --- |
| Rangekeeper | `7a0181774edcf29d363822b26cfb8739a467d11b` | Notebook 02 and themed Plotly book work are committed. Notebook 03 and related book changes are implemented and locally reviewed but uncommitted. The working tree also contains unrelated conflict files and other untracked material |
| Whirlwind MCP | `1490552fcd221622e490d12abe47589e00ecba53` | Clean checkout. Python API, optional stdio server and macOS Codex desktop trial kit exist. The package still pins RK with the `workflow` extra |
| Whirlwind Viewer | `c1322a078f9700c9cb90ed59b3c0fcead390da70` | Clean checkout. Local Payload browser with tree, native list/drawer, Cytoscape and Speckle exists. Portable component extraction and ChatGPT integration remain pending |

MCP has Python, protocol, installed-package and Codex CLI evidence, including
resumption. The second-computer Codex desktop trial with live user answers is
still pending. Viewer has local browser evidence on retained fixtures; that does
not establish ChatGPT operation, large-model performance or production adoption
of Payload. Correct the stale Viewer plan statement that the MCP adapter itself
is pending when the repository plans are aligned.

The walkthrough baseline is the current three-notebook book. Preserve its teaching
sequence and the current Notebook 03 work before making package changes. Do not
restart from the committed Notebook 02 state and discard the later work.

## Rangekeeper structure

The target Python package has the following relevant structure. Existing domain
modules not shown here retain their current owner.

```text
src/rangekeeper/
├── model/
├── specification/
├── run/
├── calculations/
├── dynamics/
├── schema/
├── shared/
├── io/
│   ├── json.py
│   ├── yaml.py
│   ├── polars.py
│   ├── speckle.py
│   ├── speckle_contract.json
│   └── ... existing stores and document IO
└── visualisation/
    ├── chart.py
    ├── table.py
    ├── graph.py
    ├── geometry.py
    └── assets/ ... pinned local display files and licenses
```

Use `visualisation`, with singular module names. Use one matching installation
extra, `visualisation`, and update all known callers in the same release. Do not
retain a `visualization` extra as an alias. The module package expresses the
local display responsibility; it does not rename every existing adapter into
that package.

| Current capability | Target |
| --- | --- |
| `adapters/plotting.py` | `visualisation/chart.py` |
| Hierarchy charts in `adapters/visualization.py` | `visualisation/chart.py`; retain sunburst, treemap and icicle behaviour used by callers |
| `adapters/presentation.py` | `visualisation/table.py`; preserve useful Stream and modelling table display |
| Simple notebook graph helper | `visualisation/graph.py`, using PyVis; keep pedagogical labels, direction and selection appropriate to a local graph |
| Local notebook geometry display | `visualisation/geometry.py`, a small Python interface over Viewer-built static assets |
| `adapters/polars.py` | `io/polars.py`; preserve typed conversion, identity, missingness and provenance references |
| `adapters/csv.py` | Delete the wrapper. Use explicit Polars export for suitable tables. Keep any required precision or value-encoding safeguards with the conversion that needs them |
| Pure canonical Speckle envelope mapping | `io/speckle.py` plus its contract resource |
| Model, Specification and Run IO and stores | Remain in `io` |
| Portable C# Model library and generic Grasshopper record, composition, validation and export components | Remain under `src/grasshopper`, with their contract and authoring tests |
| `DesignExampleComponent` source reading, geometry extraction and interpretation | Move to the optional Rhino/Grasshopper integration in MCP, with its ingestion component and source-specific tests |

The canonical table representation stays with the modelling owner. Formatted
display belongs in `visualisation.table`; transformation of source evidence
belongs in MCP. CSV is a projection format, not a lossless substitute for a
canonical Model document.

Update lazy imports from `model.flux`, display methods and other active callers.
Importing RK core must not import plotting, Speckle SDK, spreadsheet readers or
browser packages. Keep numerical solvers required by modelling and execution in
RK. Move solvers used only for graph presentation to Viewer.

Remove `adapters`, `workflow`, `migration` and `legacy` from the installed RK
package after their supported responsibilities have moved or been retired. Do
not leave forwarding modules, lazy redirects or wrappers that import Whirlwind.

## Grasshopper modelling and Rhino ingestion

Split the current Grasshopper project by responsibility. Explicitly constructing
an Entity, Value, Relationship, Assembly or Model is modelling. Deciding which
records a Rhino layer represents, or how geometry supplies their measurements,
is source interpretation. The host application does not determine the owner.

RK retains `src/grasshopper/Model`: generated canonical records, serialization,
identity, composition, local validation and the shared envelope contract. This
library remains independent of Rhino and Speckle. RK also retains the generic
components in `RecordComponents.cs` and their `RecordGoo` bridge. A user can author,
validate and export a Model in Grasshopper without installing Whirlwind. Export
returns canonical data; acquisition, service authentication and ingestion
workspace operations belong in MCP.

Move the current `DesignExampleComponent.cs` implementation into an optional
Rhino/Grasshopper integration owned by MCP. It reads a `.3dm` file, interprets
`complex::` layer names and object attributes, slices geometry at declared floor
elevations, calculates measurements and records source evidence. These are
ingestion responsibilities even though the component emits a canonical Model.
Move any Grasshopper component that invokes this ingestion with it. Do not leave
an RK wrapper that imports or launches MCP.

The MCP repository can hold this integration as a separate source project, for
example `integrations/rhino/`, with extraction, host components and tests. Keep
Rhino-dependent geometry operations in their supported runtime; this move does
not require a Python rewrite of Brep operations. Define explicit invocation,
input, output and failure contracts before connecting it to the workspace API.
The integration must be usable without an LLM or a running MCP server. Ordinary
MCP installation and non-Rhino source workflows must not require Rhino,
Grasshopper or the .NET toolchain.

The dependency is the MCP-owned integration to the public RK C# library and,
where needed, its generic Grasshopper record bridge. Pin the compatible RK
assemblies or packages and canonical schema. Do not copy generated record classes
into a separately maintained model library or use build references to another
developer checkout. RK must have no dependency on the MCP integration.

Keep canonical C# contract and generic authoring tests in RK. Transfer source
interpretation and geometry-extraction assertions to MCP. Split the current Rhino
acceptance driver and example definition so the generic RK host check can run
alone, while the source-to-Model example exercises the optional MCP integration.
Update executable definitions and assembly references together. Preserve original
Rhino/GHX source evidence and accepted semantic comparisons. Delete predecessor
components; do not create compatibility assemblies or duplicate component
registrations. Current canonical component identities need not change merely
because an implementation changes repositories.

## Whirlwind MCP structure

Keep the existing `whirlwind_mcp` package and workspace API. Add the ingestion
implementation below it; do not create a second workflow service.

```text
src/whirlwind_mcp/
├── workspace.py             existing application entry points
├── wire.py                  service response contracts
├── server.py                optional MCP transport
├── workflow/                extracted ingestion engine and Evidence
└── sources/
    ├── excel/
    ├── document.py
    └── speckle/             source reading, transport and explicit mapping
```

Move the whole active ingestion workflow, including source bindings, catalog,
operations, checks, recipe composition, execution, transient Evidence, provenance
construction, reports, progress and CLI responsibilities. Keep one ingestion
engine behind both Python and MCP. Preserve the current recipe meaning unless a
specific change is recorded and tested.

Move Excel extraction, inspection, snapshots, classification and source mapping.
Move document source inspection. Move Speckle acquisition, object detachment and
the explicit conversion used to rebuild the retained design source. A source
reader can support a named historical input format without exposing any former
RK API. It must not import the predecessor runtime.

The optional Rhino/Grasshopper source integration follows the split above. Its
source checks, mappings and provenance participate in the same retained ingestion
contract. It must not become an independent interpretation workflow hidden inside
a Grasshopper component.

Transient ingestion Evidence and canonical provenance are different owners.
MCP owns observations, interpretation rules and the builder that translates them.
RK owns the Source, Location, Claim, Method and other canonical records that are
part of the saved Model contract. Do not create a second Model or provenance
schema in MCP. Preserve claim links, stable source locations, uncertainty,
conflicts, missing values, real zero and `False`.

Replace every cross-repository private import. In particular, audit workflow
operand handling, structured encoding, JSON copying and atomic file operations.
Expose a small public RK operation only where it expresses a modelling concern.
Place workspace file writes and ingestion-only helpers in MCP. Do not make all
RK internals public to make the move compile.

The current review/workbench code imports Cytoscape assets and writes viewer
HTML. Split this dependency. MCP must always export the canonical Model, checks,
manifest and a usable interpretation report with exact target references.
An optional Viewer adapter can add a browser or static advanced report. Core
builds must not fail because a renderer is absent.

Preserve workspace isolation, source hashes, retained decisions and rationale,
decision invalidation, restart/resumption, bounded resources and failure
behaviour. A failed build must not return a previous successful Model as the
new result. Do not add selective decision invalidation, source replacement or
remote hosting as part of this extraction.

## Whirlwind Viewer structure

Retain the existing app as the working browser. Extract a reusable component
package inside this repository, for example `packages/viewer`, with components,
projections and browser contracts. Keep Payload/Next and ChatGPT adapters outside
the shared components. Keep any Python graph layout tooling in a separate
installable subproject, for example `python/src/whirlwind_viewer`.

Loading a canonical artifact into Payload remains Viewer work. This builds a
derived browsing index from an existing Model. Preserve the original bytes and
their identity; keep projections rebuildable and user access read-only. Source
interpretation and construction of that Model remain MCP work. Viewer must not
add another interpretation engine under its importer.

Viewer owns the advanced Cytoscape client, projection/routing code, graph document
generation, layout profiles, reduction, layout solvers and layout review tools
that now live under RK's Cytoscape adapter. It also owns their fixtures, tests,
bundled assets and third-party notices. This does not move mathematical
formulations or RK's execution solvers.

Do not install two maintained graph browsers in the same repository. Compare the
RK browser with the existing Viewer components. Transfer useful projection,
layout, provenance and selection behaviour into the shared implementation, then
delete redundant renderer code. Retire an old surface explicitly if its behaviour
is no longer in scope; do not silently lose it during a file move.

The product direction from the Viewer session remains:

1. Shared tree, graph, 3D, inspector and table components.
2. A full standalone browser that composes those components and works without
   ChatGPT.
3. Focused ChatGPT resources that use the same components, selected to fit the
   question and available data.
4. Optional full-browser embedding, with separate host acceptance.

First define artifact, scope, selection, data access and inspect-event contracts.
Then extract the tree and object/evidence inspector and compose them back into
the full browser. Mount them independently without Payload or ChatGPT providers.
Isolate graph and geometry loading through host adapters. A geometry component
must not assume a particular `/api/geometry` endpoint exists.

Payload's native list and drawer may remain host controls. Share inspector content
and evidence logic. If a focused table is offered in ChatGPT, the standalone
browser must offer that same component too; a different native list alone does
not establish parity. Keep Payload adoption and the separate v4 beta experiment
outside this refactor decision.

Preserve canonical node and Relationship identity, relationship direction, shared
membership occurrences and distinct membership edges. A cycle can prevent a tree
perspective while the graph remains usable. A browse occurrence must not become a
new domain entity. Keep the recorded limits on inspector coverage, retained-model
lifecycle and scale until new evidence closes them.

## Shared contracts

| Contract | Authority | Consumers |
| --- | --- | --- |
| Canonical Model, Specification, Run, identity and provenance semantics | RK | MCP, Viewer and Grasshopper |
| Ingestion recipes, source evidence and decision records | MCP | Python callers, harnesses and ingestion review surfaces |
| Tool/resource messages, artifact access and viewer service requests | MCP | MCP clients and Viewer host adapters |
| Component data, rendering events and local presentation state | Viewer | Standalone browser, focused resource shell and local static renderer |
| Canonical Speckle envelope and geometry associations | RK | Python codec, generated C# constants, source adapters and Viewer |

Pin canonical schemas or generate consumer types from them. Do not copy and
independently edit their meaning. Keep the server-facing contract in MCP and the
component-facing contract in Viewer, with a tested adapter between them. This
plan requires no fourth repository or generic integration framework.

Selections and evidence requests must identify one exact Model revision/artifact
and canonical target. Add scope and an occurrence path where relevant. Viewer
database IDs and visual occurrence IDs must never replace canonical identity.
Reject stale or inaccessible artifacts explicitly. Do not fall back to the most
recent Model. Unknown geometry and absent associations remain visible states.

### Why the Speckle contract is shared with C#

The existing `adapters/speckle/contract.json` defines the envelope format
`rk.speckle-model/v1`, its `rk_format`, `rk_model` and `rk_associations` fields,
and association keys such as `model_revision` and `domain_id`. Python reads this
file. `tools/schema/generate_csharp.py` also reads it and generates
`src/grasshopper/Model/Generated/TransportContract.cs`.

The generated C# file contains matching field and format constants. It does not
generate the Python modelling implementation. The sharing lets Grasshopper write
an envelope that Python can read, and lets both sides agree which canonical
object a geometry object describes. The canonical Model is carried in the
envelope; geometry remains separate and is linked by explicit associations.

Move the resource to `io/speckle_contract.json`, update the generator and package
data, and keep the field names and format value unchanged unless an actual wire
change requires a new version. These names describe the current contract. They
are not compatibility aliases. Keep generation freshness, fixture round trips
and association validation as acceptance checks.

### Build identity and reproducibility

The current implementation fingerprint assumes that workflow, adapters and model
code share one RK package. Replace it with inventories for the relevant RK and
MCP code, schemas and dependencies. Record both package revisions and installed
artifacts. Record Viewer assets separately from computation inputs unless a
specific rendering operation actually affects the model build.

For Rhino ingestion, also record the integration build, RK C# assembly/schema
versions, geometry runtime and explicit extraction rules. Treat these as build
inputs where they affect source interpretation or derived measurements.

Do not blindly change recorded method identifiers when Python modules move.
Separate semantic method identity from implementation location. Changed
implementation provenance can legitimately produce a new Model revision.
Preserve business IDs and compare domain values, relationships, units and
evidence links across the move. Require exact reproducibility within the new
pinned environment; do not force old bytes by omitting changed provenance.

Old accepted artifacts remain readable under their declared current schema.
Rebuilding an old artifact byte-for-byte may require its archived old environment.
This is a reproducibility record, not a reason to ship old runtimes in the new
packages. Keep an explicit comparison record if a refactor rebuild changes the
Model revision.

## Walkthrough preservation

RK remains the owner of the walkthrough curriculum and book. A normal walkthrough
run loads the prepared canonical Model and retained geometry, models the problem,
and displays the result. It must not require a running MCP server, Viewer app,
Payload database or ChatGPT session.

Move source preparation and interpretation into MCP. Keep a documented preparation
command or recipe that rebuilds the RK teaching fixture from retained source.
The examples preparation environment may use the MCP Python package. The RK
runtime and prepared-data lessons must not acquire that dependency through an
import. Rewrite synthetic example builders that use the old Speckle converter
to construct canonical records directly where source interpretation is not the
lesson.

The Rhino source-preparation example uses the optional MCP integration. Generic
RK Grasshopper modelling examples remain independent. Preserve their separate
setup instructions and acceptance checks; running the prepared-data book must
not require either Rhino or Grasshopper.

The local geometry helper must load the retained Speckle source with verified
associations. Package a local renderer build, asset manifest and required notices.
Keep complete source closure and data hashes. A hosted viewer link that expires
does not satisfy the lesson. Local display must work with its documented notebook
or book serving method without requiring remote source retrieval. If a small
local file server is necessary, supply a simple helper and test the workflow.

Preserve the current mixed-use property's objects, shared membership, relationships
and design-to-value explanation. Preserve Notebook 03's dated development plan,
forward/inverse SFFA examples and funding constraints. Compare its financial
outputs against the existing independent audit. Keep false, zero, unavailable
contributors and complete-versus-partial totals distinct.

Retain theme-aware Plotly charts, tables and simple PyVis graphs. Promote only
general display behaviour into RK; keep teaching-specific colours, narrative
layout and examples in notebook helpers. Ensure chart state survives theme changes
where the current book supports it.

Accept all three active notebooks from clean candidate wheels. Execute every code
cell and rebuild the four-page book. Inspect rendered charts, graph interaction,
local 3D, selection/inspection, tables, theme changes and narrow layouts. Keep
source data unchanged. Save the checks and distinguish browser observations from
unit-test results. Add live notebook-host checks where package/display behaviour
changes; a book preview alone does not establish every notebook host.

The older notebooks are teaching references. They do not require restoration of
removed APIs. Notebooks 04–06 remain feature work after this refactor: market
uncertainty, timing/phasing, and design flexibility. Keep their existing capability
questions and curriculum sequence.

## Zero legacy target

Delete the following from supported packages and active commands:

- The old Python Graph/Measure/Speckle runtime, its predecessor tests and excluded
  C# predecessor tree.
- `rangekeeper.legacy`, the `legacy` extra, obsolete exports and old test exclusions.
- The old adapter/workflow import paths and the superseded installation extras
  after callers have moved. Remove `workflow`, `speckle` and `layout` from RK when
  their integrations have transferred; retain modelling execution dependencies.
- Draft/graph/scenario schema upgraders without a current supported consumer.
  Remove old layout-profile upgrades after retained required profiles have been
  converted once. Do not add automatic detection or fallback into current loaders.
- Duplicate browser implementations, forwarding packages and compatibility
  facades created only to preserve the previous repository layout.

Update all known active callers together. If a retained project needs an obsolete
format, convert it once with a pinned old tool before deletion, or declare an
explicit current source reader in MCP. Do not import a converter on the assumption
that some unknown downstream user might need it. Publish clear breaking-change
instructions when this refactor is released.

The local static import audit found no maintained canonical runtime dependency
on `rangekeeper.legacy`. The active .NET 8 projects use explicit compile lists
that exclude the C# predecessor. Some tests and source-preparation callers still
use `migration`; each needs conversion, relocation or retirement. This evidence
supports a clean break but does not enumerate unknown external consumers.

The following material must remain, with the indicated owner:

| Material | Reason and owner |
| --- | --- |
| Current canonical schemas, IO, identity and provenance rules | Active RK contract; required by all three repositories |
| Portable C# model library, generic Grasshopper authoring, C# generation and canonical envelope fixtures | Current RK modelling implementation and cross-language verification |
| Active Rhino source extraction, interpretation and its Grasshopper entry component | Reproducible geometry ingestion in the optional MCP integration; retain its source-specific assertions and evidence |
| Reader for the retained historical Speckle source used by the walkthrough | Required for reproducible source-to-Model preparation; explicit source support in MCP, without the old runtime |
| Original Rhino/GHX files, source archives, hashes and canonical fixture data | Evidence for the teaching model and independent comparisons |
| Useful semantic assertions from predecessor/migration tests | Rewrite as current canonical or source-reader tests before deleting their old harness |
| Git history, schema history and dated acceptance records | Historical evidence, not executable compatibility |

Zero legacy means zero compatibility APIs and predecessor runtimes. It does not
mean deleting historical source data. To remove the historical Speckle reader too,
first replace that teaching source with an accepted canonical source and record
the resulting provenance/reproducibility change. That replacement is not required
for this refactor.

Keep canonical Windows/Rhino connector acceptance open. Update configurable Rhino
references and acceptance-script paths where required, then test the active
connector on its claimed platform. Do not mark Windows accepted because legacy
code was deleted or because macOS/offline tests passed. Use the revised
[retirement procedure](../contributing/legacy-retirement.md).

## Implementation control

This plan is the integration authority for ownership, sequencing and shared
contracts. Repository-local plans own their detailed implementation tasks. A
conflict must be resolved here before changing a shared boundary. Each change
must name the affected contract, consumer updates and acceptance evidence.

The existing sessions are the intended implementation owners when work is released:

| Session | Repository and work | Hold and restart point |
| --- | --- | --- |
| [Whirlwind Walkthroughs](codex://threads/01a118ff-697e-7161-bbfe-c56b55f0cecd?hostId=remote-control%3Aenv_e_6a067b397c28832ca54b3ab6a28ee817) | RK: preserve the current Notebook 03 work; make package, display, IO and portable C# changes; separate generic Grasshopper modelling from source ingestion; run model, authoring and book acceptance | No Notebook 04–06 authoring during the refactor. Resume the curriculum only after coordinated acceptance |
| [Whirlwind MCP](codex://threads/01a13247-832f-77a1-8f80-1153ba712e84?hostId=remote-control%3Aenv_e_6a067b397c28832ca54b3ab6a28ee817) | MCP: extract ingestion, including the optional Rhino/Grasshopper source integration; remove the RK workflow dependency; revise manifests, tests, docs and the desktop trial kit | Defer the second-Mac trial until new package pins are accepted. Then resume at setup and a successful empty `workspace_list`, before live interpretation answers |
| [Model Browser Spike](codex://threads/01a1328c-ef42-7073-882e-619c6a1847d6?hostId=remote-control%3Aenv_e_6a067b397c28832ca54b3ab6a28ee817) | Viewer: define shared component contracts; consolidate advanced renderers/layouts; extract tree/inspector; produce the local geometry bundle | Preserve the working standalone browser. After refactor acceptance, resume actual focused ChatGPT integration and its host checks |

These are assignments, not dispatched prompts. All three sessions remain held
until the user starts implementation under this plan. Their recorded working
directory can still be RK, regardless of title. Every implementation handoff must
state the exact repository root and allowed files. Do not let a Viewer or MCP
session edit RK implicitly.

Before a phase starts, record its baseline commits and approved working-tree
contents. Preserve the uncommitted Notebook 03 work in a reviewed checkpoint or
recoverable snapshot before changing imports. Do not use a clean checkout that
omits it. Preserve unrelated sync-conflict files and the untracked root
`grasshopper/` material separately; they are not an authorized bulk deletion list.

The coordinating session owns shared contract changes, candidate package pins
and the final acceptance record. The owner of each repository implements its
assigned changes. Cross-repository edits need a coordinated handoff, not duplicate
patches from several sessions. Do not restart general feature development between
partially completed phases.

## Ordered implementation

| Phase | Work and dependency | Exit evidence |
| --- | --- | --- |
| 0 Preserve baseline | Snapshot reviewed dirty work; inventory active imports, extras, commands, fixtures and assets across all three repos and known example/project consumers; record the current outputs | Recoverable Notebook 03 baseline, caller/move/delete manifest and retained artifact hashes |
| 1 Fix contracts | Agree public RK Python/C# operations, optional Rhino integration invocation and artifact pins, provenance boundary, artifact/selection contracts, Speckle resource path, fingerprints and static geometry distribution; align each repo's PLAN/AGENTS/current docs | One owner per contract; no reverse runtime dependency; exact candidate schema and contract versions |
| 2 Transfer ingestion | Move workflow, source readers and `DesignExampleComponent` extraction/interpretation to MCP; adapt its existing workspace API; split renderer-independent reports; rewrite synthetic example builders; repoint source preparation | Python ingestion and MCP produce equivalent substantive outputs; optional Rhino example preserves geometry, identity and evidence; deterministic clean rebuild; no private RK or old workflow imports |
| 3 Transfer advanced display | Extract/reuse shared components, migrate useful Cytoscape/layout behaviour, remove duplicate renderer ownership and build the portable local geometry assets | Shared tree/inspector mount outside host providers; standalone browser still works; real graph/3D render with canonical selection; static bundle has provenance and notices |
| 4 Complete RK boundary | Add `visualisation` and native IO paths; use PyVis for simple graph display; package static geometry; retain generic Grasshopper authoring and split host checks; update C# generator paths, executable definitions, notebooks, examples and extras | Installed RK core and generic Grasshopper modelling are independent of MCP; simple local display and canonical envelope round trips work; active notebooks use new paths |
| 5 Delete predecessors | Remove obsolete runtimes, migrations, imports, extras, test exclusions and duplicate code after current semantic tests have moved | Installed-package and source scans show no forbidden compatibility paths; retained sources rebuild through the explicit MCP reader |
| 6 Accept and release control | Install matched candidate artifacts, run per-repo and integrated checks, record deviations and update active docs/locks | One acceptance manifest names all commits, wheel hashes, schema/service/UI versions, geometry asset hash and pending external checks |

Prepare interdependent phases as coordinated changes. In particular, MCP may need
a candidate RK wheel containing the agreed public API before RK removes workflow.
Use exact artifacts during staging. Do not merge or publish a consumer that points
at deleted producer code, a mutable branch tip, or an unpublished dependency.
No temporary compatibility shim may remain at phase 6.

Coordinate the Rhino integration transfer with the RK C# package/assembly build,
updated Grasshopper definitions and split acceptance drivers. Record the exact
host binaries in the acceptance manifest alongside Python wheels and Viewer
assets. Do not remove the working source example before its replacement passes
the retained source and geometry comparisons.

## Acceptance and scope limits

| Area | Required check |
| --- | --- |
| RK core | Installed core import, schema suites, canonical validation, calculations and execution; no ingestion/UI dependencies loaded; absent old modules and extras |
| RK display | Chart/table/PyVis smoke checks and rendered inspection; real local geometry from the prepared source; lazy optional dependency behaviour |
| Python and C# contract | Fresh generated files; canonical envelope fixture round trips; exact associations, IDs, zero/false/missing and error handling |
| Generic Grasshopper modelling | Create, compose, validate, export, save, reopen and recompute with RK components alone; stable canonical identity; no MCP dependency or ingestion component registration |
| Optional Rhino ingestion | Retained `.3dm` source is unchanged; explicit layer/attribute and elevation rules; matching geometry measurements, domain identities, associations and evidence; recorded runtime/build inputs; clear failures; runs without an LLM or MCP server |
| MCP engine | Source immutability, source-change detection, interpretation questions, decisions/rationale, invalidation, provenance, failed-build isolation, workspace resumption and independent expected results |
| MCP interface | Installed Python package plus real stdio SDK tests, versioned tools/resources and bounded responses; ordinary ingestion works without Rhino, Grasshopper, .NET, Viewer, Node or LLM |
| Viewer | Exact artifact/scope/selection; shared occurrences, cycles, isolates and empty scopes; graph direction and membership distinction; source evidence; invalid/stale selections; real graph/3D, manual node drag, canvas pan and keyboard interaction; user writes denied |
| Advanced layout | Transferred model/solver/validation tests and explicitly recorded solver availability; no claim that a missing optional solver passed |
| Walkthroughs | All cells in Notebooks 01–03 executed from candidate wheels; independent financial comparisons; four-page book and actual display interactions inspected |
| Integrated flow | Retained source → MCP Python build → RK load/validate/model → Viewer open/select/evidence → changed recorded rule → new Model; old Model remains intact; repeat build without chat |
| Packaging and documentation | Fresh installs, licenses/assets included, known consumers updated, no absolute developer-path dependency, current docs and locks consistent, documentation checks pass |

Keep separate completion states for refactor acceptance and external/product
acceptance. The second-Mac desktop trial, actual ChatGPT checkpoints C1–C7,
full-browser embedding E1, deployment choice, production Payload adoption, large
model/concurrency work and canonical Windows connector acceptance are not proved
by this refactor. Preserve their open status and named owners.

The MCP repository's `docs/chatgpt-plugin.md` remains the authority for C1–C7 and
E1. Shared component extraction provides a foundation; actual ChatGPT tool/UI
round trips, graph/3D rendering, artifact isolation, evidence exchange and
standalone parity must still be verified in the claimed hosts. E1 is additional
to the first focused resource.

After phase 6, release the paused workstreams against the recorded package pins.
MCP resumes the staged desktop trial, Viewer resumes focused ChatGPT integration,
and RK resumes the walkthrough curriculum. Commit, push and release publication
remain explicit delivery actions. No runtime or platform acceptance is claimed
by approval of this plan alone.

## Supporting records

- [Package and project ownership](004-package-and-project-ownership.md)
- [Walkthrough curriculum](006-walkthrough-curriculum.md)
- [Prepared property source](../guides/mixed-use-project.md)
- [Notebook 03 local acceptance](../research/notebook-03-2026-10-13/README.md)
- [Windows acceptance](../contributing/windows-acceptance.md)
- [Documentation lifecycle](../contributing/documentation.md)

Use the MCP repository's `PLAN.md`, `docs/architecture.md`, `docs/python-api.md`,
`docs/mcp.md`, `docs/developer-trial.md` and `docs/chatgpt-plugin.md` for its current
service contracts and pending host checks. Use the Viewer repository's `PLAN.md`,
`docs/ARCHITECTURE.md`, `docs/CHATGPT.md` and `docs/FINDINGS.md` for its shared
component direction and measured local limits. Preserve dated evidence; update
current plans when implementation changes their state.

## Implementation record

See [local validation and deviations](../research/three-repository-refactor-2026-10-13/README.md)
and its artifact manifest. The three sessions remain undispatched. External host and
product acceptance gates remain open. The old separate layout browser controls listed in
the record are retired; there is one shared browser component owner.
