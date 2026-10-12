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

This local book includes two accepted chapters. Notebook 01 introduces the numerical
tools through a small DCF. Notebook 02 introduces the continuing mixed-use property:
its actual geometry, graph, use mix, shared services and completed-property economics.
The six legacy sources remain available as references while later lessons are
consolidated and updated.

The continuing example uses the legacy Rangekeeper design, the Garden City framework
for development flexibility, and SFFA for forward and inverse financial questions.
Later chapters will add these ideas in steps:

| Term | Meaning |
| --- | --- |
| Base plan | What is proposed, in what sequence, and when |
| Base case | Financial results under stated reference assumptions |
| Market scenario | One possible history of external conditions |
| Flexibility strategy | Choices retained, their costs and rules for exercising them |
| Realised development | What is built and when after applying those rules |

Notebook 02 loads its complete pinned source locally. Its embedded Speckle viewer
also reads that archive locally; the expired hosted model is retained as a reference.
No live receive, account or upload is needed to run the accepted chapters.

## Table of Contents
- [A Basic Discounted Cash Flow Valuation](basic_dcf.ipynb)
- [From design to property economics](design_to_value.ipynb)

## Acknowledgements
For Andrea, who keeps reminding me it is possible.

```{bibliography}
```
