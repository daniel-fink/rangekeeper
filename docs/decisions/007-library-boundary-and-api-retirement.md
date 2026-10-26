# ADR-007: Library boundary and API retirement

Status: implemented; external host acceptance remains separate. Recorded: 2026-10-13.

> RK extract, 17 October 2026: application-specific plans and identifiers were removed.
> The retained requirements describe the recorded refactor, not new verification.

## Recorded RK scope and baseline

Rangekeeper owns modelling and simple local display. The target is zero legacy
APIs, runtimes, aliases or automatic fallbacks in the supported package. Use
Rangekeeper Bundle (short: Bundle) for the immutable deliverable described by the
older Package terminology in this record.

The refactor replaced the requirement to retain predecessor code until Windows
connector acceptance. Canonical Windows acceptance remains open and controls the
platform support claim; it does not require the excluded predecessor implementation.

The RK repository name and modelling ownership remain unchanged. RK owns canonical
Model, Specification and Run records, schemas, units, validation, calculations,
execution, provenance, native IO, local display, the portable C# model library and
generic Grasshopper modelling components. Source interpretation, workspaces,
service transports and application browsers are outside the library.

The recorded starting revision was `7a0181774edcf29d363822b26cfb8739a467d11b`.
Notebook 02 and themed Plotly book work were committed. Notebook 03 and related
book changes were implemented and locally reviewed but uncommitted. The working
tree also contained unrelated conflict files and other untracked material.
These are starting conditions, not refactor acceptance evidence.

The baseline was the current three-notebook book. Preserve its teaching sequence
and Notebook 03 work before package changes. Do not restart from the committed
Notebook 02 state and discard later work. The RK workstream covered package,
display, IO and portable C# changes, generic Grasshopper authoring, and model,
authoring and book acceptance. Notebook 04–06 authoring remained on hold during
the refactor, with curriculum work to resume after acceptance.

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
| Local notebook geometry display | `visualisation/geometry.py`, a small Python interface over Interface-built static assets |
| `adapters/polars.py` | `io/polars.py`; preserve typed conversion, identity, missingness and provenance references |
| `adapters/csv.py` | Delete the wrapper. Use explicit Polars export for suitable tables. Keep any required precision or value-encoding safeguards with the conversion that needs them |
| Pure canonical Speckle envelope mapping | `io/speckle.py` plus its contract resource |
| Model, Specification and Run IO and stores | Remain in `io` |
| Portable C# Model library and generic Grasshopper record, composition, validation and export components | Remain under `src/grasshopper`, with their contract and authoring tests |
| `DesignExampleComponent` source reading, geometry extraction and interpretation | Move to the optional Rhino/Grasshopper integration in Core, with its ingestion component and source-specific tests |

The canonical table representation stays with the modelling owner. Formatted
display belongs in `visualisation.table`; transformation of source evidence
belongs in Core. CSV is a projection format, not a lossless substitute for a
canonical Model document.

Update lazy imports from `model.flux`, display methods and other active callers.
Importing RK core must not import plotting, Speckle SDK, spreadsheet readers or
browser packages. Keep numerical solvers required by modelling and execution in
RK. Move solvers used only for graph presentation to Interface.

Remove `adapters`, `workflow`, `migration` and `legacy` from the installed RK
package after their supported responsibilities have moved or been retired. Do
not leave forwarding modules, lazy redirects or wrappers that import [external application omitted].

## Grasshopper modelling and Rhino ingestion

Split the current Grasshopper project by responsibility. Explicitly constructing
an Entity, Value, Relationship, Assembly or Model is modelling. Deciding which
records a Rhino layer represents, or how geometry supplies their measurements,
is source interpretation. The host application does not determine the owner.

RK retains `src/grasshopper/Model`: generated canonical records, serialization,
identity, composition, local validation and the shared envelope contract. This
library remains independent of Rhino and Speckle. RK also retains the generic
components in `RecordComponents.cs` and their `RecordGoo` bridge. A user can author,
validate and export a Model in Grasshopper without installing [external application omitted]. Export
returns canonical data; acquisition, service authentication and ingestion
workspace operations belong in Core.

Move the current `DesignExampleComponent.cs` implementation into an optional
Rhino/Grasshopper integration owned by Core. It reads a `.3dm` file, interprets
`complex::` layer names and object attributes, slices geometry at declared floor
elevations, calculates measurements and records source evidence. These are
ingestion responsibilities even though the component emits a canonical Model.
Move any Grasshopper component that invokes this ingestion with it. Do not leave
an RK wrapper that imports or launches Core.

The Core repository can hold this integration as a separate source project, for
example `integrations/rhino/`, with extraction, host components and tests. Keep
Rhino-dependent geometry operations in their supported runtime; this move does
not require a Python rewrite of Brep operations. Define explicit invocation,
input, output and failure contracts before connecting it to the workspace API.
The integration must be usable without an LLM or a running MCP server. Ordinary
Core installation and non-Rhino source workflows must not require Rhino,
Grasshopper or the .NET toolchain.

The dependency is the Core-owned integration to the public RK C# library and,
where needed, its generic Grasshopper record bridge. Pin the compatible RK
assemblies or packages and canonical schema. Do not copy generated record classes
into a separately maintained model library or use build references to another
developer checkout. RK must have no dependency on the Core integration.

Keep canonical C# contract and generic authoring tests in RK. Transfer source
interpretation and geometry-extraction assertions to Core. Split the current Rhino
acceptance driver and example definition so the generic RK host check can run
alone, while the source-to-Model example exercises the optional Core integration.
Update executable definitions and assembly references together. Preserve original
Rhino/GHX source evidence and accepted semantic comparisons. Delete predecessor
components; do not create compatibility assemblies or duplicate component
registrations. Current canonical component identities need not change merely
because an implementation changes repositories.

## Notebook Geometry ownership — 14 October 2026

RK owns the standalone Speckle viewer used by its walkthrough notebooks, including
source, npm build, third-party notices and packaged assets. Source lives in
`tools/geometry`. Python installation uses the prepared RK assets; it does not run
npm or fetch an unpinned bundle. This amends the earlier asset-build ownership in
the table above. See [the build procedure](../../tools/geometry/README.md).

RK owns canonical Bundle/schema rules and its Parquet mapping/reader, with optional
storage adapters. [ADR-008](008-rangekeeper-bundle-contract.md) owns canonical conformance.
Reader and external host acceptance remain separate. A complete retained Bundle
needs no original source connection or credentials.

## Shared contracts

| Contract | Authority | Consumers |
| --- | --- | --- |
| Canonical Model, Specification, Run, identity and provenance semantics | RK | Core, Interface and Grasshopper |
| Ingestion recipes, source evidence and decision records | Core | Python callers, harnesses and ingestion review surfaces |
| Tool/resource messages, artifact access and viewer service requests | Core | MCP clients and Interface host adapters |
| Component data, rendering events and local presentation state | Interface | Standalone browser, focused resource shell and local static renderer |
| Canonical Speckle envelope and geometry associations | RK | Python codec, generated C# constants, source adapters and Interface |

Pin canonical schemas or generate consumer types from them. Do not copy and
independently edit their meaning. Keep the server-facing contract in Core and the
component-facing contract in Interface, with a tested adapter between them. This
plan requires no fourth repository or generic integration framework.

Selections and evidence requests must identify one exact Model revision/artifact
and canonical target. Add scope and an occurrence path where relevant. Interface
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
Core code, schemas and dependencies. Record both package revisions and installed
artifacts. Record Interface assets separately from computation inputs unless a
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
and displays the result. It must not require a running MCP server, Interface app,
Payload database or ChatGPT session.

Move source preparation and interpretation into Core. Keep a documented preparation
command or recipe that rebuilds the RK teaching fixture from retained source.
The examples preparation environment may use the Core Python package. The RK
runtime and prepared-data lessons must not acquire that dependency through an
import. Rewrite synthetic example builders that use the old Speckle converter
to construct canonical records directly where source interpretation is not the
lesson.

The Rhino source-preparation example uses the optional Core integration. Generic
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
explicit current source reader in Core. Do not import a converter on the assumption
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
| Active Rhino source extraction, interpretation and its Grasshopper entry component | Reproducible geometry ingestion in the optional Core integration; retain its source-specific assertions and evidence |
| Reader for the retained historical Speckle source used by the walkthrough | Required for reproducible source-to-Model preparation; explicit source support in Core, without the old runtime |
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

## Recorded RK implementation controls

Before package changes, record baseline commits and approved working-tree contents.
Preserve uncommitted Notebook 03 work in a reviewed checkpoint or recoverable
snapshot. Preserve unrelated sync-conflict files and untracked root `grasshopper/`
material separately; they are not an authorized bulk deletion list.

The RK implementation added `visualisation` and native IO paths, PyVis graph
display, packaged geometry assets and generic Grasshopper authoring. It updated
C# generator paths, executable definitions, notebooks, examples and extras.
Obsolete runtimes, migrations, imports, extras and test exclusions could be removed
only after their useful semantic assertions moved to current tests.

Record exact candidate package revisions, wheel hashes, schema versions, geometry
asset hashes and host binaries. Compare retained source and geometry results before
removing a working source example. Record deviations and pending external checks;
do not use a mutable branch tip as an artifact pin or retain temporary shims.

## Acceptance and scope limits

| Area | Required check |
| --- | --- |
| RK core | Installed core import, schema suites, canonical validation, calculations and execution; no ingestion/UI dependencies loaded; absent old modules and extras |
| RK display | Chart/table/PyVis smoke checks and rendered inspection; real local geometry from the prepared source; lazy optional dependency behaviour |
| Python and C# contract | Fresh generated files; canonical envelope fixture round trips; exact associations, IDs, zero/false/missing and error handling |
| Generic Grasshopper modelling | Create, compose, validate, export, save, reopen and recompute with RK components alone; stable canonical identity; no Core dependency or ingestion component registration |
| Optional Rhino ingestion | Retained `.3dm` source is unchanged; explicit layer/attribute and elevation rules; matching geometry measurements, domain identities, associations and evidence; recorded runtime/build inputs; clear failures; runs without an LLM or MCP server |
| Core ingestion engine | Source immutability, source-change detection, interpretation questions, decisions/rationale, invalidation, provenance, failed-build isolation, workspace resumption and independent expected results |
| MCP interface | Installed Python package plus real stdio SDK tests, versioned tools/resources and bounded responses; ordinary ingestion works without Rhino, Grasshopper, .NET, Interface, Node or LLM |
| Interface | Exact artifact/scope/selection; shared occurrences, cycles, isolates and empty scopes; graph direction and membership distinction; source evidence; invalid/stale selections; real graph/3D, manual node drag, canvas pan and keyboard interaction; user writes denied |
| Advanced layout | Transferred model/solver/validation tests and explicitly recorded solver availability; no claim that a missing optional solver passed |
| Walkthroughs | All cells in Notebooks 01–03 executed from candidate wheels; independent financial comparisons; four-page book and actual display interactions inspected |
| Integrated flow | Retained source → Core Python build → RK load/validate/model → Interface open/select/evidence → changed recorded rule → new Model; old Model remains intact; repeat build without chat |
| Packaging and documentation | Fresh installs, licenses/assets included, known consumers updated, no absolute developer-path dependency, current docs and locks consistent, documentation checks pass |

Keep separate completion states for refactor acceptance and external/product
acceptance. The second-Mac desktop trial, actual ChatGPT checkpoints C1–C7,
full-browser embedding E1, deployment choice, production Payload adoption, large
model/concurrency work and canonical Windows connector acceptance are not proved
by this refactor. Preserve their open status and named owners.

The Core repository's `docs/chatgpt-plugin.md` remains the authority for C1–C7 and
E1. Shared component extraction provides a foundation; actual ChatGPT tool/UI
round trips, graph/3D rendering, artifact isolation, evidence exchange and
standalone parity must still be verified in the claimed hosts. E1 is additional
to the first focused resource.

After phase 6, release the paused workstreams against the recorded package pins.
Core resumes the staged desktop trial, Interface resumes focused ChatGPT integration,
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

## Implementation record

See [local validation and deviations](../research/three-repository-refactor-2026-10-13/README.md)
and its artifact manifest. These retain recorded local results; external host and
product acceptance gates remain separate.

See the [current architecture](../concepts/architecture.md), [upgrade guide](../guides/upgrading.md), [verification guide](../contributing/verification.md) and [Windows acceptance](../contributing/windows-acceptance.md).

Supersedes: none. Superseded by: none.
Amended by: [ADR-010](010-layers-and-packages.md), accepted 2026-10-26. Local display adapters move to the walkthrough helpers; the Grasshopper solution moves to `examples/grasshopper`.
