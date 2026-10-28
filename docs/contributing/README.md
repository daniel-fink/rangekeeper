# Contributing

Start with [installation](../guides/installation.md) and the
[architecture](../concepts/architecture.md). [Make a change](change.md) gives
the steps for one pull request; this page explains the tools. Follow
[documentation upkeep](documentation.md) during every change. Use
[verification](verification.md) to select checks for the affected contracts.

## Working folder and branches

Follow the [agent instructions](../../AGENTS.md). Start new `feature/<name>`
branches from `develop` and integrate reviewed work into `develop` through pull
requests; `main` holds releases. Lessons follow the same rule, under
`examples/walkthrough`; keep `codex/walkthrough-acausal` unchanged as source
material and follow the [walkthrough procedure](walkthrough-branch.md). A merge into `develop` does
not make the Bundle format stable or publish the walkthroughs.

Verify the reviewed diff, run the applicable checks and stage only the intended
files. Follow branch protections and the authorized delivery scope. Preserve the
walkthrough branch and ignored source data.

## Release lines

`develop` and `main` carry 1.x. `support/0.8` carries the 0.8.x maintenance
line: bug and security fixes only, until an announced end of life. Start a 0.8
fix from `support/0.8` and open its pull request into `support/0.8`; do not
merge between `support/0.8` and `develop`. A pushed version tag starts the
release workflow. The [release guide](releasing.md) gives the tags, the procedure
and the one-time PyPI setup. [SECURITY.md](../../SECURITY.md) shows the supported
versions.

## Development environment

Use Python 3.12 or 3.13. From the repository root, install the locked development
group and runtime extras:

```sh
uv sync --all-extras --group dev --locked
uv run pytest
```

The development group includes the example builders from this checkout. Record
optional dependency skips separately from passed checks. The core suite needs no
chart, graph or design-transport dependency; the
[walkthrough environment](../guides/walkthroughs.md#explore-the-lessons) tests the
helpers.

Schema tooling uses a separate pinned environment. Follow
[schema development](schema.md) for generation and conformance checks.
The [Grasshopper example](../../examples/grasshopper/README.md) covers the
independent .NET build.

## Dependencies and versions

`pyproject.toml` declares compatible version ranges. Exact versions appear only
in `uv.lock`. The `dev` group includes the `lint` and `notebook` groups;
`ipykernel` is a notebook dependency, not a runtime dependency.

Import an optional dependency where the feature needs it, inside
`rangekeeper.shared.optional.requires`. The resulting `ImportError` names the
extra that installs it:

```python
from rangekeeper.shared.optional import requires

with requires("bundle"):
    import pyarrow as pa
```

setuptools-scm derives the version from git tags; `rangekeeper.__version__`
reads it from the installed metadata. On `develop`, only `v1.*` tags count.
Until the first such tag, `develop` builds as `1.0.0a1.devN`. Release tags use
the PEP 440 form `vX.Y.Z`, with an optional `aN`, `bN` or `rcN` suffix. A CI
checkout needs the full history (`fetch-depth: 0`) for the correct distance.
The C# example takes the same version:

```sh
dotnet build -p:Version=$(python tools/version.py --dotnet)
```

## Python formatting and linting

Use ruff from the development environment. It formats and lints; it replaces
Black. Settings belong in [`pyproject.toml`](../../pyproject.toml). From the
repository root:

```sh
uv run --locked ruff format .
uv run --locked ruff check --fix .
```

The lint rules are Pyflakes (`F`), import order (`I`), bugbear (`B`), pyupgrade
(`UP`) and pydocstyle (`D`). Docstring rules apply to `src/rangekeeper` only:
each public module, class, method and function needs a docstring. Write the first
line of a function or method docstring in the imperative mood. Ruff skips the
generated schema modules and the captured evidence under `docs/`.

Import order can change module load order. If a sorted import causes a circular
import, import the name from the module that defines it, not from its package.

Short signatures can stay on one line. When a signature spans multiple lines:

- Put each parameter on its own line.
- Put `/` and `*` separators on their own lines.
- Add a trailing comma after the last parameter.
- Put the closing parenthesis and return annotation on a separate line.

```python
def author(
    parameters: Mapping | None = None,
    *,
    scenario: Market | None = None,
) -> Model:
    pass
```

The trailing comma makes the formatter keep the expanded layout. The formatter
also accepts some multiline signatures with several parameters on one line, so
the check alone does not enforce this convention.

Keep a `# noqa` or a per-file ignore only with a comment that gives the reason.
Update generators instead of editing generated outputs by hand.

## Local hooks and changelog

pre-commit runs ruff, mypy, nbstripout and the layer contract before each
commit, and the changelog check before each push. Install the hooks once:

```sh
uv run --locked pre-commit install
```

mypy uses the settings in `pyproject.toml`. It checks `src/rangekeeper` with a
baseline that passes; strict mode follows when the public API is typed. Run it
directly with `uv run --locked mypy`. nbstripout removes notebook outputs from
committed notebooks.

Each pull request adds a changelog fragment in
[`changelog.d/`](../../changelog.d/README.md), which gives the names and types.
A pull request with no change for users can use the `no-changelog` label
instead. towncrier writes [`CHANGELOG.md`](../../CHANGELOG.md) from the fragments
at release time.

## Continuous integration

The [CI workflow](../../.github/workflows/ci.yml) runs on each pull request to
`develop`, `main` or `support/0.8` and on each push to `develop` or `main`.
`--locked` fails a job when `uv.lock` does not match `pyproject.toml`.

| Job | Checks |
| --- | --- |
| `lint` | `ruff check` and `ruff format --check` |
| `layers` | `lint-imports`: the layer contract of [ADR-010](../decisions/010-layers-and-packages.md) |
| `types` | mypy, with all extras for their types |
| `changelog` | A fragment in `changelog.d/` and a draft changelog build, in the separate [Changelog workflow](../../.github/workflows/changelog.yml) on pull requests. The `no-changelog` label skips the fragment check; adding or removing a label reruns only this check |
| `generated files` | `tools/schema/generate.py --check`, `check_generator.py`, `generate_csharp.py --check`, `verify_native.py` and `typecheck.py` in the pinned schema environment |
| `dotnet` | Restores and builds the C# Model library and fixture runner in `examples/grasshopper` with the package version, then round-trips the cross-language fixtures through C# |
| `docs` | `tools/docs/check.py` |
| `test` | The full suite with all extras, on Linux and macOS with Python 3.12 and 3.13, and on Windows with Python 3.13 |
| `extra` | The wheel with no extra, then with each extra alone, on Python 3.12 without the lock file. `tools/ci/check_extra.py` imports every module, requires an installation hint for each failure, and runs a small operation of the extra |
| `walkthrough` | The Geometry viewer asset manifest hashes, the helper tests, including charts, graph display, local display and the Speckle envelope, and the lesson checks, then each lesson from a fresh kernel and its conversion for the docs site, in the locked walkthrough environment. Fixture design data and four market paths |
| `wheel` | `uv build`, `twine check --strict`, `check-wheel-contents`, `verify_install.py` with all optional slices and no adapter files, and the suite against the installed wheel |

The test jobs skip no tests, and no test needs a display or network access. `-rs` lists any skips in the log.

CI does not build the Grasshopper components, which need the Rhino assemblies,
or the documentation site. Run those
[verification](verification.md) procedures locally when the change affects them.

## Layer rules

`src/rangekeeper` has 12 layers ([ADR-010](../decisions/010-layers-and-packages.md),
[architecture](../concepts/architecture.md#layers)). A module imports only from
its own layer or a lower layer. The import-linter contract in `pyproject.toml`
encodes the order. Run it from the repository root:

```sh
uv run --locked lint-imports
```

The contract checks imports inside functions too. It excludes imports under
`TYPE_CHECKING`, because they do not run. When a module needs a type from a
higher layer only for an annotation, import it under `TYPE_CHECKING`. Move
other code to the layer that owns it. `ignore_imports` lists only the upward
imports that a planned change removes. Each entry names its issue, and the
change that removes the import also removes the entry.

## Naming and ownership

Use one clear noun for a type and one clear verb for an operation. Qualify a name
when one word would lose domain meaning. Put a record's invariant on its owner;
keep cross-record validation, execution and IO at their explicit boundaries.
Owner subclasses of generated records declare no persistent fields.

Validation helpers use one verb family
([ADR-011](../decisions/011-records-and-validation.md#validation-api)):

| Verb | Returns | On a content problem |
| --- | --- | --- |
| `validate*` | A `ValidationReport` | Adds an `Issue`; raises nothing |
| `check*` | Nothing, or the checked input | Raises a `RangekeeperError`, usually `ContractError` or `ValidationError` |
| `require*` | Nothing | Raises `ContractError` for one rule |

`bounded(issues, check, document=...)` turns a `check*` function into a report.
Each document's `validate_document` (in its package's `validation` module) is
the one implementation behind `validate()` and `check()`.

Use composition between runtime services instead of inheritance with hidden
state. For example, `Executor` traverses batches, `Plan` resolves their graph,
and `Attempt` owns one scalar execution. A layout `Formulation` owns symbolic
geometry; `Interface` owns mutable display state. C# `Validator.Check` overloads
distinguish structural and local Model checks. These different responsibilities
do not require a shared service superclass or universal status enum.

The [package map](../concepts/architecture.md) owns import locations. The
[market paths and rules reference](../reference/market-paths-and-rules.md) owns
quantity names, authoring verbs and the distinction between declarations and
recorded outcomes. The [record reference](../reference/records.md) owns field
presence, immutability and intrinsic methods.

## Writing and documentation

Follow ASD-STE100 principles in documentation, comments, docstrings and contributor
communication. Use clear, direct language. Allow exceptions where they improve
clarity or preserve technical accuracy. Formatters do not enforce prose style.

Agents and developers must apply the
[routine upkeep procedure](documentation.md#routine-upkeep-for-agents-and-developers)
as part of each change. It includes current references, examples, navigation,
decision status and the transfer of completed or superseded plans to history.

Keep the [legacy retirement procedure](legacy-retirement.md) as the authority for
held predecessor code. Directory cleanup does not close its acceptance gate.
