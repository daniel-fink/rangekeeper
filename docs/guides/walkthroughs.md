# Run the walkthroughs

The notebook sources live under
[`examples/walkthrough/`](../../examples/walkthrough). The first,
[`basic_dcf.ipynb`](../../examples/walkthrough/basic_dcf.ipynb), introduces Flow,
Span, projection and Stream calculations before Model authoring. Its current
Flux/Stream migration has [execution and rendered acceptance](../research/basic-dcf-2026-10-08/README.md).
The subsequent [native Polars display acceptance](../research/native-polars-display-2026-10-08/README.md)
records the native renderer and refreshed notebook outputs.
The [Jupyter Book 2 acceptance](../research/jupyter-book-2-2026-10-08/README.md)
records the local book migration for the introduction and first chapter.
[Notebook 02](../../examples/walkthrough/design_to_value.ipynb) now joins the
accepted book with the complete mixed-use source, local Speckle geometry inspection,
PyVis graphs and Plotly partition charts. Its
[initial execution and visual evidence](../research/notebook-02-2026-10-12/README.md) records
the verification scope. The [condensed chapter acceptance](../research/notebook-02-2026-10-13/README.md)
records the eight-section revision and presentation helpers. The six legacy sources remain teaching references; their
stored outputs do not establish current API acceptance.
The [Plotly style acceptance](../research/plotly-walkthrough-2026-10-13/README.md)
records the shared chart theme, updated adapters and light/dark book review.
[Notebook 03](../../examples/walkthrough/development_feasibility.ipynb) adds a fixed
development plan, SFFA forward/inverse solving and construction funding checks.
Its [acceptance record](../research/notebook-03-2026-10-13/README.md) includes
independent cash-flow arithmetic, actual solver diagnostics and rendered charts.

The [agreed walkthrough curriculum](../decisions/006-walkthrough-curriculum.md)
retains notebook 01 and consolidates the other six sources into five further
lessons. It records the teaching objectives, continuing property example, source
references, open assumptions and library capability dependencies. Notebooks
04–06 remain planned; the book configuration below remains the chapter acceptance
list.

For notebook 02 preparation, use the [detailed outline](../decisions/006-notebook-02-outline.md)
and [mixed-use project brief](mixed-use-project.md). The complete legacy source
package is captured and reconciled. Notebook and viewer acceptance are recorded
separately in the evidence linked above.

Shared builders live in `examples/rangekeeper_examples/`. Install both packages
from the same checkout. Live design receive also needs the `speckle` extra;
fixture mode needs no service SDK.

## Explore the notebooks

The locked walkthrough environment requires Python 3.12–3.13. From
`examples/walkthrough/`:

```sh
uv sync --locked
uv run jupyter lab
```

The lockfile resolves Rangekeeper from `../..` and the example builders from
`..`. Polars is the dataframe dependency. These paths prevent the environment
from silently selecting an older published API.

The four later numerical notebooks expose `RK_SCENARIO_COUNT`. Use four scenarios for
routine acceptance, or `RK_SCENARIO_COUNT=2000` for the retained full comparison.
The first notebook has one fixed DCF example and does not use a scenario count.
The two legacy design notebooks default to `RK_DESIGN_MODE=fixture`. Live mode needs
configured credentials and an explicit source pin; canonical mode needs a named
envelope file and interpretation. A failed live read does not switch to fixture
mode. The notebooks do not publish.

## Execute for acceptance

Use the candidate wheel and matching example package in a separate environment,
with the `calculations`, `execution`, `visualization` and `workflow` extras
plus `nbclient`, `nbformat`, `nbconvert` and `ipykernel`. Record the wheel hash and
interpreter. A fresh kernel must execute each notebook from top to bottom.

Copy the accepted notebooks and resources into a new execution directory so their
relative resources and generated `design-output/` files stay together. From the
repository root, with the candidate-wheel environment active:

```sh
mkdir /tmp/rk-notebooks-001
cp examples/walkthrough/basic_dcf.ipynb examples/walkthrough/design_to_value.ipynb examples/walkthrough/development_feasibility.ipynb /tmp/rk-notebooks-001/
cp -R examples/walkthrough/data /tmp/rk-notebooks-001/data
cp -R examples/walkthrough/resources /tmp/rk-notebooks-001/resources
cp -R examples/walkthrough/_static /tmp/rk-notebooks-001/_static
cp -R examples/walkthrough/helpers /tmp/rk-notebooks-001/helpers
cd /tmp/rk-notebooks-001
MPLBACKEND=Agg RK_SCENARIO_COUNT=4 RK_DESIGN_MODE=fixture python -m nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=6000 basic_dcf.ipynb design_to_value.ipynb development_feasibility.ipynb
```

Use a registered kernel for that environment, or supply its name through
`--ExecutePreprocessor.kernel_name`. Do not assume that a notebook's saved kernel
name selects the candidate-wheel environment. Inspect execution errors, tables,
figures, mode declarations and expected financial results. Preserve the outputs
with the acceptance result.

Execute `basic_dcf.ipynb`, `design_to_value.ipynb` and
`development_feasibility.ipynb` by name instead of using `*.ipynb`. Expand
acceptance to later chapters after their migration.

## Design example conventions

The two legacy design notebooks use the maintained
[`rangekeeper_examples.design`](../../examples/rangekeeper_examples/design.py)
builder. It authors explicit AUD flows, with signed floor and facade operating
expenses. Capital payments occur on 2005-12-31 and 2010-12-31, with growth
exponents zero and one over those five-year intervals.

Reversion is 2011 net after-capital cashflow (NACF) divided by the capitalization
rate, received at the 2010 sale. It does not capitalize net operating income (NOI).
Contributor IDs are deduplicated before aggregation. Parent totals are not added
to their constituent values. These conventions belong to this reviewed example;
the transport adapter does not impose financial equations.

## Build the site

The local book uses Jupyter Book 2. The locked walkthrough environment supplies
its CLI; Node.js is also required. The first build downloads the standard MyST
book theme and web dependencies. The current acceptance used Node.js 24.

[`myst.yml`](../../examples/walkthrough/myst.yml) is the single book configuration
and chapter acceptance list. It currently includes the introduction,
`basic_dcf.ipynb`, `design_to_value.ipynb` and `development_feasibility.ipynb`.
Add a later chapter only after updating its code and teaching content, executing
it in a fresh kernel and reviewing its rendered output.
The other six sources and the historical tracked v1 site remain available.

Build from the freshly executed notebook directory. With the locked book
environment active, run from the repository root:

```sh
python tools/docs/build_book.py /tmp/rk-book-001 /tmp/rk-notebooks-001
```

The first argument must be a new staging directory. The second contains the
executed notebooks listed in `myst.yml`. The tool rejects missing notebooks,
changed cell sources, missing or changed helper sources, incomplete execution counts
and error outputs. These checks
do not replace the required fresh-kernel execution. It copies only the accepted
chapters, shared assets and any supplied design artifacts, then builds static HTML
with `jupyter-book build --html --strict`. It does not execute or publish.

Serve the result on the local computer:

```sh
python -m http.server 8769 --bind 127.0.0.1 --directory /tmp/rk-book-001/_build/html
```

Open <http://127.0.0.1:8769/> or the first chapter at
<http://127.0.0.1:8769/basic-dcf/>. Keep the server running while reviewing it.
Use a new staging directory for each acceptance build, then restart the local
server against that output. Inspect navigation, source downloads, citations,
figures, collapsed outputs and tables in the browser.

The reference image uses a standard Markdown image inside a MyST figure block.
Ordinary notebook viewers can show the image and attribution; they may also show
the directive markers and citation syntax. The book renders the figure and
bibliography. Native Polars HTML remains unchanged. A small book stylesheet
prevents table labels from wrapping and lets wide tables scroll horizontally.

The v1 Sphinx pipeline has been removed. Presentation helpers live in
[`helpers/plot.py`](../../examples/walkthrough/helpers/plot.py). They wrap the
Rangekeeper Plotly adapters; financial selection and calculations remain in the
notebook. Copy `helpers/` with the notebooks when executing in a separate directory.
The build compares all helper sources, including JavaScript, with the executed copy and includes them in
the staged and served book. Notebook 02 writes interactive figures to
`design-output/notebook-02/`. Notebook 03 writes its figures, result tables and
canonical records to `design-output/notebook-03/`; each run uses a new Model
revision directory for immutable record exports. The build copies those artifacts,
the source `data/` and geometry resources into the static site. It adjusts local output iframe paths
only in the staged notebook; authored code and native Polars HTML remain unchanged.
The source notebook keeps its executed outputs and generated figures for local
inspection without a kernel. Re-execution recreates the graph and chart files.

### Shared chart style

Numerical charts use Plotly. The library adapters return editable Plotly `Figure`
objects and do not set a global theme. Use `show_flows(flows=..., title=...,
timing=...)` for the common flow chart, or `show_plot(figure, path=...)` for any
other Plotly figure. Both return an iframe; leave the call as the final expression
in a cell or pass it to `display()`. Assignment alone does not display the chart.

[`helpers/theme.py`](../../examples/walkthrough/helpers/theme.py) defines the
shared `plotly_white`/`plotly_dark` styles, fonts, controls and colour palettes.
Use colours remain fixed across the hierarchy charts. Package colours remain
fixed in the development timeline. `show_timeline()` displays supplied dates;
`show_relations()` derives its edges from the actual equations and lets the reader
switch Specification roles without changing the relationships. Line charts also use
different dashes and markers. Helpers apply the style to a copy of the Figure.

The local HTML embeds share a Plotly bundle in their output directory. A small
[`theme.js`](../../examples/walkthrough/helpers/theme.js) bridge follows the
same-origin book or JupyterLab theme; standalone and cross-origin views use the
operating system's colour preference. The book's font and background carry into
the charts. Theme changes update layout without changing numerical values,
use colours, zoom or drill-down. Native MyST Plotly output remains available for
plain Figures, but its current renderer does not follow the book colour switch.
These helpers therefore retain local HTML embeds for consistent book display.

To style a Figure for direct notebook display or a fixed export, call
`apply_theme(figure, mode="light")` or `apply_theme(figure, mode="dark")` from
`helpers.theme`. The book display helpers select the mode in the browser.

To review a candidate without adding it to the accepted TOC, pass
`--preview-chapter candidate.ipynb` to `build_book.py`. It applies the same source,
execution-count and error checks. Add the source to `myst.yml` only after review.

The local geometry view uses the official Speckle SDK with pinned in-memory source
records. Its [small host and build procedure](https://github.com/daniel-fink/whirlwind-interface/blob/5ef206aa3a525a0f4c1910512b6fa2c8b1e6f145/local/geometry/README.md)
keep the viewer bundle local. The chapter uses interactive geometry without repeated
static mesh images. `tools/docs/render_property.py` remains available to recreate
the reference images. Graph, chart and geometry selections are independent. The original
hosted model currently reports an expired version; it is not the runtime source.
 Public publication, old-URL redirects, repository launch
links and complete-book acceptance are deferred. This procedure serves only
localhost and does not update GitHub Pages.

See [examples](examples.md), [upgrading](upgrading.md) and
[verification](../contributing/verification.md) for related procedures.

## Live notebook display

The walkthrough helpers start `visualisation.local.LocalDisplay` for the explicit working
directory. It serves read-only files on loopback with a random URL prefix and no directory
listing. It stops when the kernel closes. This avoids JupyterLab's file-URL query rewriting
and HTML sandbox restrictions. The saved notebook's display links work while its kernel
runs; execute the cells again after restarting it. The book builder converts only these
local resource/output URLs to relative links, so the published book needs no Python server.
