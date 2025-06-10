# Rangekeeper Source
This directory holds the source code for the Rangekeeper Library

## Installation
The library is offered through PyPI, and so its installation in other projects can be performed by:
`pip install rangekeeper`, `poetry add rangekeeper`, or `uv add rangekeeper`, depending on your virtual environment manager.

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

### Publishing
1. First, remove any previously built packages: `rm -rf dist/`
2. Build the package: `uv build`
3. Then, publish it to PyPI with your `UV_PUBLISH_TOKEN` recorded in the .env file: `export $(grep -v '^#' .env | xargs) && uv publish --token $UV_PUBLISH_TOKEN`
