# Notebook 02 condensation — 13 October 2026

The [chapter](../../../examples/walkthrough/design_to_value.ipynb) follows the
[revised eight-section outline](../../history/plans/006-notebook-02-outline.md).
This is a presentation and teaching revision of the
[12 October acceptance](../notebook-02-2026-10-12/README.md); the library,
source Model and financial assumptions are unchanged.

## Changes

- Combine related sections and remove repeated explanations, tables and DCF code.
- Keep the legacy 3D-to-graph illustration inline, along with the overlapping
  assemblies image and current record diagram.
- Remove the two static geometry images from the chapter, both treemaps and the
  repeated floor-view embed. Reference images remain in the resource directory.
- Keep the context/property viewer, services viewer, three interactive graphs,
  four sunbursts and one income time-series chart.
- Put colours, labels, graph layout, HTML export and iframe display in
  [`helpers/plot.py`](../../../examples/walkthrough/helpers/plot.py).
  Use the existing library adapters. Keep financial logic, quantity and contributor
  selection, and temporal conventions in the notebook.
- Reuse visible branch-aggregation and valuation functions for the sensitivity.

[Content metrics](content-metrics.json) count source words and code lines,
including blank code lines. The chapter moves from 12 to eight sections,
60 to 51 cells, and 35 to 28 code cells. Prose is about 28% shorter and visible
code about 24% shorter.

## Calculation and build verification

Both accepted chapters ran top-to-bottom in fresh Python 3.12 kernels with the
same installed Rangekeeper 0.8.71 candidate wheel as the initial acceptance.
The final notebook 02 run includes the output cleanup found during visual review.
The additional [audit](audit.py) runs after the teaching cells and is removed
before saving the notebook. [Execution results](execution.json) record the evidence.

The audit independently reads the source inventory CSV and recomputes all 11 annual
income, operating-cost and capital-cost amounts. It checks 36 unique capital
contributors, branch reconciliation, 12 affected residential floors and the unchanged
source Model. Values match both the independent arithmetic and the previous chapter:

| Case | Asset value (AUD) |
| --- | ---: |
| Reference | 209,491,758.70 |
| Residential rent +10% | 225,427,188.08 |

Generated sunburst traces also retain 50 unique object IDs and reconcile their root
totals to GFA, EGI, OPEX magnitudes and CAPEX magnitudes. Expense flows remain signed.

The strict book build includes the helper package in its stage and static output.
It compares helper Python sources with the executed copy before staging.
Both missing and changed helper copies were rejected as expected; see the
[guard checks](helper-guards.json). This is a freshness check, not an execution
attestation. Fresh-kernel execution remains required.

## Rendered review

The local book shows all eight sections, nine interactive frames and 15 tables.
The [retained illustration](illustration.png) connects 3D components to a graph.
[Sunburst drill-down](sunburst.png), hover details and use colours remain available
through the helper. The spatial graph's zoom controls still reveal the floor labels;
its initial view fits the full 50-object tree. The two Speckle embeds remain local.

The saved notebook HTML and final book were inspected for chart duplication,
missing outputs, table readability and local asset paths. The income chart is
emitted once. Browser errors were checked during review. The standalone nbconvert preview
reported one `MutationObserver.observe` error with no source location; its origin
was not established. Tables, geometry and chart interactions still rendered.
The final Jupyter Book review showed all nine interactive frames and 15 tables,
with one income chart and no new browser console errors.

Use the [walkthrough guide](../../guides/walkthroughs.md) to reproduce the execution
and local build, including copying `helpers/` with the inputs. This work does not
publish the book or change the source model's geometry or financial assumptions.
