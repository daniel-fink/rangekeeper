# Notebook-facing API acceptance — 2026-10-08

Source: `acausal-modelling` at `b150927`, plus the API changes identified by
[changed Python source hashes](api-source-files.json). Flow display shares the
Stream renderer and does not alter record content. Projection calculations are
named `extrapolate` and `distribute`; `project_values` remains the numeric helper.
The two retired Flow-producing function names have no compatibility aliases.

Local checks used Python 3.10.19 on macOS:

- [Full suite](pytest-api.txt): **1,481 passed, 24 skipped**. The held live-service
  module `src/tests/legacy/test_api.py` was excluded. Missing optional engine skips
  do not establish strict layout, Windows or service acceptance.
- [Typing](typing.txt): 215 valid files plus the seven expected invalid-fixture
  groups passed. [Python generation](schema.txt): six artifacts and 72 classes
  remain current; no persistent schema fields changed.
- [Isolated wheel checks](installed-wheel.txt): records, stores, financial,
  execution, workflow, Polars/CSV, Flow display, projection verbs and acausal
  Stream examples passed. The table slice has no pandas installation.
- Documentation checks passed: 65 pages and routes to 39 current pages.

The clean staged wheel is `rangekeeper-0.8.71-py3-none-any.whl`, SHA-256
`debf952a8d81f68bfcd6ff69146911326b0ae39abce2a5e7603a6af5027632c9`. It was built outside the checkout and was not published.
Notebook execution and rendered acceptance are recorded separately after this
codebase checkpoint.

Commands (repository root):

```sh
MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/rangekeeper-acausal-mpl .venv/bin/python -m pytest -q --ignore=src/tests/legacy/test_api.py
PYSTOW_HOME=/private/tmp/rk-005-pystow /private/tmp/rk-005-schema/bin/python tools/schema/generate.py --check
PYSTOW_HOME=/private/tmp/rk-005-pystow /private/tmp/rk-005-schema/bin/python tools/schema/typecheck.py
.venv/bin/python tools/docs/check.py
```

The wheel checker used `tools/schema/verify_install.py --wheel` with the artifact
above and its runtime, execution, workflow, financial and table interpreter
options pointing at the root `.venv/bin/python`.
