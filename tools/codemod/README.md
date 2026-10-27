# Rename-pass codemod

This tool applies the 1.0 rename map
([ADR-010](../../docs/decisions/010-layers-and-packages.md),
[ADR-012](../../docs/decisions/012-naming-and-glossary.md)). It does two jobs:

- the **package pass** (#95) moves the modules of `src/rangekeeper` into the 1.0
  layers and changes the package, its tests, examples and docs;
- the **consumer pass** (#96) changes code that uses Rangekeeper. It moves no
  files.

Both use the same engine and the same map.

## The map

[`rename_map.yaml`](rename_map.yaml) is the rename map. The draft table in the
[upgrade guide](../../docs/guides/upgrading.md#100a2-rename-map-draft) comes from
it. After you change the map, update the table:

```sh
uv run python -m tools.codemod.render
```

The map has these sections:

| Section | Contents |
| --- | --- |
| `modules` | Module moves. A move applies to the module and its submodules; the longest match wins |
| `paths` | Other repository moves, for example `src/tests` to `tests` |
| `symbols` | Renames of module-level names, and moves of a name to another module |
| `attributes` | Renames of attributes, methods and fields of one class |
| `parameters` | Renames of keyword parameters |
| `removed` | Names with no direct replacement. The tool lists their uses |
| `notes` | Decisions that change API shapes. The tool does not apply them |
| `exclude` | Paths that the tool never changes, such as ADRs and history |

Each entry has a status. The tool applies `agreed` and `draft` entries. It does
not apply `pending` entries (they wait for the decisions in #255) or `open`
entries (they have no 1.0 name). An entry with `requires: [schema]` or
`requires: [refactor]` needs work that the tool cannot do; the tool skips it
unless you add `--with schema` or `--with refactor`.

## Run the package pass

Run from the repository root. Without `--apply`, the tool writes nothing and
reports the changes:

```sh
uv run python -m tools.codemod
```

Apply the pass on a branch, then format the changed files:

```sh
uv run python -m tools.codemod --apply --format --json report.json
```

The tool does these things:

- moves modules and creates missing `__init__.py` files;
- moves the `paths` entries, for example the test suite;
- rewrites `import` and `from ... import` statements, relative imports, and
  qualified references such as `rk.model.flux.Stream`;
- renames definitions and their references, `__all__` entries, string
  annotations and the lazy export tables of package `__init__` modules;
- adds new public subpackages to a package's lazy module table;
- rewrites dotted names and `src/...` paths in strings, for example
  `monkeypatch.setattr` targets and the fingerprint source lists;
- keeps `Path(__file__).parents[N]` on the same folder when a file moves;
- rewrites Python code blocks, prose references and paths in Markdown,
  notebooks and configuration files.

The run is idempotent: a second run changes nothing. `--check` exits with
status 1 when a change is still necessary.

The report lists every move and change. It also lists the uses to review:
removed names, `apply: review` attributes, and references that it cannot
rewrite safely. Read this list after each run.

## Run the consumer pass

The consumer pass needs the index of the old package: its modules and
re-exports. Write the index from a checkout of the old version:

```sh
uv run python -m tools.codemod --write-index rangekeeper-index.json
```

Then run the pass on the consumer project:

```sh
python -m tools.codemod --consumer --index rangekeeper-index.json --root ../project
```

Add paths after the options to limit the run to some files or folders.

## Limits

- The tool has no type inference. An attribute rename with `apply: all`
  changes every attribute with that name in files that import the package.
  Use it only for names that belong to one class.
- A local module alias keeps its name: `from rangekeeper.model import flux`
  becomes `from rangekeeper import flow as flux`.
- The tool does not merge modules or add re-exports. Entries that need this
  have `requires: [refactor]`.
- Generated schema modules are excluded. Regenerate them from the schema.

## Tests

```sh
uv run pytest tools/codemod/tests
```
