<img src="https://github.com/daniel-fink/rangekeeper/blob/v0.2.0/walkthrough/resources/rangekeeper.jpg?raw=true" width="300">

# Rangekeeper

Rangekeeper is a Python library for real estate financial modelling, cashflow
forecasting and scenario analysis. It separates project facts and equations in a
`Model`, investigation choices in a `Specification`, and finalized evidence in a
`Run`. Immutable revisions retain units, identity and provenance.

Known-data calculations support DCF analysis. The execution layer solves declared
finite affine equations with Pyomo/HiGHS and independently checks candidate outputs.
Source workflows and C# Grasshopper components connect reviewed source data and
design models to canonical records. Polars serves detached tables and CSV.

This checkout contains a pre-1.0 redesign that is not yet the published PyPI API.
Use the source installation instructions and the upgrade guide together.
The [package ownership and import guide](docs/README.md#package-ownership-and-imports)
lists the current namespaces; `Model`, `Specification` and `Run` remain root imports.

| Project or guide | Start here |
| --- | --- |
| Python package | [Installation and extras](src/README.md) |
| Architecture and APIs | [Documentation index](docs/README.md) |
| Executable examples | [Walkthroughs](walkthrough/README.md) |
| Schema and generation | [Schema guide](schema/README.md) |
| Rhino/Grasshopper | [C# authoring and host checks](grasshopper/README.md) |
| Older consumers | [Upgrade guide](docs/LEGACY_UPGRADE_GUIDE.md) |
| Verification | [Checks and limits](docs/VERIFICATION.md) |

The walkthroughs follow Geltner and de Neufville's
[Flexibility and Real Estate Valuation under Uncertainty](https://doi.org/10.1002/9781119106470).
Historical plans and captured acceptance results are linked from the documentation
index. The [Windows connector gate](grasshopper/WINDOWS_DEVELOPMENT.md) remains
open; the isolated predecessor trees remain until that gate closes.
