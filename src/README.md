# Rangekeeper

[Record methods and immutable replacement](../docs/RECORD_BOUNDARY.md) describes the current
Flow, Movement, Period, Distribution, alignment and account APIs.

Rangekeeper provides immutable `Model`, `Specification` and `Run` records, explicit
source workflows, Model-backed graph operations, numerical calculations and
Pyomo/HiGHS execution. LinkML owns persistent fields. Codecs and revision stores
preserve identity, provenance, ordered mathematics and missing values.

The current migration is on `acausal-modelling`; these changes are not yet a PyPI
release. See the [architecture](../docs/LIBRARY_ARCHITECTURE.md),
[upgrade guide](../docs/LEGACY_UPGRADE_GUIDE.md) and
[verification guide](../docs/VERIFICATION.md).

## Installation

Run installation commands from this `src` directory. Core installation is:

```sh
pip install .
```

Choose extras for the operations you use:

| Extra | Capability |
|---|---|
| `yaml` | Strict YAML codecs |
| `workflow` or `excel` | Source workflows, Excel reading, workbench and HTML review |
| `financial` | PyXIRR valuation, IRR and day-count calculations |
| `calculations` | Known-data Flow operations, probability distributions and scenario kernels |
| `execution` | Pyomo/HiGHS numerical execution |
| `tables` | Detached Polars and CSV adapters |
| `plotting` | Matplotlib Flow plots and Plotly presentation |
| `visualization` | PyVis and Plotly graph presentation |
| `speckle` | Explicit Speckle receive operations |
| `layout` | Optional Z3 presentation layout solver |
| `legacy` | Temporary `rangekeeper.legacy` Graph/Measure/Speckle group; see the open Windows gate |

For example, the numerical and design walkthroughs require:

```sh
pip install '.[calculations,execution,tables,plotting,visualization,workflow]'
```

The bundled Cytoscape viewer and constructive layouts need no Node.js or solver
at runtime. MiniZinc layout support needs a separately installed executable.
Core imports do not load dataframes, plotting libraries, service SDKs or solvers.
The old `flux`, numerical root modules and class-patching helper have been removed;
there are no aliases. Historical wire conversion remains under `migration`.

## Development and verification

Use Python 3.10–3.13. The development group contains test/format tools; runtime
extras remain explicit. From this directory:

```sh
uv sync --all-extras --group dev --locked
uv run pytest --ignore=tests/legacy/test_api.py
```

The excluded module contains three old live-service tests. It is not part of
local acceptance. Optional MiniZinc tests skip when that executable is absent.
Use `--show-plots` only for an interactive Matplotlib test session.

Schema generation uses the separate pinned LinkML tool environment. See
[verification commands](../docs/VERIFICATION.md) for
schema, typing, installed-wheel, notebook and project acceptance.

## Source workflows

Use `rangekeeper.workflow` with reviewed `WorkflowSpec` documents. It returns a
canonical Model; export and storage are explicit. Workflow configuration is
separate from the mathematical Specification consumed by execution.

See the [consumer guide](../docs/CONSUMER_MIGRATION.md),
[Run and storage guide](../docs/RUN_AND_STORAGE.md) and
[synthetic source examples](examples/workflow/README.md).
