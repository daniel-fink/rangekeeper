# Run the walkthroughs

The seven notebook sources under
[`examples/walkthrough/`](../../examples/walkthrough) use canonical Models. Their
shared builders live in `examples/rangekeeper_examples/`. Install both from the
same checkout. Live design receive also needs the `speckle` extra; fixture mode
needs no service SDK.

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

The five numerical notebooks expose `RK_SCENARIO_COUNT`. Use four scenarios for
routine acceptance, or `RK_SCENARIO_COUNT=2000` for the retained full comparison.
The two design notebooks default to `RK_DESIGN_MODE=fixture`. Live mode needs
configured credentials and an explicit source pin; canonical mode needs a named
envelope file and interpretation. A failed live read does not switch to fixture
mode. The notebooks do not publish.

## Execute for acceptance

Use the candidate wheel and matching example package in a separate environment,
with the `calculations`, `execution`, `visualization` and `workflow` extras
plus `nbclient`, `nbformat`, `nbconvert` and `ipykernel`. Record the wheel hash and
interpreter. A fresh kernel must execute each notebook from top to bottom.

Copy the authored notebooks and resources into a new execution directory so their
relative resources and generated `design-output/` files stay together. From the
repository root, with the candidate-wheel environment active:

```sh
mkdir /tmp/rk-notebooks-001
cp examples/walkthrough/*.ipynb /tmp/rk-notebooks-001/
cp -R examples/walkthrough/resources /tmp/rk-notebooks-001/resources
cp -R examples/walkthrough/_static /tmp/rk-notebooks-001/_static
cd /tmp/rk-notebooks-001
MPLBACKEND=Agg RK_SCENARIO_COUNT=4 RK_DESIGN_MODE=fixture python -m nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=6000 *.ipynb
```

Use a registered kernel for that environment, or supply its name through
`--ExecutePreprocessor.kernel_name`. Do not assume that a notebook's saved kernel
name selects the candidate-wheel environment. Inspect execution errors, tables,
figures, mode declarations and expected financial results. Preserve the outputs
with the acceptance result.

## Design example conventions

The two design notebooks use the maintained
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

Build from the freshly executed notebook directory. The build tool stages the
current book configuration, resources and supplied notebooks; it does not reuse
the Jupyter cache or execute the notebooks again. Use the Jupyter Book and Plotly
versions in `examples/walkthrough/uv.lock`.

From the repository root, with that book environment active:

```sh
plotly_asset=$(python -c 'from pathlib import Path; import plotly; print(Path(plotly.__file__).parent / "package_data" / "plotly.min.js")')
python tools/docs/build_book.py /tmp/rk-book-001 /tmp/rk-notebooks-001 "$plotly_asset"
```

The first argument is a new staging directory. The second contains all seven
executed notebooks and their generated design artifacts. The third is Plotly's
local JavaScript asset. The built site is `/tmp/rk-book-001/_build/html/`.

The static build disables the unused Sphinx-Thebe extension to avoid duplicate
JavaScript declarations. Colab launch links remain available. Inspect navigation,
resource links, citations, tables and figures in the built site. A local rebuild
does not publish GitHub Pages; publication is a separate action.

See [examples](examples.md), [upgrading](upgrading.md) and
[verification](../contributing/verification.md) for related procedures.
