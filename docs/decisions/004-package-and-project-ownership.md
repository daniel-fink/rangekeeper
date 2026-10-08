# ADR-004: Organize packages by domain and source projects by build boundary

Status: implemented. Domain package structure accepted on 2026-10-08; the user
selected `src/grasshopper` and authorized its move on 2026-10-08.

## Problem and choice

The Python library's hierarchy should express Model, Specification and Run
ownership. The repository must also contain examples, schema sources, development
tools and an independently built C# host project without treating all of them as
Python modules.

Keep Python domain capabilities under `src/rangekeeper`. Keep its file, service
and presentation adapters under `rangekeeper.adapters`. Put the Grasshopper .NET
solution beside the Python package at `src/grasshopper`. Its Model, Components
and Tests projects retain their own build and host requirements.

Keep maintained guides in `docs`, runnable examples in `examples`, authoritative
schema definitions in `schema`, and generation/verification/build programs in
`tools`. Example builders use the separate local `rangekeeper_examples` package.
Do not move contract ownership into a generic shared package merely because two
modules use similar words.

## Alternatives and consequences

Placing the C# project in `src/rangekeeper/adapters/grasshopper` would require
explicit exclusions from Python package discovery, distributions and runtime
source scans. A repository-level `adapters/grasshopper` keeps that boundary but
adds a separate source root. Moving all Python adapters to `src/adapters` would
require new imports or custom packaging to retain their current public namespace.

`src/grasshopper` keeps the .NET solution outside the existing `rangekeeper*`
package-discovery rule and Python runtime scan. Only native generator, build and
acceptance paths change. No schema version, C# namespace or component identity
change is needed. A future group of host projects can justify another grouping
when those projects exist.

## Python project configuration

On 2026-10-08, the user approved moving `pyproject.toml` and the main `uv.lock`
to the repository root. Python source remains under `src/rangekeeper`; native
source remains under `src/grasshopper`. Root commands use explicit package
discovery and root pytest configuration. The separate example and walkthrough
projects retain their own metadata; their local source paths resolve to the root.

The project description is "Algorithmic modelling for project finance". The root
README supplies package documentation, and `license-files = ["LICENSE"]` includes
the license text in distributions. Package discovery excludes implicit namespace
directories; explicit package-data rules retain runtime schemas, viewer assets,
solver data and the transport contract. Existing optional capabilities remain;
the duplicate Pint requirement was removed from `calculations` because core
already requires it.

The alternative was to retain metadata under `src`, with separate handling for
root documentation and license files. Root metadata gives developers one working
directory for installation, builds and verification. Generator and acceptance
tools keep their own environment requirements. Acceptance checks both fresh
distributions, a wheel rebuilt from the source archive, isolated installation
and the affected root commands. An ignored environment left under
`src/.venv` is an earlier local environment; `uv sync` at the root creates `.venv`.

Local acceptance on 2026-10-08 used Python 3.10.19 for the root development
and installed-package checks, and Python 3.12.12 for the schema tools:

- Root `uv sync --all-extras --group dev --locked` and `uv run --locked` pass.
  Both lockfiles retain their dependency versions and resolve the new local paths.
- The root test suite passes: 1,478 tests in 209.80 seconds, with strict layout
  solvers and zero skips. The three predecessor live-service tests in
  `src/tests/legacy/test_api.py` remain explicitly excluded.
- Both generators are current. Typing accepts 209 sources and detects all 38
  intended static errors. Documentation checks cover 64 pages and all 38 current
  pages are reachable.
- The clean wheel has 246 entries and the source archive has 284. Both include
  `LICENSE` and required runtime assets, with no native project or example code.
  All 241 runtime files match the preceding wheel byte-for-byte.
- A wheel rebuilt from the source archive passes isolated core, financial,
  table/CSV, workflow and process-isolated solver checks. The verification tool's
  own temporary build also passes and now requires the project license.

These checks cover the local packaging change. They do not establish a new
Windows/Rhino/service result. The native build, cross-language checks, schema
conformance and notebook/book results from the preceding organization pass are
recorded in the [documentation implementation record](../history/plans/DOCUMENTATION_PLAN.md#implementation-record-2026-10-08).

## Installation capabilities

On 2026-10-08, the user approved consolidating overlapping extras into useful
installation choices: `financial` and `tables` join `calculations`; `plotting`
joins `visualization`; `excel` joins `workflow`. The standalone `yaml`, `execution`,
`layout`, `speckle` and held `legacy` groups remain. This reduces twelve groups
to eight without renaming modules or changing their lazy import boundaries.

The earlier package move retained the old extras to preserve installation
behavior. This subsequent decision retires the four narrower names without
aliases. Users who selected only financial or table operations now install the
combined calculation dependencies. Visualization also installs Matplotlib.
All former capability dependencies remain available and their version ranges
are retained. The [upgrade mapping](../guides/upgrading.md#installation-extra-migration)
and [installation guide](../guides/installation.md#choose-capabilities) own the
current user instructions. Narrow import checks remain useful independently of
how packages are installed.

Local acceptance of this consolidation on 2026-10-08 used Python 3.10.19,
starting from `ece8ff8` with the changes described above:

- `uv lock --check --offline` passed for the root and walkthrough projects.
  Package versions in both lockfiles and core dependency requirements are unchanged.
- `uv sync --all-extras --group dev --locked` completed. Calculation,
  visualization and workflow dependency imports passed.
- A fresh wheel exposes exactly eight extras. Its dependency requirements match
  the combined former groups. All isolated installed-package checks passed,
  including financial, execution, workflow, Polars/CSV and Stream checks.
- The Excel ingestion, financial library, adapter and Flux/Stream test modules
  passed: **121 tests, zero skips**. Documentation checks passed for 65 pages and
  navigation to 39 current pages. Notebook execution remains a separate phase.

## Verification ownership

On 2026-10-08, the user selected explicit local verification and requested removal
of the two GitHub Actions workflows. The workflow files are removed from this
checkout. Tests and the schema, packaging, layout and documentation verification
tools remain maintained. Developers and agents run the relevant procedures before
delivering a change and retain results for the exact source and environment.

The alternative was to retain automatic checks on pushes and pull requests in a
fresh Linux environment. Removing them reduces hosted automation and its setup
maintenance. It also removes automatic check execution and artifact uploads.
Local macOS results do not establish Linux, Windows, Rhino or service acceptance.
The [verification guide](../contributing/verification.md) owns current commands;
[layout acceptance](../contributing/layout-acceptance.md) owns strict solver checks.

GitHub reported no protected branches or repository rulesets when checked on
2026-10-08. No repository settings needed adjustment. Removal takes effect on a
remote branch when these deletions are pushed to it. Earlier source and results
remain historical, including the
[schema workflow](https://github.com/daniel-fink/rangekeeper/blob/08aac85973429da8eaf4ad73b1e5b055506e2775/.github/workflows/schema-records.yml)
and [layout workflow](https://github.com/daniel-fink/rangekeeper/blob/08aac85973429da8eaf4ad73b1e5b055506e2775/.github/workflows/layout.yml)
at the preceding committed checkpoint.

## Sources and related decisions

- [Architecture and import map](../concepts/architecture.md).
- [RF-034 package structure](../history/plans/REFACTORING_FOLLOWUP_PLAN.md#rf-034-agreed-module-hierarchy-and-import-migration).
- [Repository and documentation implementation](../history/plans/DOCUMENTATION_PLAN.md).
- [Grasshopper build](../guides/grasshopper.md) and [Windows acceptance](../contributing/windows-acceptance.md).
- [Documentation upkeep](../contributing/documentation.md).

Supersedes: the temporary repository-level Grasshopper placement and the
unimplemented Python-subpackage option recorded in the documentation plan.
Those alternatives had no earlier ADR identifier. Superseded by: none.
