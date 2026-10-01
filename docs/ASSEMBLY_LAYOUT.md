# Assembly layout and editable presentation

RK owns the layout contract, versioned presentation presets, geometry checking,
export and viewer interaction. Consumers own domain selectors, interpretation,
source inputs and real-workload acceptance. Library fixtures are synthetic.

## Contract and execution

Every canonical object appears once. Each assembly has one rectangle. Transitive
members must fit inside their assembly's content region; unrelated ordinary nodes
must remain outside. Header collisions and unrelated complete enclosure are
invalid. Partial overlap can represent shared membership. Geometry uses schematic
screen units and does not imply physical adjacency, scale or occupancy.

`layout/model.py` defines the bounded integer problem. `check.py` independently
checks geometry and computes scores. `seed.grid_seed` constructs deterministic
layouts for supported membership trees and returns no result when it cannot
satisfy the contract. It does not silently repair domain membership.

Z3 and MiniZinc/CP-SAT are explicit experimental solver paths. Both use the same
problem and checker. Timeout is distinct from infeasibility; a retained checked
seed does not prove optimization. Solver timing and statuses remain separate from
deterministic geometry. No solver runs in the browser. The comparison scripts
accept supplied case files; `compare_layout_solvers.py --full-case CASE_ID` selects
a case for the `--full-seconds` budget without a domain-specific special case.

## Preferences and arrangements

Direction, ordering, grid displacement, similarity and compactness are separate
objectives. An explicit packed column arrangement stacks groups vertically using
their drawn heights plus a gap; members within a group may use a compact grid.
This keeps group order without forcing every group to a single row or uniform
height. Older problem schemas preserve their original serialization contracts.

Similarity uses explicitly selected evidence fields. Missing or conflicting values
do not establish a match. Correlated fields share families to avoid counting the
same evidence repeatedly. Affinity is a presentation preference, not a graph
relationship or inferred spatial order. Ordering uses complete, disjoint numeric
ranges from selected graph characteristics; incomplete ranges remain visible in
the signal report. RK does not guess domain bindings from labels.

## Authored and resolved profiles

A consumer can select the immutable `stacked-compact-v1` preset:

```yaml
schema: rk-layout-profile-v2
preset: stacked-compact-v1
grid_classifications: [shelf]
stack_order:
  classification: shelf
  feature: rank
  descending: true
signals: []
rationales:
  grid: Compact storage groups.
  stack: Stack by declared rank; no physical scale.
notes:
  - A schematic view of the completed graph.
```

RK owns this preset's canvas limits (16000 × 30000), ordinary footprints
(248 × 44), minimum assembly width (280), padding (16), header (28), gap (12),
and objective weights (grid 4, direction 3, order 6, similarity 3, compactness 1).
A future policy change should introduce a new preset version. V2 rejects unknown
fields and inline preset overrides. Legacy `rk-layout-profile-v1` remains supported
with its explicit policy and original notes.

`profile.resolve` returns independent resolved configuration; `profile.prepare`
extracts a problem and signal report from a completed graph without graph writes.
`workflow.layout_review.build(attempt, profile=..., output_root=...)` requires a
successful current workbench attempt and verifies its artifacts and in-memory graph.
It captures authored YAML content and hash, resolved policy, implementation hashes,
signal report and completed review alongside the saved layout. Failed or interrupted
runs retain the prior successful bundle, clearly labelled as previous output.
Unique successful bundles publish their latest pointer only after export completes.

## Viewer behavior

The checked saved layout is immutable and supplies initial positions and the reset
point. Session-only presentation geometry enables dragging. An assembly drag moves
all unique descendants, including hidden descendants, exactly once. Other affected
assemblies resize without moving their unrelated members. Bounds fit visible member
footprints, including labels, from inner groups outward. Empty or collapsed groups
use compact headers; hidden object positions remain available for expansion.

Focus and collapse preserve object positions while recomputing visible bounds.
Restore saved layout clears focus, collapse and conflict indicators and restores
exact saved geometry. Relationship filters remain selected. Reloading or switching
datasets starts again from saved geometry. Back is navigation history, not drag undo.

Red feedback denotes actual collisions or incorrect enclosure; optional amber
spacing advisories denote insufficient clearance. Edited arrangements are labelled
adjusted presentation. Zero visible conflicts does not certify the original grid,
ordering or compactness constraints. Provenance and review links remain attached
to canonical objects. Legacy documents retain their existing explicit fCoSE path.

## Verification

Python tests under `src/tests/test_layout_*.py` cover contracts, profile resolution,
checker parity, saved geometry and failed export handling. Client unit tests cover
nested resizing, hidden/shared movement, visibility and conflict feedback.

Generate a wholly synthetic browser gallery and serve its output directory locally:

```sh
PYTHONPATH=src python scripts/export_layout_browser_fixture.py --output /tmp/rk-layout-browser
python -m http.server 8000 --bind 127.0.0.1 --directory /tmp/rk-layout-browser
```

Then, from the Cytoscape client directory:

```sh
npm run typecheck
npm test
RK_SAVED_VIEWER_URL=http://127.0.0.1:8000/index.html node --test test/saved-browser.cjs
```

The pointer test covers nested shelves, a legacy dataset and overlapping shared
membership with no external data. Consumer integration tests and measured real
workload results stay with their consuming repositories.
