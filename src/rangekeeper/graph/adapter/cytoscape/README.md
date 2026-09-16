# Offline Cytoscape graph review

`rangekeeper.graph.adapter.cytoscape.project(graph_or_view, name, config)` projects canonical objects and explicit Assembly memberships. `write_viewer([document], path)` validates and writes one offline HTML file. Neither edits the Graph or defines persistence. Existing PyVis visualization APIs are unchanged.

Optional configuration: positions, notes, anchors, initialFocus, alignment and containmentClassifications (classification UUID strings). Without explicit containment classifications, the adapter makes no domain-specific containment inference. Relationship filters use classification UUIDs, so identical codes in different taxonomies remain distinct. View exports include only selected nodes, edges and their in-scope memberships.

The Python package includes pinned Cytoscape/fCoSE assets and licences; users need no Node runtime or network connection. Source text is written with textContent and JSON escaping; the HTML blocks network connections. Invalid identities, endpoints, membership cycles and finding links fail before writing.

## Maintained implementation

- `document.py`: export validation; `client/document.ts`: typed browser contract.
- `client/context.ts`: explicit mutable display state and action interfaces.
- `client/app.ts`: offline bootstrap and controls.
- `client/projection.ts`, `membership.ts`: pure nested collapse and membership traversal.
- `client/geometry.ts`: Assembly bounds, native endpoints and label geometry.
- `client/routing.ts`: independently testable four-port Bézier mathematics.
- `client/navigation.ts`: focus, history, reveal and arrangement restoration.
- `client/inspector.ts`: safe values, provenance and review findings.
- `client/renderer.ts`, `styles.ts`: native Cytoscape lifecycle, selection, dragging, fCoSE and styling.

Run `npm ci`, `npm run typecheck`, `npm run build`, `npm test` inside client. Commit the compiled browser assets when publishing changes; Python wheel packaging includes those assets and licences, not node_modules. Generic JS regressions live in client/test. Mandarin's spike retains its synthetic fixtures and browser workflow tests.

A collapsed ancestor hides members reachable only through that path. A second visible expanded membership path preserves a shared object. Summaries redirect hidden endpoints to visible collapsed ancestors, retain distinct original IDs and never become domain relationships. Nested membership connectors record their paths. Reveal chooses a deterministic root path and expands it explicitly; simply inspecting a hidden object changes no collapse state.

Native boxes follow visible direct members, including child boxes; bounds update from deepest to shallowest. Group dragging translates unique visible descendants once. Hidden member positions remain saved. Whole graph changes scope; restore changes positions; layout stays explicit. Rectangles may enclose unrelated members and are never physical geometry. Routing preserves the accepted four-port approach, broad parallel separation and displayed-label-span alignment; it does not avoid obstacles. Large overlapping/nested graphs can remain crowded.
