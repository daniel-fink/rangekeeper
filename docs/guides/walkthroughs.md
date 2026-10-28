# Run the walkthroughs

## Branches and publication

The walkthrough lives on `develop` under
[`examples/walkthrough`](../../examples/walkthrough/README.md):

- the lessons `NN_slug.ipynb`;
- the presentation helpers;
- the resources;
- the locked environment and the tests.

The lessons use the data package
[`examples/data/mixed_use_property`](../../examples/data/mixed_use_property/README.md).
[Walkthrough plan v2](../decisions/020-walkthrough-plan-v2.md) defines the seven
lessons. Each lesson stays a skeleton until its issue is done.

The interim draft book stays on
[`codex/walkthrough-acausal`](https://github.com/daniel-fink/rangekeeper/tree/codex/walkthrough-acausal/examples/walkthrough)
as source material. It uses the API of its date and the retired Jupyter Book 2
build. `develop` keeps the original 2022 notebooks in `walkthrough/` as historical
teaching material until their replacements are accepted
([ADR-019](../decisions/019-walkthrough-direction.md)). They do not work with the
current library.

GitHub Pages serves the published book from `gh-pages`. Code and lesson merges do
not publish the book; publication is a separate, explicit action. Contributors
follow the [walkthrough branch procedure](../contributing/walkthrough-branch.md).

## Explore the lessons

The locked walkthrough environment needs Python 3.12 or 3.13. From the repository
root:

```sh
uv sync --project examples/walkthrough --locked
uv run --project examples/walkthrough jupyter lab examples/walkthrough
```

The environment installs Rangekeeper from `../..` and the example builders from
`..`, as editable packages. These paths prevent the environment from silently
selecting an older published API.

## Execute for acceptance

Each lesson must run from top to bottom in a fresh kernel. From the repository
root, with the walkthrough environment:

```sh
uv run --project examples/walkthrough --locked pytest examples/walkthrough
```

The tests check the helpers, the lesson names and the conversion. They run each
lesson in a new kernel, then convert it for the docs site. The `walkthrough` CI job
runs the same tests with `RK_DESIGN_MODE=fixture` and `RK_PATH_COUNT=4`. Inspect
the tables, figures and expected financial results of each executed lesson. Helpers
write their HTML to `examples/walkthrough/output/`, which git ignores.

## Convert for the docs site

The docs site uses Zensical ([ADR-018](../decisions/018-release-and-engineering.md)).
Zensical renders Markdown, so
[`tools/docs/notebooks.py`](../../tools/docs/notebooks.py) converts executed
lessons to Markdown pages:

```sh
python tools/docs/notebooks.py /tmp/rk-site/walkthrough /tmp/rk-executed/*.ipynb
```

The first argument is the output folder. The tool writes one page for each
lesson, the output images and the local files that the lesson links to. It needs
only Python's standard library. It refuses a lesson name that is not
`NN_slug.ipynb`, a code cell without an execution count and an error output.
`--allow-unexecuted` turns off the execution check, for skeleton lessons. Cell
tags control the page:

| Tag | Effect |
| --- | --- |
| `remove-cell` | Leave out the cell |
| `remove-input` | Show only the outputs |
| `remove-output` | Show only the source |
| `solution` | Put the source and outputs in a collapsed "Solution" block |

HTML outputs, for example native Polars tables and Plotly figures, stay as HTML
in a `rk-output` block. The [docs site build](../contributing/README.md#docs-site)
runs each lesson and converts it in the same way; its preview shows the lessons
with their outputs.

## Design example conventions

[`rangekeeper_examples.design`](../../examples/rangekeeper_examples/design.py)
provides `author`, `formulate` and `specify`. They construct a Model, finite
mathematical declarations and a Specification. Construction does not execute or
store them. Ambiguous use interpretation and missing required geometry quantities
fail; the builder does not guess them.

The two legacy design notebooks use the maintained
[`rangekeeper_examples.design`](../../examples/rangekeeper_examples/design.py)
builder. It authors explicit AUD flows, with signed floor and facade operating
expenses. Capital payments occur on 2005-12-31 and 2010-12-31, with growth
exponents zero and one over those five-year intervals.

Reversion is 2011 net after-capital cashflow (NACF) divided by the capitalization
rate, received at the 2010 sale. It does not capitalize net operating income (NOI).
Contributor IDs are deduplicated before aggregation. Parent totals are not added
to their constituent values. These conventions belong to this reviewed example;
the design envelope helper does not impose financial equations.

## Shared chart style

Numerical charts use Plotly. The chart functions return editable Plotly `Figure`
objects and do not set a global theme. In
[`helpers/plot.py`](../../examples/walkthrough/helpers/plot.py), use
`show_flows(flows=..., title=..., timing=...)` for the common flow chart, or
`show_plot(figure, path=...)` for any other Plotly figure. Both return an iframe;
leave the call as the final expression in a cell or pass it to `display()`.
Assignment alone does not display the chart.

[`helpers/theme.py`](../../examples/walkthrough/helpers/theme.py) defines the
shared `plotly_white`/`plotly_dark` styles, fonts, controls and colour palettes.
Use colours stay the same across the hierarchy charts. Package colours stay the
same in the development timeline. `show_timeline()` displays supplied dates;
`show_equations()` derives its edges from the actual equations and lets the reader
switch Specification roles without changing the relationships. Line charts also
use different dashes and markers. Helpers apply the style to a copy of the Figure.

The local HTML embeds share a Plotly bundle in their output folder. A small
[`theme.js`](../../examples/walkthrough/helpers/theme.js) bridge follows the
same-origin page or JupyterLab theme; standalone and cross-origin views use the
operating system's colour preference. Theme changes update layout without
changing numerical values, use colours, zoom or drill-down. To style a Figure for
direct notebook display or a fixed export, call `apply_theme(figure, mode="light")`
or `apply_theme(figure, mode="dark")` from `helpers.theme`.

`show_geometry(view)` writes the local geometry viewer for the data package and
shows one view: `context`, `property`, `floors` or `utilities`. The viewer checks
the data package hashes before it displays the geometry. Its
[build procedure](../../examples/walkthrough/viewer/README.md) keeps the viewer bundle local.

See [examples](examples.md), [upgrading](upgrading.md) and
[verification](../contributing/verification.md) for related procedures.

## Live notebook display

The helpers start `helpers.local.LocalDisplay` for the folder that holds the
displayed file. It serves read-only files on loopback with a random URL prefix
and no directory listing. It stops when the kernel closes. This avoids
JupyterLab's file-URL query rewriting and HTML sandbox restrictions. The saved
notebook's display links work while its kernel runs; execute the cells again
after a restart.
