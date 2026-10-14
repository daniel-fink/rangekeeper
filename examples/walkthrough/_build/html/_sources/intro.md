# Rangekeeper

These notebooks introduce immutable Model records, explicit cashflow calculations,
scenario generation and policy comparisons. They also show how reviewed design
content becomes a canonical Model and a financial investigation.

The numerical examples follow David Geltner and Richard de Neufville's
[Flexibility and Real Estate Valuation under Uncertainty](https://doi.org/10.1002/9781119106470).
They assume familiarity with its valuation concepts and Python.

Use the source checkout and optional dependencies listed in the walkthrough README.
The current notebooks use the pre-1.0 canonical API; a plain installation of the
published PyPI package may not supply that API. Tables use Polars. Canonical
records retain their units and provenance independently of display tables.

The five numerical notebooks include a visible routine count of four scenarios.
`RK_SCENARIO_COUNT=2000` selects the larger study. The two design notebooks use an
explicit local fixture by default. Live receive requires separate configuration;
there is no automatic fallback or service publication.

## Table of Contents
```{tableofcontents}
```

## Acknowledgements
For Andrea, who keeps reminding me it is possible.

## Bibliography
```{bibliography}
```