# Contributing

Start with [installation](../guides/installation.md) and the
[architecture](../concepts/architecture.md). Follow
[documentation upkeep](documentation.md) during every change. Use
[verification](verification.md) to select checks for the affected contracts.

## Working folder and branches

Follow the [agent instructions](../../AGENTS.md) and the branch procedure below.
Use the single RK folder. Start new `feature/<name>` branches from `develop`
and integrate reviewed work into `develop`; `main` holds releases. Create
worktrees only on an explicit user request. Coordinate branch changes,
staging, commits, merges and shared environments with active chats. Keep
the existing unfinished teaching work on `codex/walkthrough-acausal`; retain
that recovery reference until its own agreed transition. Switch branches
only after saving current changes and coordinating the handoff. Follow the
[walkthrough branch procedure](../guides/walkthroughs.md#branches-and-publication).
A development merge does not approve a stable Bundle format or publish the
walkthroughs. Verify the reviewed diff, run the applicable checks and stage only
the intended files. Follow branch protections and the authorized delivery scope.
After delivery, verify that local `develop` matches a fresh remote query and keep
the primary checkout clean. Preserve the separate unfinished walkthrough branch
and ignored source data.

## Development environment

Use Python 3.10–3.13. From the repository root, install the locked development
group and runtime extras:

```sh
uv sync --all-extras --group dev --locked
uv run pytest
```

The development group includes the example builders from this checkout. Record
optional dependency skips separately from passed checks. Use `--show-plots` only
for an interactive Matplotlib test session.

Schema tooling uses a separate pinned environment. Follow
[schema development](schema.md) for generation and conformance checks.
[Grasshopper](../guides/grasshopper.md) covers the independent .NET build;
[Windows acceptance](windows-acceptance.md) covers the external host gate.

## Python formatting

Use Black from the development environment. Settings belong in
[`pyproject.toml`](../../pyproject.toml). Short signatures can stay on one
line. When a signature spans multiple lines:

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

The trailing comma makes Black preserve the expanded layout. Black also accepts
some multiline signatures with several parameters on one line, so its check alone
does not enforce this convention. From the repository root:

```sh
uv run --locked black path/to/file.py
uv run --locked black --check path/to/file.py
```

Apply the convention when adding or changing handwritten Python. Keep unrelated
formatting outside the task's scope. Run formatting and verification locally
before delivery. Update generators instead of editing generated outputs by hand.

## Continuous integration

The [Tests workflow](../../.github/workflows/tests.yml) runs on each pull request
to `develop` or `main` and on each push to them. On Ubuntu with Python 3.13, it
runs:

```sh
uv sync --locked --all-extras
MPLBACKEND=Agg uv run --locked pytest -q -rs
```

`--locked` fails the run when `uv.lock` does not match `pyproject.toml`. The
workflow installs all extras because the suite imports Matplotlib, Polars, the
Pyomo/HiGHS backend and Bundle IO. It skips no tests: Matplotlib uses the
off-screen `Agg` backend, and no test needs a display or network access.
The `-rs` option lists any optional-dependency skips in the log.

A pull request merges only after its `pytest` check passes. The workflow does not
run Black, schema generation, C# builds, wheel checks, notebooks or the
documentation link check. Run those [verification](verification.md) procedures
locally when the change affects them.

## Naming and ownership

Use one clear noun for a type and one clear verb for an operation. Qualify a name
when one word would lose domain meaning. Put a record's invariant on its owner;
keep cross-record validation, execution and IO at their explicit boundaries.
Generated record behaviors declare no persistent fields.

Use composition between runtime services instead of inheritance with hidden
state. For example, `Executor` traverses batches, `Plan` resolves their graph,
and `Attempt` owns one scalar execution. A layout `Formulation` owns symbolic
geometry; `Interface` owns mutable display state. C# `Validator.Check` overloads
distinguish structural and local Model checks. These different responsibilities
do not require a shared service superclass or universal status enum.

The [package map](../concepts/architecture.md) owns import locations. The
[scenario and policy reference](../reference/scenarios-and-policies.md) owns
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
