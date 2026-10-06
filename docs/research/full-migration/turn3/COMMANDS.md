# Turn 3 reproduction commands

Use the recorded environment versions in [environment-final.json](environment-final.json).
Run from `/Volumes/Data/Projects/Rangekeeper` unless a different directory is shown.
Temporary directory names are execution locations, not required public APIs. Use
fresh locations for a new acceptance run. Real project outputs stay private.

## Python, schemas and typing

```sh
# cwd: /Volumes/Data/Projects/Rangekeeper/src
MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/rk-mpl-cache /private/tmp/rk-full-runtime/bin/python -m pytest tests --ignore=tests/test_api.py -q --tb=short --junitxml=../docs/research/full-migration/turn3/complete-suite.xml

# cwd: /Volumes/Data/Projects/Rangekeeper
PYTHONPATH=/private/tmp/rk-record-typecheck /private/tmp/rk-full-runtime/bin/python tools/schema/typecheck.py
PYSTOW_HOME=/private/tmp/rk-domain-migration-pystow /private/tmp/rk-probe-audit-venv/bin/python tools/schema/generate.py --check
PYSTOW_HOME=/private/tmp/rk-domain-migration-pystow /private/tmp/rk-probe-audit-venv/bin/python tools/schema/generate_csharp.py --check
```

Run each of `schema/checks/validate.py`, `native_roundtrip.py`, `expressions.py`,
`formulations.py`, `models.py`, `specifications.py`, and `runs.py` with the schema
interpreter and the same `PYSTOW_HOME`. [checks/commands.jsonl](checks/commands.jsonl)
contains the exact executed commands and exit codes. `runs.py` was repeated after
the report-index correction; see `accepted-schema-runs.txt`.

## One wheel and seven notebooks

```sh
/private/tmp/rk-probe-audit-venv/bin/python docs/research/full-migration/turn1/build_notebook_environment.py --output /private/tmp/rk-turn3-complete-wheel
/private/tmp/rk-full-runtime/bin/python tools/schema/verify_install.py --wheel /private/tmp/rk-turn3-complete-wheel/wheel/rangekeeper-0.8.71-py3-none-any.whl --runtime-python /private/tmp/rk-full-runtime/bin/python --execution-python /private/tmp/rk-full-runtime/bin/python --workflow-python /private/tmp/rk-full-runtime/bin/python --financial-python /private/tmp/rk-full-runtime/bin/python
/private/tmp/rk-full-runtime/bin/python docs/research/full-migration/turn3/run_walkthroughs.py /private/tmp/rk-turn3-complete-wheel/site /private/tmp/rk-turn3-complete-notebooks

# cwd: /private/tmp; no source checkout on the import path
PYTHONPATH=/private/tmp/rk-turn3-complete-wheel/site /private/tmp/rk-full-runtime/bin/python /Volumes/Data/Projects/Rangekeeper/docs/research/full-migration/turn3/guide_example.py
```

The runner declares `RK_DESIGN_MODE=fixture`, `RK_SCENARIO_COUNT=4`, workers 1,
wheel-first imports, and isolated plotting/cache directories. Each notebook starts
its own fresh kernel. The historical 2,000-scenario option remains available but
is not a routine acceptance run.

## Projects

The new project environment was created with Python 3.13.11 and the original
project dependencies, then installed with the exact wheel and no editable RK.
The original independent lockfiles remain the dependency authority. The captured
installed package list is in the environment report. The final wheel update was:

```sh
UV_CACHE_DIR=/private/tmp/rk-turn3-uv-cache /Users/daniel/.local/bin/uv pip install --python /private/tmp/rk-turn3-project-venv/bin/python --no-deps --reinstall-package rangekeeper /private/tmp/rk-turn3-complete-wheel/wheel/rangekeeper-0.8.71-py3-none-any.whl
/private/tmp/rk-turn3-project-venv/bin/python docs/research/full-migration/turn3/bootstrap_projects.py prepare
/private/tmp/rk-turn3-project-venv/bin/python docs/research/full-migration/turn3/bootstrap_projects.py build
/private/tmp/rk-turn3-project-venv/bin/python docs/research/full-migration/turn3/bootstrap_projects.py tests
/private/tmp/rk-turn3-project-venv/bin/python docs/research/full-migration/turn3/bootstrap_projects.py notebook
/private/tmp/rk-turn3-project-venv/bin/python docs/research/full-migration/turn3/compare_bootstrap.py
```

`prepare` requires a fresh destination and reads original inputs. It copies no
archives, environments or prior build outputs. `build` creates all three Models;
`tests` runs pytest, Ruff and ty for each project. `notebook` runs Mandarin's thin
review in a new kernel and checks source hashes. The separate comparator uses
private historical bundles under `/private/tmp/rk-turn3-private/baseline`.

The older Mandarin SOM test is separate. From the copied Mandarin directory:

```sh
MANDARIN_REFERENCE=/Volumes/Data/Projects/Whirlwind/projects/mandarin/artifacts/yaml-rebuild/reference MANDARIN_CANDIDATE=/private/tmp/rk-turn3-complete-project-bootstrap/results/mandarin/runs/5400730b-c910-43ff-a8a8-e5e529555f1d /private/tmp/rk-turn3-project-venv/bin/python -m pytest tests/test_equivalence.py -q
```

Select the new successful attempt directory when reproducing the check. The ordinary suite skips this
reference-only test; no historical artifact enters a build.

## Viewer and layout

From `src/rangekeeper/adapters/cytoscape/client`, run the package's typecheck,
build and test scripts with Node 24.15.0. The saved-layout browser test is
`node --test test/saved-browser.cjs` with its documented `RK_SAVED_VIEWER_URL`
fixture and optional `RK_CHROME` executable override. It uses a temporary browser profile and a synthetic
layout. Python layout and workbench tests are included in the complete suite.
MiniZinc checks require `RK_MINIZINC` pointing to an installation with CP-SAT.
Z3 is a separate optional dependency and was installed for local acceptance.

## C#, Rhino and service boundary

```sh
DOTNET_CLI_HOME=/private/tmp/rk-dotnet-home NUGET_PACKAGES=/private/tmp/rk-nuget /opt/homebrew/bin/dotnet build grasshopper/Components/Components.csproj --no-restore
DOTNET_CLI_HOME=/private/tmp/rk-dotnet-home NUGET_PACKAGES=/private/tmp/rk-nuget /opt/homebrew/bin/dotnet build grasshopper/Tests/Tests.csproj --no-restore
PYTHONPATH=/private/tmp/rk-turn3-complete-wheel/site /private/tmp/rk-full-runtime/bin/python docs/research/full-migration/turn3/cross_language.py prepare /private/tmp/rk-turn3-cross
```

First-time restoration uses the checked package lockfiles and local Rhino 8
references. Run `grasshopper/Tests/bin/Debug/net8.0/Tests.dll` with the
Rhino arm64 .NET runtime and `DIRECTORY/python.json DIRECTORY/csharp.json` as its arguments, then
run `cross_language.py check` with the same directory. See
[grasshopper/README.md](../../../../grasshopper/README.md) for the complete host
commands and reference paths.

In a fresh Rhino 8 process, run `grasshopper/Tests/accept_rhino.py` through
`RunPythonScript`. It creates the canonical GHX, recomputes, saves and reopens,
and writes temporary host reports. It never changes the original 3dm or old GHX.
`compare_rhino.py` compares the private historical Model with the canonical
export; pass the two filenames and a private report path explicitly.

`receive_canonical_adapter.py` performs only the configured pinned service read.
It uses existing local authentication without printing it. `design_real.py` uses
the captured canonical Model and a declared 300-second execution budget; its
output Models and Runs remain private. Do not include these payloads in Git.
The additional full-size checks use the same wheel:

```sh
PYTHONPATH=/private/tmp/rk-turn3-complete-wheel/site /private/tmp/rk-full-runtime/bin/python docs/research/full-migration/turn3/design_real.py --output /private/tmp/rk-turn3-private/design-solve-310
/private/tmp/rk-turn3-project-venv/bin/python docs/research/full-migration/turn3/design_real.py --output /private/tmp/rk-turn3-private/design-solve-313
```

The 3.13 environment adds the same pinned `pyomo==6.10.1` and `highspy==1.15.1`.
After export, `design_oracle.py <model.json>` independently checks every contributor
and aggregate component, dates, reversion and PV. Its input/output remains private.
The official Windows connector procedure is a separate, still-open gate.

## Documentation and final checks

`build_book.py` takes a fresh temporary book directory, the accepted executed
notebook directory, and the installed Plotly `package_data/plotly.min.js` path.
Run it with the documentation interpreter. It adds offline HTML renderings from
captured Plotly data and builds without reusing cached notebook execution. Copy
the generated HTML and executed notebooks back with `retain_book.py`; no generated
page is edited manually. This is a local build, not publication.

Run `scan_legacy.py`, `verify_evidence.py`, and `git diff --check` in both repositories.
Retain selected final logs as `.txt` because the user's global ignore rules omit
`.log` files. Preserve failed interim logs locally; never label them accepted.
