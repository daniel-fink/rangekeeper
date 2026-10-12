# Plotly walkthrough style — 13 October 2026

The numerical adapters now return Plotly Figures. Notebook 02 uses a shared
light/dark style for its income chart and four sunbursts. The source Model,
financial assumptions, illustrations, Speckle viewers and PyVis graphs retain
their previous roles.

## Implementation

- `rangekeeper.adapters.plotting` retains resolved-value, date, unit and finite
  sample checks. Mixed units use separate panels. No global Plotly theme changes.
- [`helpers/theme.py`](../../../examples/walkthrough/helpers/theme.py) extends
  `plotly_white` and `plotly_dark`, with common typography and stable use colours.
  Line dashes and marker shapes provide another way to distinguish series.
- [`helpers/plot.py`](../../../examples/walkthrough/helpers/plot.py) adds
  `show_plot()` and `show_flows()`. Exports use a copy of the supplied Figure and
  one local Plotly bundle per output directory. Annual ticks label the actual
  receipt years, including the first and last observations.
- [`helpers/theme.js`](../../../examples/walkthrough/helpers/theme.js) reads the
  same-origin host theme and updates chart layout. It wraps plain-text titles,
  adjusts widths and sunburst heights, and preserves chart selections.
  Standalone or cross-origin views use the OS colour preference.
- The MyST renderer supports native Plotly MIME output but does not track the
  book theme. Local HTML embeds therefore remain the walkthrough display path.
- Older notebook plotting calls have minimal compatibility edits for Plotly
  display/export. Their full current-code migration and execution remain pending.

## Verification

Both accepted notebooks ran in fresh Python 3.12.12 kernels against a new
Rangekeeper 0.8.71 candidate wheel. [Execution results](execution.json) include
the independent CSV calculation audit. [Source hashes](source-hashes.json)
record the wheel and reviewed sources; the wheel's plotting module matches the
checkout. Notebook 02 retains 28 code cells and now has five Plotly embeds.

The reference asset value remains AUD 209,491,758.70; the residential-rent
sensitivity remains AUD 225,427,188.08. All four sunbursts retain 50 unique UUIDs
and their verified totals. The source Model is unchanged.

[Nine plotting/helper tests](chart-tests.txt) pass. The earlier combined run
also passed all 35 Flux/Stream checks; see [targeted tests](targeted-tests.txt).
Checks cover signed magnitudes, mixed units, explicit period timing, unknown
values, empirical probabilities, scenario pairing, Figure ownership and annual
date labels. Black, JavaScript syntax and documentation-link checks pass.
The [strict book build](book-build.txt) accepts all three pages. Missing or stale
JavaScript helper copies are rejected before staging ([guard checks](helper-guards.json)).

## Rendered review

The book was inspected in light and dark modes at normal and 390-pixel viewport
widths. All five charts render locally. Review covered receipt-year labels,
title wrapping, legend visibility, sunburst drill-down and hover details.
Switching themes preserves the selected branch and hidden income series. No
browser warnings or errors were reported during this book review.

- [Light income chart](light-income.png)
- [Dark sunburst after drill-down](dark-sunburst.png)
- [Narrow income chart](narrow-income.png)
- [Narrow sunburst with wrapped title](narrow-sunburst.png)

The saved notebook's HTML preview was also inspected. It reports the same
unattributed `MutationObserver.observe` error recorded in the
[earlier preview review](../notebook-02-2026-10-13/README.md); its origin remains
unconfirmed. Charts and tables render, and the book reports no such error.
Live JupyterLab theme switching and cross-origin iframe behaviour were not separately tested.
This acceptance is local; it does not publish to GitHub Pages.
