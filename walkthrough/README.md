# Rangekeeper Walkthrough
This directory contains a set of Jupyter Notebooks, assembled into a Jupyter Book.

## Development
If you wish to contribute to its development, it is recommended to use [Poetry](https://python-poetry.org/) for environment and dependency management:

### Environment Setup

1. Install poetry, if you haven't yet: <https://python-poetry.org/docs/master/#installing-with-the-official-installer>
2. Clone this repo.
3. Use a terminal to install poetry packages from the repo's directory: `<path_to_repo>$ poetry install`
4. Some notebooks require API access to [Speckle](https://speckle.systems/). It is recommended to use the [Poetry Dotenv Plugin](https://github.com/mpeteuil/poetry-dotenv-plugin) via `poetry self add poetry-dotenv-plugin`, and add a `.env` file in the project's root directory with your `SPECKLE_TOKEN` environment variable.


### Updating Documentation:

1. Make sure the Github Pages is being built with the `gh-pages` branch, from the `/`(root) directory
2. Build via `poetry run jupyter-book build ../walkthrough`
3. Commit any changes to the `main` branch
4. While in the `main` branch, run `poetry run ghp-import -n -p -f _build/html` from this directory