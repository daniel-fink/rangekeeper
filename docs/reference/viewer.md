# Offline graph presentation and layout

`rangekeeper.adapters.cytoscape` projects canonical Models or pinned Views into
read-only display documents. It does not edit Model state or define persistence.
Use [canonical codecs](run-and-storage.md) to save and reload domain documents.

## Projection and offline viewer

`project(model_or_view, name, config=None)` returns detached display data.
`write_viewer([document], path)` validates that data and writes one offline HTML
file. Optional configuration includes `positions`, `notes`, `anchors`,
`initialFocus`, `alignment`, `reviewUrl` and `containmentClassifications`.
Containment and relationship filters use classification UUIDs; identical codes
in different taxonomies remain distinct. Without explicit containment selectors,
the adapter makes no domain-specific containment inference.

View exports include only selected nodes, edges and in-scope memberships. Each
export retains the pinned `modelId`. Canonical Entity and Relationship UUIDs remain
unique. Shared membership uses display-only connectors and membership paths;
a repeated outliner occurrence is not a second Entity. Invalid identities,
endpoints, membership cycles and finding links fail before writing.

The package contains pinned Cytoscape/fCoSE assets and their licences. Opening an
export requires no Node runtime or network connection. Source text uses
`textContent` and escaped JSON; the HTML blocks network connections. Bounded rich
value display identifies truncation or unsupported types. Display data cannot be
read back as a canonical Model.

## Membership, navigation and geometry

A collapsed ancestor hides members reachable only through that path. A second
visible expanded membership path preserves a shared object. Collapse summaries
redirect hidden endpoints to visible ancestors and retain the original Relationship
IDs; they never become domain relationships. Nested membership connectors retain
their paths.

Reveal chooses a deterministic root path and expands it explicitly. Inspecting a
hidden object alone does not change collapse state. Whole-graph navigation changes
scope; restore changes positions; layout remains an explicit action. The browser
inspection hook is `window.graphReview`, with navigation through `focus`, `remember`
and `collapse`.

Assembly boxes follow visible direct members, including child boxes, from deepest
to shallowest. Group dragging moves each unique visible descendant once; hidden
positions remain saved. Display rectangles can enclose unrelated objects and are
not physical geometry. Four-port Bézier routing preserves broad parallel separation
and displayed-label-span alignment; it does not avoid obstacles. Large overlapping
or nested graphs can remain crowded.

## Layout preparation and review

`adapters.cytoscape.layout.profile.prepare(model, profile)` returns a detached
`Problem` and signal report without changing or solving the Model. Profile
`rk-layout-profile-v3` resolves `System.assemblies`, classification UUIDs, property
Value keys and quantity keys with explicit units. `stacked-compact-v1` supplies the
rendering policy. Code/name lookup is confined to explicit profile authoring or
upgrade and must be unambiguous. Invalid versions, selectors, units and geometry
fail; missing evidence cannot establish a signal.

`adapters.cytoscape.layout.review.build(model, *, bundle, profile, output_root)`
accepts a canonical Model and its complete successful source-review bundle. It
checks artifact hashes and compares complete Model content with exact types,
including `0` versus `False`. It does not require a workflow Attempt object. It
prepares a constructive grid/stacked layout and writes a checked geometry/review/viewer
bundle. Shared membership is retained. If no constructive layout supports the
constraints, the attempt fails with a diagnostic; the ordinary graph viewer remains
usable and solver execution is a separate explicit operation.

Layout supports pins, preferences, arrangements, spacing, order and similarity
signals, independent geometry checks and saved fingerprints. Dragging is session
state; restore returns saved geometry. Overlap/enclosure warnings concern the
drawing, not domain validity. Constraint construction is separate from timed solver
control; MiniZinc has a separate data encoder. Z3 and MiniZinc/CP-SAT are optional
presentation solvers. Neither publishes a mathematical Run; Pyomo/HiGHS remains
the mathematical execution backend.

Invalid geometry or a damaged/wrong Model bundle cannot advance the successful
layout pointer. A pre-publication failure leaves prior output historical. Once
pointer replacement succeeds, later durability or status-record failure retains
completion and diagnostics. An interruption after publication carries
`completed_attempt`. See the shared [publication contract](workflow.md#workbench-and-publication).
Layout owns its status enums; persisted geometry/review documents keep their own
string fields.

## Maintain the viewer

The Python `document.py` and TypeScript `client/document.ts` own display validation
and types. `client/context.ts` defines mutable viewer state and actions;
`projection.ts`/`membership.ts` handle collapse and membership traversal.
`geometry.ts` owns boxes and endpoints, `routing.ts` owns routing mathematics,
`navigation.ts` owns focus/history/reveal/restore, and `inspector.ts` owns safe value
and provenance display. `renderer.ts`/`styles.ts` integrate Cytoscape.

From `src/rangekeeper/adapters/cytoscape/client`, run:

```sh
npm ci
npm run typecheck
npm run build
npm test
```

Commit rebuilt browser assets with their source changes. Wheels contain compiled
assets and licences, not `node_modules`. Use the
[layout acceptance procedure](../contributing/layout-acceptance.md) for pinned
engines and required-engine checks; local test results do not establish Windows,
Linux or remote CI acceptance unless those environments were actually run.
