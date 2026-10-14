# Turn 4 reproduction commands

Run from `/Volumes/Data/Projects/Rangekeeper` unless a command states another
working directory. Use fresh temporary destinations when repeating the checks.
`commands.jsonl` retains exact commands for the executed checks. `baseline.json`
and `environment-final.json` record installed versions and import locations.
Private historical bundles and original workbooks are local prerequisites for
real-source comparison; they are not included in this repository.

## Core regression, schema and typing

```sh
# cwd: /Volumes/Data/Projects/Rangekeeper/src
MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/rk-turn4-mpl PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python -m pytest -q --ignore=tests/test_api.py --junitxml=../docs/research/full-migration/turn4/full-suite.xml

# cwd: /Volumes/Data/Projects/Rangekeeper
PYSTOW_HOME=/private/tmp/rk-domain-migration-pystow /private/tmp/rk-probe-audit-venv/bin/python tools/schema/generate.py --check
PYSTOW_HOME=/private/tmp/rk-domain-migration-pystow /private/tmp/rk-probe-audit-venv/bin/python tools/schema/generate_csharp.py --check
PYTHONPATH=/private/tmp/rk-record-typecheck /private/tmp/rk-full-runtime/bin/python tools/schema/typecheck.py
/private/tmp/rk-full-runtime/bin/python docs/research/full-migration/turn4/audit_retirement.py
```

Run each of `schema/checks/validate.py`, `native_roundtrip.py`, `expressions.py`,
`formulations.py`, `models.py`, `specifications.py`, and `runs.py` with
`/private/tmp/rk-probe-audit-venv/bin/python` and the same `PYSTOW_HOME`. That
interpreter has LinkML 1.11.1, runtime 1.11.1 and jsonschema 4.26.0. Each harness
isolates its generated artifacts. These checks do not execute a solver.

The captured numerical fixture can only be regenerated from the frozen checkpoint
`305f3ff` in an isolated historical checkout. `capture_reference.py` records its
source hashes. Do not restore retired modules into the candidate to run tests.

## Build one wheel and verify installed operations

```sh
/private/tmp/rk-probe-audit-venv/bin/python docs/research/full-migration/turn1/build_notebook_environment.py --output /private/tmp/rk-turn4-wheel
/private/tmp/rk-full-runtime/bin/python tools/schema/verify_install.py --wheel /private/tmp/rk-turn4-wheel/wheel/rangekeeper-0.8.71-py3-none-any.whl --runtime-python /private/tmp/rk-full-runtime/bin/python --execution-python /private/tmp/rk-full-runtime/bin/python --workflow-python /private/tmp/rk-full-runtime/bin/python --financial-python /private/tmp/rk-full-runtime/bin/python
```

Create an empty Python 3.10 venv for core checks and a Python 3.13 venv for Projects.
Install the wheel normally, not with `--no-deps`. The executed install commands
and pinned test/notebook tool versions are in `commands.jsonl`. For the core use
no extras; for Projects use `[workflow,excel]`. Clear `PYTHONPATH` for both.
`verify_core.py` checks real model/unit/store operations and optional-library absence.

## Seven walkthroughs, guide and documentation

```sh
/private/tmp/rk-full-runtime/bin/python docs/research/full-migration/turn3/run_walkthroughs.py /private/tmp/rk-turn4-wheel/site /private/tmp/rk-turn4-notebooks
# cwd: /private/tmp
PYTHONPATH=/private/tmp/rk-turn4-wheel/site /private/tmp/rk-full-runtime/bin/python /Volumes/Data/Projects/Rangekeeper/docs/research/full-migration/turn3/guide_example.py
```

The walkthrough runner checks wheel import paths in every fresh kernel, uses
explicit fixture mode, declares four scenarios and one worker, and saves outputs
and PNGs. It uses a shared temporary kernel specification: finish it before
running the Mandarin notebook with a different interpreter. Execute both
`src/docs/examples/ingestion_evidence.py` and `excel_ingestion.py` with the same
wheel-first environment from `/private/tmp`. They use synthetic workbook data.

```sh
# cwd: /Volumes/Data/Projects/Rangekeeper
/private/tmp/rk-turn3-docs-venv/bin/python docs/research/full-migration/turn3/build_book.py /private/tmp/rk-turn4-book-final /private/tmp/rk-turn4-notebooks /Volumes/Data/Projects/Rangekeeper/src/.venv/lib/python3.10/site-packages/plotly/package_data/plotly.min.js
/private/tmp/rk-full-runtime/bin/python docs/research/full-migration/turn3/retain_book.py /private/tmp/rk-turn4-book-final /private/tmp/rk-turn4-notebooks /private/tmp/rk-turn4-pre-book
```

Resolve the installed Plotly asset path on a different machine. Book building
uses the captured outputs, converts Plotly MIME for Jupyter Book 1, and loads no
old execution cache. Retention backs up previous generated output first. It does
not edit source notebooks or publish the site. Inspect representative PNGs for
units, dates, signs, capital-payment timing and policy/hindsight labels.

## Real projects

```sh
/private/tmp/rk-full-runtime/bin/python docs/research/full-migration/turn3/bootstrap_projects.py prepare --root /private/tmp/rk-turn4-project-bootstrap
/private/tmp/rk-turn4-project-venv/bin/python docs/research/full-migration/turn4/verify_projects.py build
/private/tmp/rk-turn4-project-venv/bin/python docs/research/full-migration/turn4/verify_projects.py tests
/private/tmp/rk-turn4-project-venv/bin/python docs/research/full-migration/turn4/verify_projects.py compare
```

Each project command runs from its copied project directory. The strict comparator
reads the frozen baseline under `/private/tmp/rk-turn3-private/baseline` only after
new builds finish. It never supplies build inputs. `source-hashes.json` records
copied originals. Run the separate SOM comparison with `MANDARIN_REFERENCE` set
to its historical reference bundle and `MANDARIN_CANDIDATE` set to the new successful
Mandarin attempt directory. Exact paths for this run are in `commands.jsonl`.

```sh
# cwd: /private/tmp/rk-turn4-project-bootstrap/mandarin
/private/tmp/rk-turn4-project-venv/bin/python /Volumes/Data/Projects/Rangekeeper/docs/research/full-migration/turn2/run_notebook.py notebooks/01_workflow_review.ipynb /private/tmp/rk-turn4-project-bootstrap/mandarin-review.ipynb --cwd /private/tmp/rk-turn4-project-bootstrap/mandarin
```

Both independent project locks and RK's lock must pass `uv lock --check --offline`
from their own directories. Do not sync or replace the user's project environments
as part of this isolated acceptance. No archive is executed.

## Cross-language, host and final preservation

Use `turn3/cross_language.py prepare` with the wheel-first Python environment and
a fresh output directory. Run `grasshopper/Tests/bin/Debug/net8.0/Tests.dll` with
Rhino's installed arm64 .NET runtime and the `python.json`/`csharp.json` paths;
then run `cross_language.py check`. The exact runtime and arguments are logged.
C# sources are unchanged; generation freshness passes. Validate the captured Mac
Model and canonical envelope with this wheel and require equal detached content.
This revalidates the export; it is not a new Rhino UI recomputation.

Run `verify_final.py` after documentation and generated output retention. It checks
protected hashes, schema/fixture hashes, checkpoint state, empty Git indexes,
source/wheel equality, unchanged canonical runtime and C# files, and fresh notebook
outputs. The Windows connector procedure remains a separate open gate.
