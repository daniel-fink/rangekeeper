# Rangekeeper Source
This directory holds the source code for the Rangekeeper Library

## Installation
The library is offered through PyPI, and so its installation in other projects can be performed by:
`pip install rangekeeper`, `poetry add rangekeeper`, or `uv add rangekeeper`, depending on your virtual environment manager.

## Current branch domain core

This checkout exposes `rangekeeper.Model`, `Specification`, and `Run`, with JSON/YAML
codecs and append-only memory/filesystem stores. See the [Run and storage guide](../docs/RUN_AND_STORAGE.md)
for a complete example. These branch changes have not been released to PyPI.
Install this checkout with `pip install .`; use `pip install '.[yaml]'` for YAML IO.
Graph/numerical APIs remain available, and their existing dependency metadata remains.
Core imports do not initialize graph, plotting, service or solver integrations.
No new-schema executor has produced authentic outputs yet.

## Development
If you wish to contribute to its development, it is recommended to use [uv](https://docs.astral.sh/uv/) for 
environment and dependency management:

### Environment Setup

1. Install uv, if you haven't yet: <https://docs.astral.sh/uv/>
2. Clone this repo.
3. Create a virtual environment: `uv venv .venv`
4. Activate the virtual environment: `source .venv/bin/activate`
5. Install dependencies: `uv pip install -r <(uv pip compile pyproject.toml)`
6. Some tests require API access to [Speckle](https://speckle.systems/). It is recommended to use [Python-Dotenv](https://github.com/theskumar/python-dotenv), and add a `.env` file in the project's root directory with your `SPECKLE_TOKEN` environment variable.

### Testing

Run the test suite without opening Matplotlib windows:

```bash
uv run pytest
```

To inspect plots interactively, including from a PyCharm pytest run configuration, add the `--show-plots` option:

```bash
uv run pytest --show-plots
```

### Publishing
1. First, remove any previously built packages: `rm -rf dist/`
2. Build the package: `uv build`
3. Then, publish it to PyPI with your `UV_PUBLISH_TOKEN` recorded in the .env file: `export $(grep -v '^#' .env | xargs) && uv publish --token $UV_PUBLISH_TOKEN`


## Typed graph persistence and YAML workflows

The optional `workflow` extra provides a bounded source-to-graph executor, strict
YAML specifications and an explicit export CLI. Graph JSON supports reloadable
canonical provenance. See [the API and schema guide](../docs/GRAPH_YAML_WORKFLOW.md)
and [synthetic examples](examples/workflow/README.md).

For ownership and API rationale, see [the adapter guide](../docs/GRAPH_ADAPTER_GUIDE.md)
and [the ingestion/workflow boundary review](../docs/GRAPH_ADAPTER_REVIEW.md).
