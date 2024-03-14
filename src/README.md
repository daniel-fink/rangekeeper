# Rangekeeper Source
This directory holds the source code for the Rangekeeper Library

## Installation
The library is offered through PyPI, and so its installation in other projects can be performed by:
`pip install rangekeeper` or `poetry add rangekeeper`

## Development
If you wish to contribute to its development, it is recommended to use [Poetry](https://python-poetry.org/) for environment and dependency management:

### Environment Setup

1. Install poetry, if you haven't yet: <https://python-poetry.org/docs/master/#installing-with-the-official-installer>
2. Clone this repo.
3. Use a terminal to install poetry packages from the repo's directory: `<path_to_repo>$ poetry install`
4. If you wish to develop this repo alongside other projects locally, you may install the local Rangekeeper library via `<path_to_repo>$ poetry run pip install -e <path_to_rangekeeper_repo>`,
replacing `<path_to_rangekeeper_repo>` with its location on your system.
5. Some tests require API access to [Speckle](https://speckle.systems/). It is recommended to use the [Poetry Dotenv Plugin](https://github.com/mpeteuil/poetry-dotenv-plugin) via `poetry self add poetry-dotenv-plugin`, and add a `.env` file in the project's root directory with your `SPECKLE_TOKEN` environment variable.
