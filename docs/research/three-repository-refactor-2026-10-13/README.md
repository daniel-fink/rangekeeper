# Three-repository refactor — 13 October 2026

> Edited extract, 17 October 2026: external application references were removed.
> Retained RK results keep their original scope; this is not an unchanged capture.

The implementation assigns modelling and simple local display to Rangekeeper, ingestion
to [external application omitted], and advanced browsing and layout to [external application omitted]. Runtime aliases,
predecessor implementations and old layout-format upgrades are removed. The canonical
schema stays at 0.7.0; current wire field names and semantic method identities stay intact.

## Changes and distribution

RK 0.9.0 contains `io.polars`, the pure `io.speckle` envelope, and
`visualisation.chart`, `table`, `graph`, `geometry` and `local`. Core imports do not load ingestion
or visual dependencies. MCP 0.2.0 owns the workflow, Evidence, Excel/document/Speckle readers,
source recipes and optional Rhino integration. Viewer 0.1.0 supplies the Python projection
and layout package; the web app and static export share tree, graph and inspector components.
Geometry receives an explicit asset loader in the full host. Viewer builds the pinned local
geometry asset shipped in RK; an RK installation does not run npm or need an MCP/Viewer service.

MCP and Viewer's Python checkout each contain the exact RK candidate wheel under `vendor`.
Their uv locks pin its hash. This avoids a broken dependency on an unpublished registry
version or a sibling source checkout. Replace those pins only with the matched published
artifact. The Rhino integration consumes an explicit RK assembly directory and rejects
an assembly version other than 0.9.0.0.

The original dirty Notebook 03 work, source archives, Rhino/GHX evidence, historical
notebooks and sync-conflict files were backed up before implementation. Some unrelated conflict files
were removed externally during this session; this refactor does not restore or edit them. Recoverable baseline
archives and the per-file transfer manifests are recorded by this task. No Git history was
rewritten, and no commit, push, release or service publication was performed.

## Local validation

See [the manifest](manifest.json) for baseline commits, wheel/assembly hashes, geometry
asset provenance and unchanged source hashes. The adjacent logs distinguish unit tests,
installed-package checks, source comparisons and observed UI behaviour.

- RK: **854 tests pass**. Installed-package checks cover schemas, models, units, calculations, forward/inverse
  execution, native IO, lazy display imports and absence of the old installed modules.
- MCP: **316 tests pass**. These cover source immutability, recorded decisions, invalidation, provenance,
  failed attempts, resumption, installed Python APIs and the real stdio MCP SDK.
- Viewer: **108 strict Python tests and 15 Node tests pass**. Strict tests run both MiniZinc 2.10.1/CP-SAT 9.15 and Z3 5.1.0.0 without skips.
  Browser arithmetic, artifact identity, stale selection, publication failures and native
  consumer CMS lifecycle checks also run. TypeScript checking and production build pass.
- All 81 executable cells in the three active notebooks run from installed candidate
  wheels. The strict four-page book builds. Notebook 03 passes the existing independent
  CSV/finance audit; its results remain unchanged. See [financial results](finance-audit.json).
- Both generic authoring and the moved source integration pass in Rhino 8.35 on macOS,
  using .NET 8.0.14. Save/reopen/recompute preserves content and generic revision history.
  The source comparison checks 36 entities, 14 assemblies, 63 relationships and 45 geometry
  associations at relative tolerance 1e-10 and absolute tolerance 1e-7.
- Actual browser interaction confirms shared tree scope, node dragging, canvas panning,
  canonical inspection and source evidence. The full consumer CMS host renders retained 3D;
  clicking geometry selects its canonical RK object. The book renders charts, tables,
  PyVis graphs and local geometry. Its relation selector survives a light/dark theme change.

## Deliberate interface changes

RK uses PyVis for its simple local graph. Advanced layouts are in Viewer. The separate
old Cytoscape browser shell is removed. Shared static browsing uses saved node centres;
the old compound-box controls, route overlays and fCoSE control are retired. The numerical
rectangle, routing and conflict algorithms and their tests remain in Viewer. Do not claim
complete parity with that old browser's controls.

Generic Grasshopper authoring remains in RK. The new MCP source definition uses [external application omitted]
0.2.0 and RK 0.9.0 assembly identities and requires an explicit source path. Original GHX
files remain source evidence, with no compatibility assembly installed beside the new one.

## Open gates and workstream control

Windows host/connector acceptance, the second-computer desktop trial, actual ChatGPT
C1-C7/E1, production deployment and large-model/concurrency work remain open. The local
checks do not establish any of them. The three feature sessions were not resumed or sent
implementation messages. Their restart points remain in the decision: RK curriculum after
Notebook 03, MCP desktop setup plus an empty workspace_list, and Viewer focused ChatGPT
resources over the shared components. Use the recorded candidate pins when resuming.

## Live notebooks and required consumers

Live JupyterLab renders the local Speckle view, PyVis graph and Plotly chart from the
installed RK wheel. The local display helper serves an explicit directory on loopback
with a random URL prefix. It rejects directory listings and paths outside that directory.
This fixes Jupyter's treatment of query-bearing file iframe URLs. Saved live outputs need
a running kernel; the book builder rewrites these URLs to portable relative assets.
Geometry selection shows `buildingAhotelFloor1`, GFA 1,697.452 m² and its canonical identity.
See [live Jupyter](live-jupyter.png) and [full Viewer host](viewer-host.png).
A fresh narrow-viewport check was not established: the browser retained its normal viewport.

The user authorized only the required consumer migration in the separate primary consumer repo.
Fifteen files in proving project A and proving project B update imports, dependency pins, verification
metadata, current API assertions and generated-output documentation. Sources, YAML mappings,
historical outputs and unrelated work remain unchanged. Both consume MCP's exact RK wheel.
Proving project A's eight synthetic tests, all five notebooks, and proving project B's six tests over the
two original workbook scenarios pass. Ruff and type checks pass for both projects. Old
automatic `viewer.html` links were removed from their core-ingestion instructions; advanced
export is a separate Viewer operation.

## Applied checkout verification

The same changes are now in the original repositories. Their environments synchronize
from the locked metadata. The applied MCP suite passes all 316 tests, including the RK
execution example; Polars and that execution extra are declared development dependencies.
The applied Viewer passes 108 strict Python tests, 15 Node tests, layout JavaScript tests,
and TypeScript checking. Its shared static build reproduces the packaged asset bytes.
RK's applied boundary/display/retirement check passes 51 tests and C# generation is current.
The final installed-wheel suite remains 854 passing tests. Both applied consumer suites pass.

Stale uv wheel hashes were refreshed against the final wheel. Three test files had trailing
blank lines removed. MCP's source-envelope error assertion now follows the explicit reader
message. All other post-transfer file adjustments are listed in `manifest.json`.
Only generated caches remained under retired RK namespaces. Those directories, including
an empty older `dynamics` directory, were moved intact to the recoverable task backup so
editable imports cannot discover empty predecessor namespaces. No runtime shim was added.

The applied generic RK and moved [external application omitted] Rhino assemblies also build with zero warnings
and zero errors. Their hashes are recorded separately from the assemblies used in the
macOS host acceptance run. Final preservation checks found no unrelated baseline changes
beyond the 17 externally removed conflict files. Consumer source mappings remain unchanged.
