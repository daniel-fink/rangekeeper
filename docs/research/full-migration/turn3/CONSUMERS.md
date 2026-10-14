# Turn 3 consumer register

Starting points: RK `b9de7fc`, Projects `5725cc0`, layout reference `4e5aec4`.
The source and preservation inventory is in `baseline.json`. Original source
workbooks, archived files, and received design data remain outside this evidence
folder. This register distinguishes planned replacements from accepted consumers.

| Consumer | Existing dependency | Replacement and supported behavior | Environment and acceptance | Retirement gate |
|---|---|---|---|---|
| Mandarin source build | Workflow v1, Graph, Features, old codec and provenance | Workflow v2, canonical Model, property Values, explicit quantity keys; same source interpretations, decisions and findings | Project Python 3.13, original local workbooks, strict historical comparison | Real build, project tests and semantic comparison |
| Mandarin review notebook | Reference-branch workbench and layout profile v2 | Canonical workbench, profile v3, separate failed attempts and saved-layout bundles | Fresh project kernel; wheel bootstrap; local browser | Notebook, integrity and interaction checks |
| East Whisman December | Workflow v1 and Graph | Separate canonical December Model; original square-foot quantities and missingness | Python 3.13, original workbook, independent comparison | Build and source-scope tests |
| East Whisman November R2 | Workflow v1 and Graph | Separate canonical November Model; only reviewed shared identities | Same environment; separate comparison | Build and source-scope tests |
| Layout reference branch | Old Graph objects, Features and Measure selection | Detached layout Problems from Models; explicit property and quantity selectors | Geometry, saved-layout, browser, optional Z3/MiniZinc checks | Feature-by-feature port acceptance; no old-domain merge |
| Design loading walkthrough | `rk.api.Speckle`, mutable Entity/Assembly reconstruction | Explicit receive or fixture load, canonical envelope decode or named legacy conversion, Model-backed View | Installed wheel; explicit fixture/live mode; pinned live source | Offline and live read, identity and mapping tests |
| Design financial walkthrough | Legacy numerical modules and class patching | Explicit financial declarations, Specification, execution and reporting | Installed wheel and independent component/timing/PV oracle | Full notebook and accepted output provenance |
| Grasshopper example | Rhino 7/net48, Speckle-inherited objects and old components | LinkML-derived C# wire records, connector-independent authoring and Rhino 8 components | .NET 8 on Mac; cross-language round trip; Rhino load and recompute | Pure tests plus local host acceptance |
| Current official Speckle connector | External Windows host integration | Canonical envelope and explicit geometry association contract | Approved destination and Windows host required | Separate Windows publication/receive gate; remains open without host |
| Five numerical walkthroughs | Already migrated at Turn 2 checkpoint | Retain duration, Movement, calculations, market and policy APIs | Same final candidate wheel as other consumers | Regression execution |
| Executable examples and guides | Mixed current and historical examples | Current public APIs; generated documentation rebuilt from sources | Outside-checkout example execution and source import scan | No unexplained active legacy imports |
| Hypar | Historical design integration files | Retired from supported consumers; historical files preserved | No current acceptance claim | Historical retention only |
| Browser/outliner | Future importer, already on hold | No implementation in this turn | Not part of legacy consumer acceptance | Hold unchanged |

## Acceptance status

The final candidate wheel and raw results are indexed in [BASELINE.md](BASELINE.md)
and [README.md](README.md). All named local consumer paths have implementation
and acceptance evidence. The reference layout features run with Models; Z3 is
accepted and MiniZinc remains an optional host gap. The new Python adapter has a
pinned live read; the two design notebooks use declared fixtures for routine runs.
Mac Rhino recompute, identity, revision and semantic comparison pass. The official
Windows connector publication/receive row remains open and holds its predecessor
retirement group. No compatibility claim is made for unknown downstream callers.

