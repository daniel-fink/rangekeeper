# Extension points

Every extension point uses one pattern ([ADR-013](../decisions/013-execution-and-extensions.md#extension-points)):

- a `Protocol` that each implementation satisfies;
- a registry in the package that owns the point, with `register(name, implementation)`;
- an optional entry point group, `rangekeeper.<point>`, for installed distributions;
- a fingerprint for each implementation, which evidence records.

The registry class is `rangekeeper.shared.registry.Registry`. `shared` is
internal, so use the registry objects that the owning packages export.

## Points

| Point | Registry | Protocol | Built-in names | Evidence |
| --- | --- | --- | --- | --- |
| Execution backends | `rangekeeper.execution.backends.registry` | `execution.backends.Backend` | `pyomo-highs` | A `solver` implementation in each Run |
| Unit systems | `rangekeeper.quantity.unit_systems` | `quantity.UnitSystem` | `default` | An `evaluator` implementation in each Run that reaches acceptance |
| Geometry providers | `rangekeeper.io.geometry_providers` | `io.GeometryProvider` | none | — |
| Profiles | `rangekeeper.profile.profiles` | Profile classes; each instance satisfies `profile.Profile` | `constant`, `linear`, `compounding`, `uniform`, `scurve` | None yet: `Flow.from_profile` calculates on known data. Equations that name a profile record it ([#309](https://github.com/daniel-fink/rangekeeper/issues/309)) |

The path generators of `rangekeeper.market` and the equation functions of
`rangekeeper.expressions` use the same pattern when their 1.0 APIs land
([#299](https://github.com/daniel-fink/rangekeeper/issues/299),
[#309](https://github.com/daniel-fink/rangekeeper/issues/309)). The profiles
registry holds classes, not instances, because a profile has parameters, such
as `Compounding(rate=)`.

## Register an implementation

```python
from rangekeeper.execution import ExecutionConfig, execute
from rangekeeper.execution.backends import registry

registry.register("my-solver", MySolver())
outcome = execute(specification, store, config=ExecutionConfig(backend="my-solver"))
```

`register` checks the implementation against the Protocol with `isinstance`
and raises `TypeError` when it does not match. A name has lowercase letters and
digits, separated by `-`, `_` or `.`. Registering the same object again under
the same name changes nothing. Another implementation under a used name raises
`ExtensionConflictError`; pass `replace=True` to replace it. Both errors are in
[`rangekeeper.errors`](errors.md#errors).

| Member | Behaviour |
| --- | --- |
| `register(name, implementation, *, fingerprint=None, modules=(), replace=False)` | Registers one implementation and returns its `Registration` |
| `get(name)` | Returns the implementation. An unknown name raises `UnknownExtensionError`, a `LookupError` with `suggestions` |
| `registration(name)` | Returns the `Registration`: `point`, `name`, `implementation`, `fingerprint` and `qualified_name` |
| `names()` | Returns the registered and declared names. It loads no entry point |
| `describe(implementation)` | Returns the registration that evidence records, for a registered or an unregistered implementation |
| `group` | The entry point group, `rangekeeper.<point>` |

## Declare an entry point

An installed distribution can add implementations without an import by the
caller. Declare each one in the group of its point, in `pyproject.toml`:

```toml
[project.entry-points."rangekeeper.backends"]
my-solver = "my_package.solver:backend"

[project.entry-points."rangekeeper.unit_systems"]
imperial = "my_package.units:imperial"
```

The value names the implementation object, not a factory. The registry loads an
entry point on the first lookup of its name. These rules apply:

- An explicit registration takes precedence over an entry point with the same
  name, so an installed distribution cannot replace a built-in.
- Two distributions that declare one name raise `ExtensionConflictError` on
  lookup. Register one of them explicitly to choose.
- An entry point that fails to load raises `ImportError`, with the distribution
  name and version.

## Fingerprints

Each registration has a fingerprint. It is calculated on first use, so
registration at import time reads no source.

- By default, `shared.registry.fingerprint` hashes the static import closure of
  the module that defines the implementation, inside its top-level package. It
  uses the same mechanics as the [execution fingerprints](execution.md). Comments
  and docstrings do not change it. An implementation defined in a script or a
  notebook contributes its own source. A module with no Python source
  contributes the version of the distribution that provides it.
- `modules=` adds sources that no import reaches. The built-in backend adds its
  worker module, which runs in a child process.
- A point whose implementations are values, such as unit systems, gives the
  registry a fingerprint function. `UnitSystem.fingerprint` hashes the
  implementation, the currencies and the definitions.
- `fingerprint=` sets the fingerprint explicitly.

Evidence records `Registration.qualified_name` with the fingerprint as the
version. A registered implementation is `rangekeeper.<point>:<name>`, for example
`rangekeeper.backends:pyomo-highs`. An unregistered implementation, such as a
backend object in an `ExecutionConfig`, is `<module>:<qualified name>`.

## Add an extension point

The package that owns the point creates its registry and registers its built-ins:

```python
from typing import Protocol, runtime_checkable

from rangekeeper.shared.registry import Registry


@runtime_checkable
class Profile(Protocol):
    def shape(self, periods): ...


registry: Registry[Profile] = Registry("profiles", Profile)
registry.register("uniform", Uniform())
```

- Make the Protocol `runtime_checkable`; `Registry` refuses one that is not.
- Use a point name of lowercase letters, digits and `_`. The entry point group is
  `rangekeeper.<point>`.
- Name the registry `registry` when the package holds only that point, and after
  the point otherwise.
- Record `registry.describe(implementation)` in the evidence of the operation
  that uses the implementation.
- Add the point to the table on this page.
