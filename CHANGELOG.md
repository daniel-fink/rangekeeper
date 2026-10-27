# Changelog

This file records the changes in each 1.x release. towncrier writes each section
from the fragments in [`changelog.d/`](changelog.d/README.md). Do not edit the
sections by hand. The 0.8 line keeps its changelog on `support/0.8`.

<!-- towncrier release notes start -->

## 1.0.0a1 (2026-10-27)

### Breaking changes

- `rangekeeper.visualisation.table` moves to `rangekeeper.model.display`. `Flow.display()`, `Stream.display()`, `Pivot.display()` and their notebook HTML need only the `calculations` extra, not `visualisation`. ([#89](https://github.com/daniel-fink/rangekeeper/issues/89))
- Rangekeeper requires Python 3.12 or later and supports 3.12 and 3.13. The distribution name is lowercase: `rangekeeper`. ([#172](https://github.com/daniel-fink/rangekeeper/issues/172))

### Removals

- `rangekeeper.visualisation` (charts, PyVis graph display and `LocalDisplay`) and the `visualisation` extra are removed. The charts and graph display are walkthrough helpers in `examples/walkthrough/helpers`. Use `Stream.display()` for tables. ([#87](https://github.com/daniel-fink/rangekeeper/issues/87))
- `rangekeeper.io.speckle`, its contract and the geometry viewer are removed from the package; the wheel no longer ships the viewer. They are walkthrough helpers in `examples/walkthrough/helpers`, and the viewer build is in `examples/walkthrough/viewer`. ([#88](https://github.com/daniel-fink/rangekeeper/issues/88))
- The package no longer contains `rangekeeper.schema.native`, the stock LinkML module, which could not be imported without LinkML. The conformance tools generate it when they need it. ([#105](https://github.com/daniel-fink/rangekeeper/issues/105))

### Features

- A feature that needs a missing optional extra raises an `ImportError` that names the extra, for example `pip install 'rangekeeper[bundle]'`. Core modules need no extra: `year_fraction` no longer uses PyXIRR. ([#173](https://github.com/daniel-fink/rangekeeper/issues/173))
- `rangekeeper.__version__` gives the installed version. Versions come from git tags. ([#174](https://github.com/daniel-fink/rangekeeper/issues/174))

### Fixes

- Windows: the directory store, the file codecs and Bundle writing no longer fail on durability syncs.

### Packaging

- The source distribution contains only the package, its metadata and the licence. ([#80](https://github.com/daniel-fink/rangekeeper/issues/80))
- Dependencies use compatible version ranges instead of exact pins; `uv.lock` keeps the exact versions for development. The execution worker accepts any Pyomo and HiGHS version in range and records the versions it found in the Run evidence. ([#170](https://github.com/daniel-fink/rangekeeper/issues/170))
- `ipykernel` is no longer a runtime dependency. Install it with your notebook environment. ([#171](https://github.com/daniel-fink/rangekeeper/issues/171))
- On Windows, Rangekeeper depends on `tzdata`, so that time zone keys in Content values decode without a system time zone database.

### Documentation

- The design transport reference moves to the walkthrough helpers' README and the Grasshopper guide to the example's README. The Windows connector acceptance procedure moves to history: it is no longer a library gate. The architecture page lists the folders outside the package. ([#92](https://github.com/daniel-fink/rangekeeper/issues/92))
- Walkthrough plan v2 (ADR-020) defines the seven 1.0 lessons, their readers, developer-experience rules and source rights. It supersedes the ADR-006 curriculum. ([#200](https://github.com/daniel-fink/rangekeeper/issues/200))
- The mixed-use property data in `examples/data/mixed_use_property` is licensed under CC BY 4.0. Its manifest gives the origin, description and licence of each file, and `origins.json` gives the origin of each teaching assumption. ([#210](https://github.com/daniel-fink/rangekeeper/issues/210))

### Engineering

- The walkthrough uses four figures from de Neufville and Geltner (2018) with the publisher's permission and with attribution. ADR-020 records this. ([#76](https://github.com/daniel-fink/rangekeeper/issues/76))
- The C# Model library and Grasshopper components move from `src/grasshopper` to `examples/grasshopper`, as an unsupported example. The C# generator writes there, and a `dotnet` CI job builds the Model library and fixture runner and round-trips the cross-language fixtures. ([#90](https://github.com/daniel-fink/rangekeeper/issues/90))
- The chart, graph, local display, Speckle envelope and geometry tests move to the walkthrough CI job. The core test suite installs no chart, graph or Matplotlib dependency. ([#91](https://github.com/daniel-fink/rangekeeper/issues/91))
- pre-commit runs ruff, mypy, nbstripout and the changelog check. ([#182](https://github.com/daniel-fink/rangekeeper/issues/182))
- CI tests Linux and macOS on Python 3.12 and 3.13 and Windows on Python 3.13, each optional extra alone, and the built wheel. It also runs ruff, mypy, the generated-file checks, the documentation check and the changelog check (#180, #181, #184, #185, #186, #188). ([#183](https://github.com/daniel-fink/rangekeeper/issues/183))
- A `walkthrough` CI job runs the helper tests and each lesson from a fresh kernel in the locked walkthrough environment, then converts each lesson for the docs site. ([#187](https://github.com/daniel-fink/rangekeeper/issues/187))
- A pushed version tag publishes the release to PyPI by trusted publishing, after maintainer approval, and creates a GitHub Release with build provenance attestations. `SECURITY.md` lists the supported versions (#70, #71). ([#189](https://github.com/daniel-fink/rangekeeper/issues/189))
- The walkthrough moves onto `develop` under `examples/walkthrough`: seven lesson skeletons named `NN_slug.ipynb`, the presentation helpers with tests, a locked environment and the book resources. `tools/docs/notebooks.py` converts executed lessons to Markdown for the Zensical docs site. The Jupyter Book configuration and environment in `walkthrough/` are removed. ([#202](https://github.com/daniel-fink/rangekeeper/issues/202))
