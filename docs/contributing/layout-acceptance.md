# Layout solver acceptance

Layout solvers are optional presentation dependencies. See the
[viewer reference](../reference/viewer.md) for their behavior and limits. The strict acceptance
command requires MiniZinc **2.10.1**, its bundled OR-Tools CP-SAT **9.15**, and
`z3-solver` **5.1.0.0**. These pins and official release-asset SHA-256 hashes are in
[`toolchain.json`](../../tools/layout/toolchain.json). They do not change the Pyomo/HiGHS execution backend.

## Set up a machine

Use a current patched Python 3.10–3.13 with the `tarfile` data extraction filter.
Run from the repository root:

```sh
python -m pip install -e '.[layout,workflow]' ./examples 'pytest==8.4.2' 'matplotlib>=3.10'
npm ci --prefix src/rangekeeper/adapters/cytoscape/client
python tools/layout/install.py --directory "$HOME/Applications/rk-minizinc-2.10.1"
. "$HOME/Applications/rk-minizinc-2.10.1/env.sh"
```

The installer supports macOS Apple Silicon/Intel and Linux x86-64. It downloads
the [official full bundle](https://www.minizinc.org/downloads/), checks the pinned
digest before extraction, and refuses to replace an existing directory. On Linux,
choose a suitable installation directory instead of `Applications`. The generated
`env.sh` sets `RK_MINIZINC` and, on Linux, the bundle's library path for the current
shell. Shell startup files are not edited. `--archive PATH` accepts a downloaded
asset and applies the same checksum check.

## Run strict acceptance

```sh
python tools/layout/verify.py --output /tmp/rk-layout-acceptance-001
```

The output directory must be new. Alternatively, use `--minizinc /absolute/path/to/minizinc`
instead of setting `RK_MINIZINC`. The path applies only to that command's child
processes. `RK_MINIZINC` takes precedence over `PATH` in both tests and production.

The command checks the pinned versions and runs every `src/tests/test_layout*.py`
file. This includes native MiniZinc, Z3 comparisons, workbench, saved layouts,
geometry checks and browser arithmetic. Node and the viewer's development
dependencies are required for the browser test. Any missing engine, empty test
selection, test failure, collection error or skip causes failure. Shell-level
`PYTEST_ADDOPTS` cannot silently narrow the acceptance selection.

Each run retains `result.json`, `preflight.txt`, `pytest.txt` and `results.xml`.
The result records versions, source hashes, command, selected files, counts and
elapsed time. Temporary solver files and Matplotlib caches are not evidence.
The GitHub workflow has been removed. Run this procedure explicitly on each
platform being accepted and retain its output directory, including failed runs.
No automatic upload or separate Linux run occurs after a push.

## Ordinary tests

From the repository root, after sourcing the environment file:

```sh
python -m pytest --require-layout-solvers --ignore=src/tests/legacy/test_api.py
```

The shared `tests.layout_support` plugin owns both solver checks. The `minizinc`
and `z3` markers declare requirements. Without `--require-layout-solvers`, a missing
engine produces an explicit skip. With the option, preflight requires both engines
and every skip fails the selected run, including collection and browser skips.
The three excluded predecessor service tests remain a separate acceptance gap.

Do not increase solver deadlines or weaken geometry/score assertions to obtain a
passing run. Retain failed attempts and diagnose the cause. For a solver upgrade,
review the bundle URLs and hashes, update pins, run strict acceptance, and retain
new evidence. Prior checkpoint counts remain historical.
