# Rangekeeper
Rangekeeper is a library assisting financial modelling in real estate scenario planning, decision-making, cashflow forecasting, and the like.

It decomposes elements of the Discounted Cash Flow (DCF) Proforma modelling approach into recomposable code functions that can be wired together to form a full model. More elaborate and worked-through examples of these classes and functions will be documented in a forthcoming Jupyter Book to be found in the `/notebooks` directory.

Development of the library follows the rigorous methodology established by Profs Geltner and de Neufville in their book [Flexibility and Real Estate Valuation under Uncertainty: A Practical Guide for Developers](https://doi.org/10.1002/9781119106470)

## Dependencies:

- Python >= 3.9 & < 3.11

- Poetry: <https://python-poetry.org/>, a package manager (although it is possible to roll your own; YMMV)

## Installation

1. Install poetry, if you haven't yet: <https://python-poetry.org/docs/master/#installing-with-the-official-installer>

2. Clone this repo.

3. Use a terminal to install poetry packages from the repo's directory: `<path_to_repo>$ poetry install`
