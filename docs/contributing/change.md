# Make a change

This page gives the steps for one change, from a branch to a merged pull
request. The [contributor guide](README.md) explains each tool. Run all commands
from the repository root.

## 1. Start a branch

Start from the latest `develop`. Name the branch for its issue:

```sh
git fetch origin
git switch -c feature/123-short-name origin/develop
```

A 0.8 fix starts from `support/0.8` instead, and its pull request goes into
`support/0.8` ([release lines](README.md#release-lines)). Keep one issue in each
pull request. Rebase on `develop` often; a small pull request is easier to
review and to rebase.

## 2. Set up once

Install the locked environment and the hooks:

```sh
uv sync --all-extras --group dev --locked
uv run --locked pre-commit install
```

The hooks run ruff, mypy, nbstripout and the layer contract before each commit,
and the changelog check before each push
([local hooks](README.md#local-hooks-and-changelog)).

## 3. Put the code in the right layer

Find the package that owns the concept in the
[architecture](../concepts/architecture.md#layers). A module imports only from
its own layer or a lower layer ([layer rules](README.md#layer-rules)). Check
before you commit:

```sh
uv run --locked lint-imports
```

- Put an optional dependency inside `requires(...)` at the point of use
  ([dependencies](README.md#dependencies-and-versions)).
- To let users add implementations of a Protocol, use the
  [extension pattern](../reference/extensions.md#add-an-extension-point).
- To change a persistent field, change the LinkML schema and regenerate
  ([schema development](schema.md)). Do not edit generated files.

## 4. Test the change

Put each test in the folder of the package that owns the behaviour
([test layout](verification.md#python-and-solvers)). Then run the core checks:

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked lint-imports
uv run --locked pytest -q
uv run --locked python tools/docs/check.py
```

Add the checks that the change affects, for example the schema checks or the
installed-wheel check ([verification](verification.md)).

## 5. Update the public API snapshot

A change to a public name, signature or defining module changes
`tests/contracts/api.json`. The snapshot test fails until you write it again:

```sh
uv run python -m tests.contracts.api --write
```

Review the difference before you commit it. When a public import path moves or
is removed, add the move to `tools/codemod/rename_map.yaml` and render the
[upgrade guide](../guides/upgrading.md) table
([codemod](../../tools/codemod/README.md#the-map)).

## 6. Add a changelog fragment

Add one fragment for each kind of change, named for the issue
([fragment types](../../changelog.d/README.md)):

```sh
uv run --locked towncrier create 123.feature.md --content "Describe the change."
```

Use `breaking` when existing code, data or installations can stop working, for
example when a public import path changes. Write for users of the package: say
what changed and what they must do.

## 7. Update the documentation

Update the page that owns the changed behaviour in the same pull request
([documentation upkeep](documentation.md#routine-upkeep-for-agents-and-developers)).
Update decision status only when the implementation supports it.

## 8. Open the pull request

Push the branch and open a pull request into `develop`. In the description,
give the issue, what changed, the API snapshot and changelog changes, and the
checks that you ran, with their results. Say when the change needs a new
required CI check; the maintainer updates the branch protection. List the choices
that the maintainer has not confirmed
([record each decision](documentation.md#record-each-decision)).

The repository is public. In issues, pull requests, commits and documents, name
a consumer of the library by its role, not by its name.

CI runs the [jobs](README.md#continuous-integration) on the pull request. A
pull request merges into `develop` when the maintainer approves it, every
required check passes and the branch is up to date with `develop`. A pull
request that changes a lesson notebook waits for the maintainer's review. A
squash merge into `develop` does not close the issue; the maintainer closes it
after the merge.

The Status field of the
[Rangekeeper project](https://github.com/users/daniel-fink/projects/8) has three
values: a closed issue is Done, an open issue that an open pull request title
names is In progress, and all other issues are Todo. Set In progress by hand when
work starts before a pull request exists. Blocked-by links, not Status, show that
an issue is blocked.

## 9. Release

Releases are tags. The maintainer writes the changelog section from the
fragments, tags the commit and approves the PyPI deployment
([release a 1.x version](releasing.md#release-a-1x-version)).
