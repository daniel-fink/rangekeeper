# Verification

Run Python tests from `src/`; run schema and packaging tools from the repository
root. Use separate environments for runtime extras and pinned schema tools.
Historical test counts describe their captured source; run these checks for the
checkout under review.

## Python

Install the extras and development group from [src/README.md](../src/README.md).
From `src/`:

```sh
MPLBACKEND=Agg python -m pytest -q --ignore=tests/legacy/test_api.py
```

The excluded module contains three live predecessor service tests. Optional
MiniZinc tests skip when that executable is absent. Set `RK_MINIZINC` to a compiler
with CP-SAT for these checks. Install the `layout` extra for Z3 checks.

From the repository root, use the pinned [schema dependencies](../tools/schema/requirements.txt):

```sh
python tools/schema/generate.py --check
python tools/schema/generate_csharp.py --check
python tools/schema/typecheck.py
```

Typing also needs `mypy==1.18.2`. Deliberately invalid fixtures must produce their
expected errors; valid sources must pass. The [schema guide](../schema/README.md)
lists seven conformance suites, including the native loader limitation.

`tools/schema/verify_install.py` builds a wheel in a temporary environment and checks
minimal imports, records, codecs, storage and optional runtime slices. Supply
`--runtime-python`, `--financial-python`, `--execution-python` and `--workflow-python`
with interpreters that have those dependencies. Add `--tables-python` to check
Polars and CSV in the isolated environment with pandas absent. Checks use the built artifact.

Do not edit package source during workflow verification: implementation fingerprints
read the source, and a mid-test edit changes the recorded implementation identity.

## Viewer, C# and walkthroughs

From `src/rangekeeper/adapters/cytoscape/client` run `npm ci`, `npm run typecheck`,
`npm run build` and `npm test`. Generated assets ship in the wheel. Browser smoke
checks need a local browser runtime; pure geometry tests do not prove host rendering.

Follow the [C# guide](../grasshopper/README.md) for .NET builds and Python/C# record
round-trips. Follow the [walkthrough guide](../walkthrough/README.md) to execute all
seven sources in fresh kernels, inspect their tables and figures, and build the
site from those executed notebooks. Use fixture mode for local design examples.

Portable tests do not establish Rhino loading or live connector acceptance. The
[Windows procedure](../grasshopper/WINDOWS_DEVELOPMENT.md) remains the separate
external acceptance gate. Do not infer a pass from build output alone.
