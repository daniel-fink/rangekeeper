# Upgrade to 0.9

This is a breaking library change. Install the library and examples from the same
reviewed revision.
There are no forwarding modules, deprecated installation extras or automatic schema upgrades.

| Previous import | Current owner and import |
| --- | --- |
| `rangekeeper.adapters.plotting` | RK `rangekeeper.visualisation.chart` |
| `rangekeeper.adapters.presentation` | RK `rangekeeper.visualisation.table` |
| `rangekeeper.adapters.visualization.graph_html` | RK `rangekeeper.visualisation.graph.graph_html` |
| `rangekeeper.adapters.visualization` hierarchy charts | RK `rangekeeper.visualisation.chart` |
| `rangekeeper.adapters.polars` | RK `rangekeeper.io.polars` |
| Canonical Speckle envelope codec | RK `rangekeeper.io.speckle` |

Source readers, workflow orchestration, transient extraction objects and advanced
application browsing are no longer RK APIs. Consumers must supply those features
separately and create canonical records through the public library API.

Install `Rangekeeper[calculations,visualisation,execution,yaml]` for the walkthroughs.
For scalar CSV output, call `rangekeeper.io.polars.text_frame(table).write_csv(path)`.
Supply read dtypes explicitly. CSV does not preserve a complete canonical Model.

The old Python and C# runtimes, `migration` package and draft schema upgraders are removed.
Current Model, Specification and Run artifacts remain readable. Retained historical source
formats require explicit conversion supplied by the consumer. Historical evidence and source files
remain in the repository. They do not restore removed APIs.

Generic Grasshopper authoring stays in RK. Source-specific extraction belongs to
the consumer. See [Grasshopper](grasshopper.md).

## Candidate 0.10 Geometry and Bundle IO

The [Bundle reference](../reference/bundle.md) defines the optional IO and Model
schema 0.8.0. Existing 0.7.0 Models remain readable without implicit migration.
Use `model_07_to_08` for an explicit new identity/predecessor; never rewrite the
old artifact or substitute this candidate for a locked 0.9 environment.
