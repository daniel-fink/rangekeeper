# Rangekeeper walkthrough

The walkthrough teaches the library in seven lessons.
[ADR-020](../../docs/decisions/020-walkthrough-plan-v2.md) gives the plan, and the
[walkthrough guide](../../docs/guides/walkthroughs.md) tells you how to run and
check the lessons.

## Contents

| Path | Contents |
| --- | --- |
| `NN_slug.ipynb` | The lessons, in reading order. Lessons have no outputs in git |
| [`helpers/`](helpers) | Presentation helpers: chart style and charts (`theme`, `chart`, `plot`), graph display (`graph`), local display (`local`), the canonical Speckle envelope (`speckle`) and the geometry viewer (`geometry` and its assets) |
| [`viewer/`](viewer/README.md) | The source and build of the geometry viewer |
| [`resources/`](resources/README.md) | Images that the lessons show, with their rights |
| [`tests/`](tests) | Helper tests, lesson checks and the fresh-kernel run of each lesson |
| [`pyproject.toml`](pyproject.toml), `uv.lock` | The locked walkthrough environment |
| [`../data/mixed_use_property`](../data/mixed_use_property/README.md) | The data package for lessons 02–07 |

| Lesson | Title | Issue |
| --- | --- | --- |
| [01](01_basic_dcf.ipynb) | Basic discounted cash flow | [#203](https://github.com/daniel-fink/rangekeeper/issues/203) |
| [02](02_front_door_back_door.ipynb) | Front door, back door | [#204](https://github.com/daniel-fink/rangekeeper/issues/204) |
| [03](03_cases_debt_equity.ipynb) | Cases, debt and equity | [#205](https://github.com/daniel-fink/rangekeeper/issues/205) |
| [04](04_market_futures.ipynb) | Many market futures | [#206](https://github.com/daniel-fink/rangekeeper/issues/206) |
| [05](05_when_to_commit.ipynb) | When to commit | [#207](https://github.com/daniel-fink/rangekeeper/issues/207) |
| [06](06_project_structure.ipynb) | Project structure | [#208](https://github.com/daniel-fink/rangekeeper/issues/208) |
| [07](07_policies_and_graph.ipynb) | Rules and design options | [#244](https://github.com/daniel-fink/rangekeeper/issues/244) |

The lessons are skeletons until their issues are done.

## Run the lessons

Use Python 3.12 or 3.13. From the repository root:

```sh
uv sync --project examples/walkthrough --locked
uv run --project examples/walkthrough jupyter lab examples/walkthrough
```

The environment installs Rangekeeper and the example builders from this
checkout, not from a published release.

## Rules for lessons

- Name a lesson `NN_slug.ipynb`, with a two-digit number and a lowercase slug.
- Do not commit outputs. The pre-commit hook removes them.
- A lesson must run from a fresh kernel, without the state of an earlier lesson.
- Import `rangekeeper as rk` and the helpers. Helpers load data and show charts,
  graphs and geometry. They do not select financial contributors, supply rates
  or hide an equation (ADR-020, principle 10).
- Helpers write their files to `output/`, which git ignores.
- Read the market path count from `RK_PATH_COUNT` and the design source mode
  from `RK_DESIGN_MODE`. CI sets four paths and `fixture`; use the full count
  locally.

## Test

From the repository root:

```sh
uv run --project examples/walkthrough --locked pytest examples/walkthrough
```

## Convert for the docs site

[`tools/docs/notebooks.py`](../../tools/docs/notebooks.py) converts executed
lessons to Markdown pages for the docs site. Execute the lessons first, then run:

```sh
python tools/docs/notebooks.py _site/walkthrough examples/walkthrough/*.ipynb
```

The tool refuses a lesson with a code cell that did not run or that has an error.
`--allow-unexecuted` turns off the first check, for skeleton lessons.
