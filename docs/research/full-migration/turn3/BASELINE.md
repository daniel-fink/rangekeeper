# Turn 3 baseline and acceptance

Verification date: 6 October 2026. **Turn 3 implementation and available local
acceptance are complete.** Official Windows connector acceptance remains open.
This is an uncommitted candidate; no commit,
push, release or external publication was made. The [implementation contract](../../../FULL_MIGRATION_TURN3.md),
[consumer register](CONSUMERS.md) and [Turn 4 removal list](RETIREMENT.md) describe
scope and remaining obligations.

## Starting state and preservation

[baseline.json](baseline.json) records branch, HEAD, dirty paths and tracked-file
hashes for RK `b9de7fc5781ffb0c8f427968d92fcb600fc438c5`, Projects
`5725cc02748ace15e390c8dcea2c5d69185d67c9`, and the read-only layout reference
`4e5aec42f16a18c4d715f5a2a1b879d98e0f71e3`. Fresh baseline results were 971 RK
local tests, six Mandarin tests and six East Whisman tests. These are starting
results, not final acceptance counts.

The user supplied ASD-STE100 reply guidance and the approved implementation plan.
Projects root, Mandarin and East Whisman `AGENTS.md` files also apply. Their
source-preservation and environment-only boundaries were followed: interpretation
stays in YAML, reusable operations live in RK, and archives are not executed.

[preservation-final.json](preservation-final.json) checks 91 protected files:
both pre-existing `.gitignore` edits, the Syncthing lock conflict copy, source
workbooks, archived inputs, original Rhino model and original Grasshopper definition.
All are byte-for-byte unchanged. Private source payloads and generated real-project
Models remain local. Retained comparison reports contain counts and mappings of
representation rules, not copied private payloads or credentials.

## Environments and candidate

[environment-final.json](environment-final.json) records full package versions,
import locations, and schema/fixture/check hashes. Python tests run from RK `src`;
schema tools and Git checks run from the RK root. Notebook kernels run outside the
checkout, with a declared fixture mode and four routine uncertainty scenarios.

| Purpose | Environment |
|---|---|
| RK tests and notebooks | Python 3.10.19, `/private/tmp/rk-full-runtime/bin/python`; NumPy 2.2.6, SciPy 1.15.3, pandas 2.3.2, Polars 1.44.2, Pint 0.24.4, PyXIRR 0.10.7, Pyomo 6.10.1, HiGHS 1.15.1 |
| Schema | `/private/tmp/rk-probe-audit-venv/bin/python`; LinkML 1.11.1, linkml-runtime 1.11.1, jsonschema 4.26.0 |
| Typing | Runtime Python with mypy 1.18.2 via `/private/tmp/rk-record-typecheck` |
| Projects | Python 3.13.11; original independent project environments plus a new isolated `/private/tmp/rk-turn3-project-venv` |
| Viewer | Node 24.15.0, bundled TypeScript/esbuild tests, real Chrome interaction check |
| C# | SDK 10.0.401 builds `net8.0`; Rhino 8.35.26251.13002 supplies .NET runtime 8.0.14 on arm64 Mac |
| Documentation | Jupyter Book 1.0.4.post1, offline HTML and captured notebook outputs |
| Services/layout | SpecklePy 3.0.7; Z3 5.1.0.0; optional MiniZinc absent |

The accepted wheel is `rangekeeper-0.8.71-py3-none-any.whl`, SHA256
`fb083f79d6b3812a908020d5e0cb5ae3c281839a3fd70abe9035138cb3c36a3c`.
It was built once at `/private/tmp/rk-turn3-complete-wheel/wheel/` and used for
installed checks and consumer acceptance. Earlier `final-*` artifacts in this
working session were superseded after a large-report validation issue was found.
The `complete-*` package reports identify the final candidate; the other named
checks retain their accepted evidence. C# and browser binaries did
not change during these Python-only corrections. Broader typing now includes
23 additional workbench, layout and transport modules (168 source files total).

## Results and limits

Final results are indexed in [README.md](README.md). The local suite excludes
`tests/test_api.py` (`test_connection`, `test_model`, `test_conversion`), which
requires the old live service boundary. A separate pinned read verifies the new
adapter. Optional MiniZinc cases are skipped explicitly; Z3 runs locally. The
retained seven warnings concern old pandas frequency aliases in `_legacy_duration`.

The three real source builds and strict separate comparisons preserve quantities,
units, source cells, relationship endpoints, membership and reviewed decisions.
Named changes are explicit unresolved measurements (Mandarin 6, December 2,
November R2 34), Feature-to-property Values, deterministic new Value IDs, enum
wire spelling and canonical unit spelling. No broad category of difference is
ignored. Mandarin's older SOM comparison remains a separate test process.

| Build | Canonical objects (Entities and Assemblies) | Relationships | Source checks |
|---|---:|---:|---|
| Mandarin | 377 | 376 | 776 agree, 14 unavailable, 28 difference |
| East Whisman December | 73 | 72 | 368 agree, 6 unavailable |
| East Whisman November R2 | 37 | 36 | 144 agree, 45 unavailable |

These source-check differences are retained business evidence, not new test
failures. The project bootstrap copies only current specifications, tests,
notebooks, presentation files and original inputs. It uses a newly created
Python 3.13 environment and the wheel, without archives, old outputs or editable
RK imports. Its local typing configuration removes only the sibling source path;
the original configuration is retained alongside it for comparison.

Both design notebooks run in explicit fixture mode. Live acceptance separately
reads pinned object `e7acaac21ae7e9369339900a4aaeb827` in project `c0f66c35e3`, yielding
36 Entities, 14 Assemblies and 63 relationships. The service returns no object
reference for historical version `9a9670946f`; the adapter reports this limitation
and never falls back to latest. The SDK's actual field is `referenced_object`.
No live write or publication was performed.

Rhino checks load the rebuilt components, recompute and reopen the new GHX, and
verify identity and revision lineage. A separate comparison checks quantities,
units, membership and all service relationships against the received historical
design, with an explicit identity map and geometry tolerance (absolute `1e-7`,
relative `1e-10`). C# structural/reference validation is bounded; Python remains
the full semantic acceptance boundary.

Large design execution exposed repeated whole-document scans for each Run evidence
reference. The fix builds the reference identity index once per revision within
one validation call. It does not share caches between calls or change checks.
A new negative test verifies that repeated references cannot borrow identity from
another revision. The real design check records stage timing separately from the
solver's explicit 300-second budget. A profiled Python 3.10 process then hit a
native allocator crash during a repeated validation after returning a feasible
Run. [The bounded crash report](large-model-runtime-crash.json) records the phase
without private data. Unprofiled 3.10 and 3.13 runs both pass, including repeated validation and export.
The native crash was not reproduced; its cause remains unproven. The large checks
used the preceding wheel, whose complete execution/core files are byte-identical
to the final wheel ([comparison](large-model-wheel-equivalence.json)). The final
wheel independently checks all 4,541 output quantities against explicit arithmetic.
These timings include authoring and repeated validation outside the solver budget;
this is functional acceptance, not an interactive-performance claim.

The documentation build uses freshly executed notebooks, no old execution cache.
It converts captured Plotly MIME data into HTML with a local JavaScript asset,
because Jupyter Book 1 does not render that MIME type. It does not rerun or alter
mathematics. The walkthrough ignore rules now retain the generated HTML assets
and seven executed notebooks while excluding build caches; the unrelated root
ignore edits remain unchanged. The component cashflow PNG was visually inspected for dates, units,
signs and the two capital-payment dips. The browser policy blocked a local-file
preview, so no claim of a fresh in-app HTML preview is made. Viewer interaction
acceptance uses the separately recorded browser test.

The **Windows official connector gate remains open**. It requires an available
Windows host and an approved publication destination. Offline fixtures and Mac
Rhino acceptance cannot close it. See the [procedure](../../../../grasshopper/WINDOWS_DEVELOPMENT.md)
and [official installation requirements](https://docs.speckle.systems/connectors/installation).
MiniZinc is an additional optional-environment limitation. Hypar is retired;
Browser/outliner remains on hold. Retained old code is governed by the removal
register, not by an assumption that all external consumers are accepted.

## Reproduction

[COMMANDS.md](COMMANDS.md) lists commands and output locations. [checks/commands.jsonl](checks/commands.jsonl)
retains the seven schema invocations, versions and durations. The reports distinguish
initial setup failures (cache permissions, copied typing path, unsupported Plotly
MIME and historical service version availability) from the corrected final checks.
Do not execute project archives or publish real payloads while reproducing them.
