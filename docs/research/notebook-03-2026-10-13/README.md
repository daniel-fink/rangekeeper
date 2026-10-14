# Notebook 03 acceptance — 13 October 2026

[A development plan and its financial limits](../../../examples/walkthrough/development_feasibility.ipynb)
continues the same mixed-use property through a fixed development plan, SFFA
forward/inverse investigations and a construction funding test. It has eight
sections, 53 cells and 27 executable cells. The library API is unchanged.

## Inputs and calculations

The pinned source retains its 50 physical objects, relationship identities and
recorded Values. Construction covers 33 distinct floors; renewal expenditure
covers those floors and three utilities. The new
[development inputs](../../../examples/walkthrough/data/mixed_use_property/development.json)
are explicit teaching assumptions. They do not change the source manifest or
claim to be current market estimates. The
[project brief](../../guides/mixed-use-project.md#notebook-03-development-assumptions)
records the timing, cost, opening, renewal, terminal-value and funding conventions.

The six passive equations keep the same references for both investigations.
The front-door Specification fixes land cost and solves the rent factor; the
back-door Specification fixes that factor and solves land cost. The round-trip
check recovers the original land cost. All investigations pin the same Model
revision; execution writes new solved revisions and leaves the source unchanged.

| Result | Verified value |
| --- | ---: |
| Required rent factor | 0.92281422 |
| SFFA supportable land | AUD 40,103,550.83 |
| Unlevered development NPV | AUD 59,406,413.73 |
| Peak construction cash shortfall | AUD 9,693,529.19 |
| Commitment funding gap at Building B start | AUD 20,635,772.25 |

At Building B's start, the first payment of AUD 19.73 million fits within cash
plus undrawn committed funding of AUD 22.83 million. The full remaining
commitment, including finance charges, is AUD 43.47 million. Forecast operating
receipts enter the cash forecast but do not count as secured commitment funding.
The notebook explains why value, loan support and payment capacity differ.

Actual executor outcomes also distinguish three cases: both land and rent
unknown returns a feasible, underdetermined candidate; an incompatible fixed
pair is infeasible; an unknown leverage × cost product is unsupported and fails
without assessing feasibility. See the [execution report](execution.json).

## Fresh execution and independent checks

All three accepted notebooks ran in separate fresh Python 3.12.12 kernels using
the installed Rangekeeper 0.8.71 candidate wheel. The final wheel was built from a clean copy of tracked package files. An initial
check found an obsolete module and sync-conflict files in the reused wheel, so it
was replaced and all three notebooks were re-executed. All 226 packaged Python
files in the clean wheel match the checkout; it contains no obsolete `flow.py`
or sync-conflict files. [Source hashes](source-hashes.json) record the
wheel and chapter/helper sources. The environment has Plotly 6.5.0, Polars 1.44.2,
nbclient 0.10.2 and Jupyter Book 2.1.7.

- [Execution log](execution.txt): all three notebooks completed without cell errors.
- [Independent audit](audit.py): appended temporarily to Notebook 03's fresh
  kernel, then removed from the saved teaching notebook. It computes each annual
  amount independently from the CSV inventory, checks land at time zero, terminal
  cash flow, NPV, closed-form SFFA results, funding and preserved physical content.
- [Notebook 02 regression](notebook-02-regression.json): the completed-property
  calculation audit still passes. Its saved source outputs remain unchanged;
  generated Plotly HTML receives the shared menu-style update.
- [Nine plotting/helper tests](chart-tests.txt): all pass. Black and JavaScript
  syntax checks pass for the presentation helpers.
- [Strict book build](book-build.txt): four pages, comprising the introduction and
  three chapters. Existing large-image conversion and Node deprecation warnings
  remain; neither prevents the build. Chapter and helper source checks pass.

The saved chapter includes native Polars tables, one local Speckle viewer and
four Plotly embeds. Canonical Model, Specification and Run exports, plus the base
plan and result tables, live under a Model-revision folder in
`examples/walkthrough/design-output/notebook-03/records/`. Re-execution creates
a new revision folder rather than overwriting immutable records.

## Rendered review

The local book was reviewed at normal and 390-pixel widths. Native tables remain
scrollable. The geometry loads from the pinned local archive. Timeline dates,
annual cash flows, funding balances and all relation labels are visible. The
relation selector changes fixed/unknown roles while preserving edges; changing
the book theme preserves the selected investigation. A fresh tab of the final book reports no browser warnings or errors and
contains 13 tables and five embeds. [Final book view](final-book.png).

- [Source-backed geometry](geometry.png)
- [Construction timeline](base-plan.png)
- [Inverse roles in light mode](light-inverse.png) and [dark mode](dark-inverse.png)
- [Funding chart](funding.png)
- [Narrow relation diagram](narrow-relations.png) and [funding chart](narrow-funding.png)
- [Standalone notebook HTML preview](notebook-preview.png)

Visual review caught clipped variable labels and Plotly's pale active-menu
highlight in dark mode. The helpers now keep labels outside the plot area visible
and style menu states for the host theme. Financial calculations remain in the
notebook; the new timeline and relation helpers only prepare presentation.

The standalone HTML preview renders its tables and charts. It reports the same
unattributed `MutationObserver.observe` error seen in earlier notebook previews;
the source of that error remains unconfirmed. It also recurred when reusing
that preview tab for book navigation. A separate fresh book tab reported no
errors; no visible failure of the charts, tables or geometry was observed.
Live JupyterLab theme switching and cross-origin embeds were not separately tested.

## Scope

This is local acceptance, not GitHub Pages publication. The fixed funding test
ends before permanent refinancing in 2032; it does not calculate subsequent
principal repayment or equity IRR. Annual cash timing does not prove liquidity
within a year. Sequential decisions, alternative designs and market uncertainty
remain work for notebooks 04–06 under the agreed curriculum.
