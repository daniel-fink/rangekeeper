# Install Rangekeeper

Rangekeeper provides immutable `Model`, `Specification` and `Run` records, source
workflows, Model-backed graph operations, numerical calculations and Pyomo/HiGHS
execution. This guide installs the checked-out source. The current architecture
must not be assumed to match an earlier published PyPI release.

Use Python 3.10–3.13. From the repository root:

```sh
python -m pip install .
```

## Choose capabilities

| Extra | Capability |
| --- | --- |
| `yaml` | Strict YAML codecs |
| `workflow` | Source workflows, Excel reading, workbench and HTML review |
| `calculations` | Financial valuation, Flow operations, distributions, scenario kernels, Polars and CSV |
| `execution` | Pyomo/HiGHS numerical execution |
| `visualization` | Matplotlib and Plotly plots, plus PyVis graph presentation |
| `speckle` | Explicit Speckle receive operations |
| `layout` | Optional Z3 presentation layout solver |
| `legacy` | Held predecessor Graph/Measure/Speckle group; see [retirement](../contributing/legacy-retirement.md) |

Extras describe installation choices. They do not change the module hierarchy.
See [upgrading](upgrading.md#installation-extra-migration) for retired extra names.

For the numerical and design examples, run from the repository root:

```sh
python -m pip install '.[calculations,execution,visualization,workflow]' ./examples
```

The separate example distribution supplies `rangekeeper_examples`. Install it from
the same checkout as the library. The Python runtime wheel does not include it.

The bundled Cytoscape viewer and constructive layouts need no Node.js or solver
at runtime. MiniZinc requires a separately installed executable; the `layout`
extra does not install it. See [layout acceptance](../contributing/layout-acceptance.md)
for the pinned toolchain. Core imports do not load dataframe, plotting, service
SDK or solver dependencies.

## Use the installed library

Import the three document roots from `rangekeeper`. Use explicit capability paths
for other operations:

```python
from rangekeeper import Model, Specification, Run
from rangekeeper.model import formulation
from rangekeeper.run import execution
from rangekeeper.shared.table import Table, Row
```

The [architecture](../concepts/architecture.md) owns the package map. Read the
[record reference](../reference/records.md) for immutable replacement and intrinsic
operations, the [examples guide](examples.md) for runnable sources, and
[upgrading](upgrading.md) for removed imports and explicit wire conversion.

For development, use the [contributor environment](../contributing/README.md#development-environment)
and [verification procedures](../contributing/verification.md). For reviewed
source configurations, use [source workflows](source-workflows.md).
