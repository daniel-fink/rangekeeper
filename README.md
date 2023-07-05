<img src="https://github.com/daniel-fink/rangekeeper/blob/v0.2.0/walkthrough/resources/rangekeeper.jpg?raw=true" width="300">

# Rangekeeper
Rangekeeper is an open-source library for financial modelling in real estate 
asset & development planning, decision-making, cashflow forecasting, and 
scenario analysis.

Rangekeeper enables real estate valuation at all stages and resolutions of 
description — from early-stage ‘back-of-the-envelope’ models to detailed 
commercial assessments, and can be completely synchronised with 3D design, 
engineering, and logistics modelling.

It decomposes elements of the Discounted Cash Flow (DCF) Proforma modelling 
approach into recomposable code functions that can be wired together to form a 
full model. More elaborate and worked-through examples of these classes and 
functions can be found in the [walkthrough documentation](https://daniel-fink.github.io/rangekeeper/).

Development of the library follows the rigorous methodology established by 
Profs Geltner and de Neufville in their book [Flexibility and Real Estate Valuation under Uncertainty: A Practical Guide for Developers](https://doi.org/10.1002/9781119106470).


## Installation
`pip install rangekeeper` or `poetry add rangekeeper`


## Development

### Dependencies

- Python >= 3.9 & < 3.11

- Poetry: <https://python-poetry.org/>, a package manager (although it is 
possible to roll your own; YMMV)

### Environment Setup

1. Install poetry, if you haven't yet: <https://python-poetry.org/docs/master/#installing-with-the-official-installer>

2. Clone this repo.

3. Use a terminal to install poetry packages from the repo's directory: `<path_to_repo>$ poetry install`

4. If you wish to develop this repo alongside other projects locally, you may 
install the local Rangekeeper library via `<path_to_repo>$ poetry run pip install -e <path_to_rangekeeper_repo>`,
replacing `<path_to_rangekeeper_repo>` with its location on your system.
