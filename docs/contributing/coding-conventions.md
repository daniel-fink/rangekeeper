# Coding conventions

These rules apply to the Python code in `src/rangekeeper`. They make the code
easy to read, navigate and change, for people and for agents. Ruff and mypy
check some of the rules ([checks](#checks)); review checks the others.

Older code does not follow all of the rules yet. The issues of
[#399](https://github.com/daniel-fink/rangekeeper/issues/399) fix it. New code
and changed code follow the rules. When a rule makes a piece of code less
clear, do not follow it there: say why in a comment, and in the pull request.

Each rule has a short example from this codebase. "Bad" examples show code on
`develop` that an open issue changes. The pull request that fixes a "Bad"
example changes it to the next example on this page, or deletes it.

## Functions

### One job for each function

A function does one job. Its body reads as a short list of named steps. When a
body needs comments to separate its parts, make each part a function.

Good: `Batch.resample` in `flow/_batch.py` reads as its steps: check the
options, assign each value to a target Period, reduce each method's lines, fill
the grid, apply the missing-value rule and merge the Claims.

```python
_check_resample(methods, missing=missing, lines=len(self.units))
targets = tuple(periods)
assigned = self._assign(targets)
reduced = _concat(
    [
        self._reduce(assigned, method=method, lines=lines)
        for method, lines in _plan(methods).items()
    ]
)
grid = _fill_grid(reduced, lines=len(self.units), periods=len(targets))
return self._period_batch(
    _apply_missing(grid, missing),
    targets,
    cells=_claims_by_cell(assigned, self.metadata),
)
```

Good: `Attempt.execute` in `execution/attempt.py`:

```python
def execute(self) -> Outcome:
    """Run the stages, account for each expected failure, and return the Outcome."""
    try:
        staged = self.prepare()
        if staged.ended is None:
            result = self.solve(staged.problem)
        else:
            result = self.record(staged.ended)
        self.accept(staged, result)
    except statuses.EXPECTED as error:
        self.fail(error)
    return self.finish()
```

Ruff stops a function at complexity 10, 12 branches, 6 return statements or 50
statements.

### Dispatch with a table, not a long chain

When the behaviour depends on a kind, put one entry for each kind in a table.
Do not write one `if` branch for each kind.

Bad: `decode` in `model/content.py` has an `if kind == ...` branch for each of
16 content kinds (complexity 30), with the shape checks and the conversions
mixed together.

Good: `Frequency.step` in `duration/calendar.py` reads its value from one
table:

```python
_STEPS: dict[Frequency, tuple[int, int]] = {
    Frequency.DAY: (1, 0),
    Frequency.WEEK: (7, 0),
    Frequency.MONTH: (0, 1),
    ...
}

@property
def step(self) -> tuple[int, int]:
    return _STEPS[self]
```

### Validate first, then compute

Check all inputs first, in one named routine. Then compute. A computation does
not check its inputs again halfway through, and a check does not run a
computation only for its errors.

Good: `ExecutionConfig.__post_init__` in `execution/config.py` checks each
field once, when the value is made. `solve` then uses the value with no
further checks.

## Arguments

### Named arguments

Public functions name their arguments (D14): put `*` first. The exceptions are
a function with one argument, a natural pair such as `start, end`, a list of
any length, and the store-protocol methods such as `load_model(id)` and
`put(document)` ([#410](https://github.com/daniel-fink/rangekeeper/issues/410)).
Public records use `@dataclass(frozen=True, kw_only=True)`. In private code, a
function has at most three positional arguments. A function has at most six
arguments in all. Use an options object, or split the function, when it needs
more.

Bad: `Stream._initialize` in `flow/__init__.py`:

```python
def _initialize(self, names, flows, model, value_ids, missing, join, batch, symbolic):
```

Good: `Model.create` in `model/model.py`:

```python
@classmethod
def create(
    cls,
    *,
    metadata: Metadata,
    definitions: Definitions | Unset = UNSET,
    system: System | Unset = UNSET,
    ...
) -> "Model":
```

### No flag arguments and no mode-only arguments

An argument does not switch the function between jobs, and it does not apply
only to some values of another argument. Use a separate function, an enum, an
options object or a small type, so that an invalid combination cannot be built.

An enum member must not change the job either. Good: `Flow.split` divides
amounts over shorter Periods, and `Flow.resample` reduces them onto longer
Periods. Before [#405](https://github.com/daniel-fink/rangekeeper/issues/405),
`ResampleMethod.SPLIT` made `resample` split, and `missing=` did not apply to
it.

Good: `Flow.clean()` removes unresolved movements and `Flow.drop_zeroes()`
removes zeroes; `Flow.require_resolved()` is separate from `Flow.check()`.
Before [#406](https://github.com/daniel-fink/rangekeeper/issues/406), the
Boolean arguments `clean(remove_zeroes=)` and `check(resolved=)` chose the job.

A result type has one mode too. When a method of a result raises because of
how the result was made, make two result types.

Good: the calendar grids in `duration/grid.py`. A week grid takes a weekday
and a multi-year grid takes an origin, so a week grid with an origin cannot be
built:

```python
rk.duration.containing_period(on=day, grid=WeekGrid(starts=Day.SUNDAY))
rk.duration.containing_period(
    on=day, grid=MultiYearGrid(frequency=Frequency.DECADE, origin=date(2021, 7, 1))
)
```

Good: `ExecutionConfig` groups the options of one solve in one frozen value:

```python
outcome = rk.execution.solve(
    specification=specification,
    config=ExecutionConfig(limits=Limits(...)),
)
```

### One object for each item, not parallel lists

Do not pass two lists that match by position, or two mappings that match by
key. Pass one list of items, or one mapping from a key to one item.

Good: `Stream.resample(method=)` takes one `ResampleMethod` for every line, or
one mapping from each name to its method. The weighting of a mean is part of
the method (`MEAN` or `ELAPSED_MEAN`), so it cannot travel in a second list
([#405](https://github.com/daniel-fink/rangekeeper/issues/405)).

Good: `Specification.cases(*, cases=)` takes one mapping from each case key to
the values of that case.

## Errors

A wrong Python type for an argument raises `TypeError`. Every other failure on
a public path raises a `RangekeeperError` subclass with an `rk.errors.Code`: a
wrong value, a lookup that finds nothing, an unresolved amount, data that does
not decode. Do not raise plain `ValueError` or `KeyError`. `ContractError`,
`UnitError` and the other value errors subclass `ValueError`, so
`except ValueError` still works. Put the values that a caller needs in the
error's fields, not only in its message. An error takes its message first and
every other field by keyword, with the same field names in each error class
([#408](https://github.com/daniel-fink/rangekeeper/issues/408)). See
[errors and diagnostics](../reference/errors.md).

Good, from `Stream.select` in `flow/__init__.py`, which raised a bare
`KeyError` before [#407](https://github.com/daniel-fink/rangekeeper/issues/407):

```python
raise MissingReferenceError(
    str(absent[0]),
    kind="Flow",
    by="name" if available is self.names else "id",
    where="Stream",
    candidates=difflib.get_close_matches(str(absent[0]), names),
)
```

Good, from `model/draft.py`:

```python
return ContractError(
    f"{kind} {by} {text!r} is already declared in {where}",
    code=Code.UNIQUE,
    values={"kind": kind, by: text, "where": where},
)
```

## Types

Every function and method has full type hints: each argument and the return.
Public signatures are part of the API reference, so make them exact.

Good: `offset` in `duration/calendar.py`:

```python
def offset(
    value: date,
    *,
    frequency: Frequency,
    count: int = 1,
    month_roll: MonthRoll = MonthRoll.PRESERVE_END,
) -> date:
```

Ruff checks the annotations of each function. mypy is strict for each package
that the ratchet has reached; see [checks](#checks).

## Classes

### Constructors assign

`__init__` and `__post_init__` assign fields and check invariants. They do not
read files, traverse documents or build other records. A classmethod (`create`,
`from_data`, `from_values`) or a separate function does that work.

Bad: `Reader.__init__` in `io/bundle.py` opens the manifest, checks the
limits, reads each document and rebuilds the records
([#422](https://github.com/daniel-fink/rangekeeper/issues/422)).

Good: `Model.__init__` makes an empty Model from a name. `Model.create` and
`Model.from_data` build a Model from complete records.

## Modules and packages

### Imports at the top

Put imports at the top of the module. A function-level import keeps
`# noqa: PLC0415` with its reason: the import cycle that it breaks, or an
optional dependency
([#331](https://github.com/daniel-fink/rangekeeper/issues/331)). An optional
dependency loads inside `requires`, which names the extra that installs it.

Good: the optional SciPy import of `profile.py`, with the comment that new
code adds:

```python
with requires("calculations"):
    from scipy import stats  # noqa: PLC0415 - optional dependency
```

### Use public names across packages

A module uses only the public names of another package, or names that the
owner package documents for internal use. Do not read another package's
`_index`, `_record`, `_prepared` or `_parse`. When a caller needs one, give
the owner a named method.

Bad: `model/system/rollup.py` calls `stream._prepared().aggregate_groups(...)`
on a Stream from the `flow` package.

Good: `model.entity(code="building_c")` finds an Entity through the Model's
public lookup, and raises `MissingReferenceError` with the nearest codes.

### Package `__init__.py` files only re-export

A package `__init__.py` has a docstring, imports and `__all__`. Public types
live in modules without a leading underscore. An underscore module holds
private helpers only.

Bad: `flow/__init__.py` defines the 450-line `Stream` class. `Flow` lives in
`flow/_flow.py`, so the API reference shows `rangekeeper.flow._flow.Flow`.

Each public module has an `__all__`, so that its imported helpers do not
look public.

Good: `duration/__init__.py` imports `Frequency`, `Period`, `Span` and the
calendar functions from `calendar.py`, `dates.py` and `period.py`, and lists
them in `__all__`.

### One home and one name for each idea

Each idea has one module, and each module name says what it holds. The same
module name in two packages means the same kind of content: every
`validation.py` holds the `validate*`, `check*` and `require*` functions of
its package ([naming and ownership](README.md#naming-and-ownership)). Use the
[glossary](../concepts/glossary.md) words in names.

Bad: `shared/` has 18 modules with unrelated jobs, from YAML decoding to table
display.

Good: the verb families have one meaning in each package: `validate*`
returns a `ValidationReport`, `check*` raises a `RangekeeperError`, and
`require*` raises `ContractError` for one rule.

## Tests

Tests mirror the package: `tests/<package>/test_<module or topic>.py`, and
`tests/<package>/<subpackage>/` for a subpackage. Test public behaviour. A test
of a private helper says why in its docstring. Do not count internal calls with
a monkeypatch, and do not parse source code. Shared fixtures for one package
live in that package's `conftest.py`. Code in `src` that only tests use moves
to the tests.

Bad: `tests/finance/test_calculations.py` has 21 tests, and one of them is
about finance.

Good: `tests/profile/test_profiles.py` tests the public profiles of
`rangekeeper.profile` through `Flow.from_profile` and the `profiles` registry.

## Checks

| Rule | Check |
| --- | --- |
| Function size and complexity | ruff `C901` (10), `PLR0911` (6), `PLR0912` (12), `PLR0915` (50) |
| Argument count | ruff `PLR0913` (6), `PLR0917` (3 positional) |
| Imports at the top | ruff `PLC0415` |
| Type hints | ruff `ANN001`–`ANN206`, mypy strict for each package |
| All other rules | Review |

`pyproject.toml` has a baseline of per-file ignores for the older code that
does not pass the ruff rules yet, and a mypy override for the packages that are
not yet strict. Do not add to either. When you fix a function, remove its codes
from the baseline; when a package passes strict mypy, remove it from the
override. CI fails when a pull request adds to the baseline or to the override.
See the [structure baseline](README.md#structure-baseline).
