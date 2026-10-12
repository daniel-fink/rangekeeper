# Notebook 02 From design to property economics

Status: condensed outline agreed and applied on 2026-10-13. This replaces the
12-section sequence of 2026-10-12 under [ADR-006](006-walkthrough-curriculum.md).
See the [initial acceptance](../research/notebook-02-2026-10-12/README.md) and
[condensation acceptance](../research/notebook-02-2026-10-13/README.md).

## Purpose and boundaries

Answer: **How do the spaces, buildings and shared systems in a property produce
its income, costs and value?** Use the complete legacy mixed-use project: two
buildings, a shared basement plinth and shared services. Treat it as a proposed
completed property. Periodic asset CAPEX is not a development budget.

Notebook 01 supplies Flow, Stream, projection and DCF concepts. This chapter adds
objects, relationships, contributor selection and traceable value. Notebook 03
introduces development timing, funding and forward/inverse questions.

Keep each section focused: a short explanation, visible calculation or selection,
useful output and brief interpretation. Distinguish recorded quantities, financial
assumptions and calculated results. Keep the source Model unchanged.

## Visual requirements

| Aid | Placement and purpose |
| --- | --- |
| Local Speckle viewer | Opening context/property/floor inspection; another embed beside utility costs |
| [Property as a graph](../../examples/walkthrough/resources/devModelGraph.jpg) | Keep inline between geometry and the actual graph. It connects physical components to graph objects; identify it as a concept illustration |
| [Overlapping assemblies](../../examples/walkthrough/resources/devModelAssembly.jpg) | Explain different relationships and groupings |
| [Current record diagram](../../examples/walkthrough/resources/mixed-use/object-model.svg) | Explain Model, objects, characteristics and separate numerical calculations |
| Full PyVis graph | Inspect the actual source objects and relationship labels |
| Spatial PyVis tree | Follow floor → use → building → property |
| Service PyVis graph | Follow plant → cores → served spaces |
| Four Plotly sunbursts | GFA, 2001 EGI, 2001 OPEX and first-payment CAPEX; common hierarchy and colours |
| One Plotly income time-series chart | Recall dated growth and vacancy at floor scale; inspect dates and amounts on hover |
| Native Polars tables and Flow/Stream displays | Bounded inputs, quantities, pro forma, reconciliation and sensitivity |

Remove the two static rendered mesh images from the chapter. Remove the GFA and
income treemaps and the repeated floor-only geometry embed. Retain the local
Speckle SDK and captured archive. The expired hosted model is a source reference,
not a runtime dependency. Geometry, graph and chart selections remain independent.

### Presentation helpers

Use `examples/walkthrough/helpers/plot.py`, with `helpers/__init__.py`, for graph
layout, short labels, hover text, local HTML export and iframe display.
`show_graph()` wraps the existing PyVis adapter; `show_sunburst()` wraps the
existing `rangekeeper.adapters.plotting.plot_partition()` adapter. UUIDs remain
chart identities. Expense magnitudes are an explicit display option.
`show_flows()` wraps the Plotly flow adapter. `helpers/theme.py` owns the shared
light/dark templates and stable use colours; `helpers/theme.js` follows the
book's colour mode in local embeds. Chart styling stays outside teaching cells.

Keep Model loading, relationship selection, Hierarchy validation, quantity
extraction, use interpretation, financial formulas, timing and aggregation in the
notebook. The helper must not select the financial population or supply rates.
Copy helper sources with the execution package and book. The book builder must
reject helper sources that differ from the executed copy.

## Reading and cell sequence

### 1. Meet and load the project

Introduce Building A's hotel/residential/retail/parking uses, Building B's
residential/retail/parking uses, and their shared plinth and services. Ask which
components earn income and which support operation. Inspect the geometry first.
Use the legacy illustration to connect 3D components to graph records, then load
the pinned Model and show the actual interactive graph and compact inventory.

### 2. Read the relationships

Ask what spatially contains an object, what serves it and which group includes
it. Use the assembly diagram, select each relationship type explicitly, and
validate the spatial Hierarchy. Show spatial and service views. Explain once that
service connections do not allocate costs and the utility group does not add
three more physical contributors.

### 3. From one floor to total area

Inspect the worked hotel floor's quantities and units. Explain GFA versus
lettable area and identity versus repeated names. Select floor contributors,
execute the visible Reduction, show branch totals and the GFA sunburst. Ask the
reader to predict whether area share will also imply income share.

### 4. From area to an income flow

Work GFA × efficiency × rent for one floor. Offer the efficiency change as an
optional exercise without a second worked table. Define the holding and forecast
spans, project PGI, subtract vacancy and display the named flows. Keep the short
income chart and one direct numerical check.

### 5. Apply the rule across the property

Show assumptions by use. Define `floor_income()` from the demonstrated arithmetic
and map results to floor UUIDs. Keep use lookup and missing-use failure visible.
Aggregate property income and show one income sunburst. Explain how it differs
from area; defer the full property EGI table to the pro forma.

### 6. Include operating and capital costs

Use three compact steps: annual operating costs, scheduled capital payments, and
shared services. Retain the facade proxy limitation and explicit cost signs.
Explain payment-interval growth and zero filling once. Keep event construction,
resampling, service-volume calculations and contributor selection visible. Show
OPEX and CAPEX sunbursts and the services geometry view. Include cost-only objects.

### 7. Assemble and value the property

Assemble NOI and NACF with signed Streams. Display one property pro forma and a
compact branch reconciliation, keeping shared costs separate. Define the branch
aggregation and valuation functions once and reuse them later. Capitalize 2011
NACF, receive sale at end 2010, discount the ten holding-year receipts and collapse
to start-2001 value. Show one valuation summary. Explain that branch contributions
are not separate market valuations.

### 8. Change one assumption and explain the result

Increase residential rent by 10% with other inputs fixed. Predict the affected
objects, copy assumptions, recalculate and reuse the branch/valuation functions.
Show one comparison table with affected floors, income change and value change.
Retain checks that only residential income changes and the source Model is intact.
Close with three learning points and a short bridge to development and inverse
solving. Keep legacy correction details and provenance in the source note.

## Authoring acceptance

- Execute both accepted notebooks in fresh kernels with the complete source and
  helper package. Do not require an earlier notebook's state.
- Reconcile all annual EGI/OPEX/CAPEX values, unique contributors, branch totals,
  valuation and sensitivity against independent arithmetic and prior results.
- Keep detailed audit code outside the teaching sequence.
- Verify sunburst root totals, UUIDs, expense signs, labels and drill-down.
- Inspect the chapter in notebook HTML and the local Jupyter Book: retained
  illustrations, geometry, graphs, charts, tables and source dependencies.
- Run the strict build and documentation checks. Local serving does not publish
  the book to GitHub Pages.
