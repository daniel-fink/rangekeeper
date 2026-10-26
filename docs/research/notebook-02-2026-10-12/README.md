# Notebook 02 acceptance — 12 October 2026

[From design to property economics](../../../examples/walkthrough/design_to_value.ipynb)
is authored and executed against the complete pinned legacy property. This follows
[source preparation](../notebook-02-source-2026-10-12/README.md) and the
[agreed outline](../../history/plans/006-notebook-02-outline.md). The local book includes
this chapter, notebook 01 and the introduction. Public publication remains deferred.

## Calculation acceptance

The fresh Python 3.12.12 kernel used an installed candidate Rangekeeper 0.8.71 wheel,
not an import from the checkout. The wheel was built from current source in a clean
temporary directory, excluding unrelated Syncthing conflict copies. No library
implementation changed for this chapter. The notebook has 60 cells, including
35 code cells; all executed in order without errors. Notebook 01 was also executed
in its own fresh kernel for the combined book.

[Execution evidence](execution.json) records versions, quantities and results.
The additional [audit cell](audit.py) was run in the same fresh kernel after the
chapter and removed from the authored notebook. It independently reads the source
inventory CSV and calculates all 11 annual income, OPEX and CAPEX amounts with
plain arithmetic. It also reconciles branch cash flows and values, the 36 unique
capital contributors, NOI + CAPEX = NACF, the unchanged source Model and the
12 affected residential floors in the sensitivity.

| Result | AUD |
| --- | ---: |
| 2001 effective gross income | 14,402,849.55 |
| 2001 operating expenditure | -6,268,157.66 |
| First capital payment, 2005 | -5,919,092.61 |
| Sale proceeds, end 2010 | 284,674,637.71 |
| Reference asset value, start 2001 | 209,491,758.70 |
| Asset value with residential rent increased by 10% | 225,427,188.08 |

The independent reference value is AUD 209,491,758.69565034, agreeing with the
notebook's AUD 209,491,758.69565037 within floating-point tolerance. The financial
rates remain teaching assumptions. They are not market estimates. Both physical
core systems and the plant contribute capital expenditure despite having no rent.
The old omission of utility-only costs is not retained as a golden result.

## Visual acceptance

The hosted Speckle model returned **Model expired** under its workspace history
limit. The user chose to use Speckle locally rather than substitute Plotly for
geometry. The small [viewer host](../../../tools/docs/property_viewer/README.md)
bundles the official Speckle 2.31.14 viewer and object loader. Its in-memory loader
reads all 3,007 original records from the local archive and verifies the archive
checksum. No model upload, server API, credentials or hosted saved view is needed.
The historical hosted URL remains a source reference.

Browser checks cover the embedded geometry controls, floor selection and isolation,
recorded quantities and identity, services-only geometry, and consistent use colours.
Building A hotel Floor 1 shows GFA 1,697.452 m², height 3.1 m, elevation 5.3 m and
its original content ID. The source measurements keep full precision in Python.
The local host supplies camera, selection and filtering controls; it is not the
full Speckle web application's user interface. WebGL is required for 3D inspection.
Static mesh images remain available without it.

The book renders the retained property-graph and assembly images and the new SVG
record diagram. The full graph, spatial tree and service graph use the current
PyVis adapter. Zoom and pan were checked; the 50-object spatial tree starts as an
overview and needs zoom for floor labels. Plotly area and income sunbursts and
treemaps plus separate OPEX and CAPEX sunbursts use the same hierarchy. Treemap
and sunburst drill-down and hover were checked in the embedded book. Visible chart
labels are short; hover retains full source names. The expense charts explicitly
show magnitudes while the pro forma retains signed deductions.

See the [local Speckle capture](local-speckle.png) and
[capital-chart capture](capital-chart.png). Native Polars output uses the
existing renderer. No custom dataframe HTML was introduced. Iframe paths and their
local JS/data dependencies are retained by the build tool. Browser console checks
reported no errors during the reviewed embedded interactions.

## Build and reproduction

Use [the walkthrough procedure](../../guides/walkthroughs.md). The local viewer's
locked npm build is needed only when changing its source; its generated bundle is
included with the notebook resources. Re-execution regenerates graph and chart
files in `design-output/notebook-02/`.

The strict final build and source hashes are recorded alongside this document.
The build guard still requires matching cell sources, sequential execution counts
and no error outputs. `--preview-chapter` permits candidate review without changing
the accepted TOC. Local HTML output paths are adjusted only in the staged copy.

This acceptance covers the fixed completed-property case. It does not establish
independent Brep recomputation, hosted Speckle version restoration, cross-widget
selection, inverse solving, development funding or later flexibility policies.
