# Upgrade to 0.9

This is a breaking library change. Install the library and examples from the same
reviewed revision.
There are no forwarding modules, deprecated installation extras or automatic schema upgrades.

| Previous import | Current owner and import |
| --- | --- |
| `rangekeeper.adapters.plotting` | Walkthrough helper `helpers.chart` |
| `rangekeeper.adapters.presentation` | RK `Stream.display()` and `Pivot.display()`, in `rangekeeper.model.display` |
| `rangekeeper.adapters.visualization.graph_html` | Walkthrough helper `helpers.graph.graph_html` |
| `rangekeeper.adapters.visualization` hierarchy charts | Walkthrough helper `helpers.chart` |
| `rangekeeper.adapters.polars` | RK `rangekeeper.io.polars` |
| Canonical Speckle envelope codec | Walkthrough helper `helpers.speckle` |
| `rangekeeper.visualisation.*` and the `visualisation` extra (1.0) | Walkthrough helpers in [`examples/walkthrough/helpers`](../../examples/walkthrough/README.md); table display is `Stream.display()` |

Source readers, workflow orchestration, transient extraction objects and advanced
application browsing are no longer RK APIs. Consumers must supply those features
separately and create canonical records through the public library API.

Use the [walkthrough environment](walkthroughs.md#explore-the-lessons) for the walkthroughs.
For scalar CSV output, call `rangekeeper.io.polars.text_frame(table).write_csv(path)`.
Supply read dtypes explicitly. CSV does not preserve a complete canonical Model.

The old Python and C# runtimes, `migration` package and draft schema upgraders are removed.
Current Model, Specification and Run artifacts remain readable. Retained historical source
formats require explicit conversion supplied by the consumer. Historical evidence and source files
remain in the repository. They do not restore removed APIs.

Generic Grasshopper authoring stays in RK. Source-specific extraction belongs to
the consumer. See [Grasshopper](grasshopper.md).

## Classification filters include sub-types

`View.filter(entity_classification=id)` and `relationship_classification=id` now
include the Classification's sub-types. Pass `exclusive=True` to keep the earlier
exact match. `Model.find_entities(classification=id)` still matches exactly. See
[ADR-009](../decisions/009-classification-sub-types.md).

## Geometry and Bundle IO

The [Bundle reference](../reference/bundle.md) defines the optional IO and Model
schema 0.8.0. Existing 0.7.0 Models remain readable without implicit migration.
Use `model_07_to_08` for an explicit new identity/predecessor; never rewrite the
old artifact or substitute this version for a locked 0.9 environment.
