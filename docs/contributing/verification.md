# Verify a change

Run tests, schema checks, packaging and book tools from the repository root.
Use separate environments for runtime extras and the pinned schema tools. Historical counts describe the source captured at that time;
record fresh results for the checkout under review.

Developers and agents run these checks explicitly before delivering a change.
The [CI workflow](README.md#continuous-integration) runs the lint, type,
changelog, generated-file, documentation, test, extra and wheel checks on pull
requests. It does not build the .NET example, execute notebooks or build the
book; run those procedures locally. Follow
[the verification decision](../decisions/004-package-and-project-ownership.md#verification-ownership)
and record the actual environment: local acceptance does not establish Linux,
Windows or service acceptance on a different host.

## Python and solvers

Install the [development environment](README.md#development-environment). From
the repository root:

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
MPLBACKEND=Agg uv run --locked pytest -q
```

To check an installed wheel with no extra or with one extra, install it in a
separate environment and run, outside the checkout's `src` folder:

```sh
python tools/ci/check_extra.py core
```

Replace `core` with `bundle`, `calculations`, `execution`, `visualisation` or `yaml`.

Record optional dependency skips separately from passed checks. Mathematical
execution uses the Pyomo/HiGHS backend; Run evidence records the installed versions. Local tests do not close the
[Windows gate](windows-acceptance.md).

Do not edit package source while a workflow verification run is active.
Implementation fingerprints read the source; a concurrent edit can change the
recorded implementation identity during the test.

## Schema and typing

In the [pinned schema environment](schema.md), from the repository root:

```sh
python tools/schema/generate.py --check
python tools/schema/generate_csharp.py --check
python tools/schema/verify_native.py
python tools/schema/typecheck.py
```

The native round trip and typing checks also need `mypy==1.18.2`,
`py-moneyed` and `pint` in that environment. `verify_native.py` generates the
stock LinkML module in a temporary folder; the package does not contain it.
`typecheck.py` uses `mypy==1.18.2`. Valid selected sources must pass, and deliberate
invalid fixtures must produce their expected errors. Run all
[seven conformance suites](schema.md#conformance) for schema, migration or record
boundary changes. Native round-trip checks test the stock loader separately from
the generated production records.

## Installed distributions

`tools/schema/verify_install.py` builds and checks an isolated wheel. It verifies
minimal imports, records, codecs and storage, plus the optional slices selected
by interpreter arguments. Run from the repository root in the schema environment:

```sh
python tools/schema/verify_install.py
```

Without `--wheel`, the script builds the wheel itself and needs `pip`,
`setuptools>=77` and `setuptools-scm>=9`.

Use `--wheel /absolute/path/to/candidate.whl` to check an already built artifact.
Supply `--runtime-python`, `--financial-python` and `--execution-python` with interpreters that have the required dependencies.
`--tables-python` adds Polars/CSV checks in an isolated environment without pandas.
These interpreter options select verification slices, not installation extra
names. The financial and table slices still check narrow import boundaries within
the combined `calculations` capability.
Copied native extensions must match the runtime interpreter. These checks use
the built artifact; source-tree imports alone do not establish wheel correctness.

When changing package discovery or data files, inspect a fresh wheel and source
archive as well. Build from a clean checkout or move an existing `build/`
cache aside first: setuptools can retain removed modules in that cache.
Check that required assets are present and that examples, native
projects and build caches have not entered the Python runtime package.

## Local display and native projects

For changes to the notebook Geometry viewer, follow the
[viewer build procedure](../../tools/geometry/README.md). Inspect the generated
assets and their manifest; `python tools/geometry/check_manifest.py` compares
the packaged assets and the viewer sources with the manifest hashes. Browser smoke checks need a local browser runtime;
geometry tests alone do not establish rendered interaction.

Follow [Grasshopper](../guides/grasshopper.md#build-and-round-trip) for .NET builds
and Python/C# fixture round trips. Follow [Windows acceptance](windows-acceptance.md)
for Rhino loading and the official connector's publication/receive gate. A portable
build or offline JSON pass cannot substitute for actual host acceptance.

## Examples and documentation

Run the affected [standalone examples](../guides/examples.md#run-standalone-examples).
For walkthrough changes, execute all affected lessons in fresh kernels, inspect
tables and figures, and [convert them for the docs site](../guides/walkthroughs.md#convert-for-the-docs-site)
from those executed notebooks. Routine design checks use explicit fixture mode.

Apply [documentation upkeep](documentation.md) in the same change. Check incoming
and outgoing relative links and headings after moves. Check example paths,
working directories and current API names. Inspect the converted pages when
lesson conversion changes. Do not rewrite captured evidence to make
historical commands appear current.

From the repository root, check local Markdown links, section anchors and routes
from the main index with:

```sh
python tools/docs/check.py
```

The check covers current pages, archived plans and history navigation. It checks
linked files but does not fetch external URLs or lint captured research and book
outputs. It cannot establish that a command or API description is correct.

## Record the result

Keep source revision, environment versions, exact commands, counts, exclusions,
failures and external limits with the dated acceptance result. Use one candidate
wheel across the required installed-package and notebook checks when accepting a
release or a large refactor. A passing subset is evidence for that subset. Record
unrun platforms, native hosts and service checks explicitly. Older records of
GitHub checks remain historical evidence; their workflows have been removed.
The current CI workflow is described in [continuous integration](README.md#continuous-integration).

## Bundle candidate verification

With the `bundle` extra installed, run `python -m pytest -q src/tests/test_bundle.py`
from the root. Full schema generation and C# checks also apply because Model schema
changed. See the [Bundle contract](../reference/bundle.md) and the acceptance
matrix in [ADR-008](../decisions/008-rangekeeper-bundle-contract.md). Do not infer provider or host acceptance
from canonical Parquet tests.
