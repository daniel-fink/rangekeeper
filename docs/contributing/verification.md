# Verify a change

Run tests, schema checks, packaging and book tools from the repository root.
Use separate environments for runtime extras and the pinned schema tools. Historical counts describe the source captured at that time;
record fresh results for the checkout under review.

Developers and agents run these checks explicitly before delivering a change.
This checkout defines no GitHub Actions workflows. A push or pull request does
not run these repository checks automatically. Follow
[the verification decision](../decisions/004-package-and-project-ownership.md#verification-ownership)
and record the actual environment: local acceptance does not establish Linux,
Windows or service acceptance on a different host.

## Python and solvers

Install the [development environment](README.md#development-environment). From
the repository root:

```sh
MPLBACKEND=Agg uv run --locked pytest -q --ignore=src/tests/legacy/test_api.py
```

The excluded module contains three predecessor live-service tests. Their exclusion
does not close the [Windows gate](windows-acceptance.md). Tests with missing
optional engines can skip. For layout acceptance, use the
[strict runner](layout-acceptance.md); it requires the pinned MiniZinc/CP-SAT and
Z3 engines and fails on skips. Mathematical execution uses the separately pinned
Pyomo/HiGHS backend.

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

Typing also needs `mypy==1.18.2`. Valid selected sources must pass, and deliberate
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

Use `--wheel /absolute/path/to/candidate.whl` to check an already built artifact.
Supply `--runtime-python`, `--financial-python`, `--execution-python` and
`--workflow-python` with interpreters that have the required dependencies.
`--tables-python` adds Polars/CSV checks in an isolated environment without pandas.
Copied native extensions must match the runtime interpreter. These checks use
the built artifact; source-tree imports alone do not establish wheel correctness.

When changing package discovery or data files, inspect a fresh wheel and source
archive as well. Build from a clean checkout or move an existing `build/`
cache aside first: setuptools can retain removed modules in that cache.
Check that required assets are present and that examples, native
projects and build caches have not entered the Python runtime package.

## Viewer and native projects

From `src/rangekeeper/adapters/cytoscape/client/`:

```sh
npm ci
npm run typecheck
npm run build
npm test
```

Generated viewer assets ship in the wheel. Browser smoke checks need a local
browser runtime; geometry tests alone do not establish rendered interaction.

Follow [Grasshopper](../guides/grasshopper.md#build-and-round-trip) for .NET builds
and Python/C# fixture round trips. Follow [Windows acceptance](windows-acceptance.md)
for Rhino loading and the official connector's publication/receive gate. A portable
build or offline JSON pass cannot substitute for actual host acceptance.

## Examples and documentation

Run the affected [standalone examples](../guides/examples.md#run-standalone-examples).
For walkthrough changes, execute all affected notebooks in fresh kernels, inspect
tables and figures, and [build the book](../guides/walkthroughs.md#build-the-site)
from those executed notebooks. Routine design checks use explicit fixture mode.

Apply [documentation upkeep](documentation.md) in the same change. Check incoming
and outgoing relative links and headings after moves. Check example paths,
working directories and current API names. Inspect built book navigation when
book source or configuration changes. Do not rewrite captured evidence to make
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
