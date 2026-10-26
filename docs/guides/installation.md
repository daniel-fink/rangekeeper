# Install Rangekeeper

Rangekeeper provides immutable `Model`, `Specification` and `Run` records, Model-backed graph operations, numerical calculations and Pyomo/HiGHS
execution. This guide installs the checked-out source. The current architecture
must not be assumed to match an earlier published PyPI release.

Use Python 3.12 or 3.13. From the repository root:

```sh
python -m pip install .
```

## Choose capabilities

| Extra | Capability |
| --- | --- |
| `bundle` | Candidate schema-derived Parquet IO with PyArrow and DuckDB |
| `yaml` | Strict YAML codecs |
| `calculations` | Financial valuation, Flow operations, distributions, scenario kernels, Polars and CSV |
| `execution` | Pyomo/HiGHS numerical execution |
| `visualisation` | Matplotlib and Plotly plots, plus PyVis graph presentation |

Extras describe installation choices. They do not change the module hierarchy.
Importing `rangekeeper` and its core modules needs no extra. When a feature needs
a missing extra, the `ImportError` names the extra to install, for example
`pip install 'rangekeeper[bundle]'`.
See [upgrading](upgrading.md) for retired extra names.

For the numerical and design examples, run from the repository root:

```sh
python -m pip install '.[calculations,execution,visualisation]' ./examples
```

The separate example distribution supplies `rangekeeper_examples`. Install it from
the same checkout as the library. The Python runtime wheel does not include it.

The local geometry renderer is packaged with RK. Installing or using it does not
run Node or start a service. Source acquisition and application browsing are
consumer responsibilities; the library does not load them.

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
and [verification procedures](../contributing/verification.md). For source
interpretation principles, read [source interpretation](../concepts/source-workflows.md).
