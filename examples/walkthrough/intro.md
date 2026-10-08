# Rangekeeper

These notebooks start with Flow, Span and Stream calculations, then introduce
immutable Model records, scenario generation and policy comparisons. They also
show how reviewed design content becomes a canonical Model and a financial
investigation.

The numerical examples follow David Geltner and Richard de Neufville's
[Flexibility and Real Estate Valuation under Uncertainty](https://doi.org/10.1002/9781119106470).
They assume familiarity with its valuation concepts and Python.

Use the source checkout and optional dependencies listed in `docs/guides/walkthroughs.md` in the matching checkout.
The current notebooks use the pre-1.0 canonical API; a plain installation of the
published PyPI package may not supply that API. Tables use Polars. Canonical
records retain their units and provenance independently of display tables.

The first notebook has been migrated to the current Flux/Stream API. The remaining
six notebooks still need that migration and verification; their stored outputs
are from an earlier API checkpoint.

The four later numerical notebooks include a visible routine count of four scenarios.
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
