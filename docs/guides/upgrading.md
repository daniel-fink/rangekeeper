# Upgrade to 0.9

This is a breaking ownership change. Install all three owners from the refactor release set.
There are no forwarding modules, deprecated installation extras or automatic schema upgrades.

| Previous import | Current owner and import |
| --- | --- |
| `rangekeeper.adapters.plotting` | RK `rangekeeper.visualisation.chart` |
| `rangekeeper.adapters.presentation` | RK `rangekeeper.visualisation.table` |
| `rangekeeper.adapters.visualization.graph_html` | RK `rangekeeper.visualisation.graph.graph_html` |
| `rangekeeper.adapters.visualization` hierarchy charts | RK `rangekeeper.visualisation.chart` |
| `rangekeeper.adapters.polars` | RK `rangekeeper.io.polars` |
| Canonical Speckle envelope codec | RK `rangekeeper.io.speckle` |
| Workflow and transient Evidence | MCP `whirlwind_mcp.workflow` |
| Excel, document and Speckle source readers | MCP `whirlwind_mcp.sources` |
| Cytoscape projection and graph layout | Viewer `whirlwind_viewer` Python subproject |

Install `Rangekeeper[calculations,visualisation,execution,yaml]` for the walkthroughs.
For scalar CSV output, call `rangekeeper.io.polars.text_frame(table).write_csv(path)`.
Supply read dtypes explicitly. CSV does not preserve a complete canonical Model.

The old Python and C# runtimes, `migration` package and draft schema upgraders are removed.
Current Model, Specification and Run artifacts remain readable. Retained historical source
formats are handled by explicit MCP source readers. Historical evidence and source files
remain in the repository. They do not restore removed APIs.

Generic Grasshopper authoring stays in RK. Source-specific Rhino extraction is the optional
`integrations/rhino` project in MCP. See [Grasshopper](grasshopper.md).
