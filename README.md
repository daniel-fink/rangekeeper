<img src="https://github.com/daniel-fink/rangekeeper/blob/v0.2.0/walkthrough/resources/rangekeeper.jpg?raw=true" width="300">

# Rangekeeper
Rangekeeper is a library assisting financial modelling in real estate scenario planning, decision-making, cashflow forecasting, and the like.

It decomposes elements of the Discounted Cash Flow (DCF) Proforma modelling approach into recomposable code functions that can be wired together to form a full model. More elaborate and worked-through examples of these classes and functions can be found in the [walkthrough documentation](https://daniel-fink.github.io/rangekeeper/).

Development of the library follows the rigorous methodology established by Profs Geltner and de Neufville in their book [Flexibility and Real Estate Valuation under Uncertainty: A Practical Guide for Developers](https://doi.org/10.1002/9781119106470).

## Dependencies:

- Python >= 3.9 & < 3.11

- Poetry: <https://python-poetry.org/>, a package manager (although it is possible to roll your own; YMMV)

## Installation

1. Install poetry, if you haven't yet: <https://python-poetry.org/docs/master/#installing-with-the-official-installer>

2. Clone this repo.

3. Use a terminal to install poetry packages from the repo's directory: `<path_to_repo>$ poetry install`

4. Currently, this library is not yet available on Python Package Index (PyPI). If you wish to use this repo with other projects locally, you may install the Rangekeeper library via `<path_to_repo>$ poetry run pip install -e <path_to_rangekeeper_repo>`, replacing `<path_to_rangekeeper_repo>` with its location on your system.
