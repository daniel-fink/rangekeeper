# Architecture after the 0.9 ownership split

Rangekeeper owns immutable canonical Model, Specification and Run contracts, identity,
provenance, validation, units, calculations and execution. `io` owns native serialization,
stores, Polars conversion and the canonical Speckle envelope. `visualisation` owns simple
local chart, table, PyVis graph and retained geometry display. Importing RK core does not
load an ingestion engine, source reader, browser or service client.

Whirlwind MCP owns acquisition, source interpretation, transient Evidence, recipes,
workspace decisions, ingestion builds and optional Rhino source extraction. Whirlwind
Viewer owns advanced browsers and graph layout, and builds the pinned local geometry
asset distributed with RK. RK imports neither Whirlwind Python package.

The portable C# Model library and generic Grasshopper authoring components stay in RK.
Generated canonical record and envelope definitions have one authority in RK. The
source-specific Grasshopper component is in MCP and consumes the pinned RK assemblies.

See [the decision](../decisions/007-three-repository-refactor.md),
[upgrade paths](../guides/upgrading.md), and [Grasshopper](../guides/grasshopper.md).

The agreed [Model and Speckle Package contract](../decisions/008-sqlite-model-package.md)
pairs one immutable Model with one exact native Speckle bundle. The Model owns the
bundle pin and mappings; changing either side or the mappings creates a new Model
and Package. Source data stays adjacent to RK data, while rendering belongs to the
interface. SQLite remains a candidate RK store, not a requirement that the entire
Package be one database file. The earlier development experiment is historical
evidence; the installed IO API and public Model schema have not adopted this contract.
