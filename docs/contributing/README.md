# Contributing

Start with [installation](../guides/installation.md) and the
[architecture](../concepts/architecture.md). Follow
[documentation upkeep](documentation.md) during every change. Use
[verification](verification.md) to select checks for the affected contracts.

## Development environment

Use Python 3.10–3.13. From the repository root, install the locked development
group and runtime extras:

```sh
uv sync --all-extras --group dev --locked
uv run pytest --ignore=src/tests/legacy/test_api.py
```

The development group includes the example builders from this checkout. Three
predecessor live-service tests remain excluded from local acceptance. Missing
optional layout engines can produce skips in ordinary tests. Use
[strict layout acceptance](layout-acceptance.md) when verifying layout support.
Use `--show-plots` only for an interactive Matplotlib test session.

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
before delivery; this checkout defines no GitHub Actions workflows.
Update generators instead of editing generated outputs by hand.

## Naming and ownership

Use one clear noun for a type and one clear verb for an operation. Qualify a name
when one word would lose domain meaning. Put a record's invariant on its owner;
keep cross-record validation, execution and IO at their explicit boundaries.
Generated record behaviors declare no persistent fields.

Use composition between runtime services instead of inheritance with hidden
state. For example, `Executor` traverses batches, `Plan` resolves their graph,
and `Attempt` owns one scalar execution. A layout `Formulation` owns symbolic
geometry; `Viewer` owns mutable display state. C# `Validator.Check` overloads
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
