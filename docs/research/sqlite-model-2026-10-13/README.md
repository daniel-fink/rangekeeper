# Portable SQLite Model proof — 13 October 2026

Update, 13 October 2026: this record predates the agreed
[Model and Geometry Package contract](../../decisions/008-sqlite-model-package.md).
Its one-file experiment and legacy identity gap are retained as historical evidence.
They do not implement or validate the new Model-owned Geometry pin and mappings.
The original results and status below are unchanged; ADR-008 owns the current plan.

Status: bundle 1 locally verified; storage adoption review pending.
[ADR-008](../../decisions/008-sqlite-model-package.md) owns the decision and limits.
[Commands](../../../tools/sqlite_spike/README.md) reproduce the experiment.

## Result

The mixed-use Model and retained Speckle object graph were packaged in one
7,770,112-byte SQLite file. Model reconstruction used generated record tables and
matched the retained canonical document. All geometry record strings matched
the original capture. A new process reopened the copied database after its private
capture/build directory was deleted, with network and original capture reads blocked.

| Check | Observed result |
| --- | --- |
| RK records, including anonymous embedded records | 1,763 |
| Records with canonical UUIDs | 621 |
| Geometry records / canonical associations | 3,007 / 52 |
| Exact reconstruction, including formulations | Mixed-use capture and three canonical Model fixtures pass |
| Presence and scalar cases | Missing, explicit null, empty list, false, integer/float distinction and negative zero preserved |
| Query separation | Object and Assembly membership queries succeed while SQLite denies geometry/document reads |
| Alternate display conversion | Two triangulations, identical vertices and 4 m² area; database bytes and content identity unchanged |
| Physical storage independence | Adding an index changes file bytes without changing content identity |
| Invalid import | Missing geometry, wrong association, wrong revision and detected external asset reject without publication |
| Corrupt package | Missing or altered Model, lookup, geometry and association rows rejected |
| Local tests | 26 passed |
| Formatting | Black check passed on all six Python files |

The conversion check uses a planar quad and is headless. It proves the storage and
conversion boundary, not browser rendering, general BRep tessellation or native
iOS compatibility. The generated `review.html` shows the two triangle layouts.

## Size and timings

The original Model JSON, associations and compressed geometry total 2,765,264
bytes. The final database is about 2.81 times that size. Geometry is compressed per
object rather than as one archive, and relational rows/indexes add overhead.
An initial build duplicated source closure edges in the geometry index; retaining
only direct edges reduced the database from 9,465,856 to 7,770,112 bytes without
changing the content digest. Original source closure declarations remain retained
and validated. No general compression or scale benchmark is claimed.

Warm query medians on this local machine, 25 iterations each:

| Operation | Median |
| --- | --- |
| Page of 25 object IDs | 0.035 ms |
| Page of up to 25 direct members | 0.022 ms |
| One selected object with embedded content | 0.026 ms |
| Largest compressed geometry record, 316,926 raw bytes | 0.465 ms |
| Full Model reconstruction and semantic validation, 3 iterations | 173.336 ms |

Build, validation and copy took 2.412 seconds. These are in-process fixture
measurements, not network latency, browser frame rate or cold-cache performance.
The selected object does not establish large-object inspector performance.

## Stock LinkML finding

Both tested generator settings emitted a 43,782-byte DDL file, but SQLite rejected
`Expression` because it contains `Call_id` and `call_id`. Those names differ only
by case. The generated parent link collides with the declared `call` slot.

- [Generator versions, inputs and outcomes](linkml/result.json)
- [Generated relational SQL](linkml/relational.sql)
- [Captured error](linkml/relational-error.txt)
- [Environment packages](linkml/environment.txt)

The experiment therefore uses a small compiler over RK's generated slot contract.
It retains JSON cells and explicit child/reference links. It does not claim that
stock LinkML produces an accepted production schema or that its failure occurs
in every version/configuration. A generator fix or a reviewed typed mapping remains
an adoption decision.

## Provenance and repeatability

Base RK commit: `c2e4f44e0ddc88f8ea2869ac142c4cf5fed2d937`, with this experiment
uncommitted. Python 3.10.19; SQLite 3.50.4; RK 0.9.0. Stock generator environment:
LinkML and LinkML Runtime 1.11.1; SQLAlchemy 2.0.54. Dependencies were installed
in an isolated temporary environment; root package metadata and lockfile were
not changed by this experiment.

Input: `examples/walkthrough/data/mixed_use_property`, checked against its existing
manifest. The source capture remains unchanged. Model revision:
`37565d7c-f2fb-5ddd-9c4d-e5faacd5c2e0`.

- [Measured result and source hashes](result.json)
- [Generated experiment schema](schema.sql)
- [Test command and result](tests.txt)

The generated local review artifacts are under
`tools/sqlite_spike/output/review-2026-10-13-final/`; this directory is ignored.
The database can be rebuilt from retained repository inputs using the documented
command with a new output directory. Its recorded SHA-256 is
`362f1b7af14a5cf9343afd307a55dc93fb68c0183d3fe90427a6eedf97f55943`.
File bytes are not the Model's semantic identity.

## Open boundaries

Public Model 0.7.0 still excludes geometry. The package content digest pins the
experimental extension; UUID-only consumers must not treat two different geometry
packages as the same complete future Model. Geometry fields and revision enforcement
need the agreed public-contract review.

Bundle 2 is not implemented: bounded component queries, full browser integration,
Payload's native-feature mapping and actual ChatGPT UI exchanges remain open.
No Payload v4 host test was repeated because this bundle changes no host code.
The current v4 migration guide was reviewed; SQLite format independence does not
itself establish integration compatibility. Native iOS, external textures, newer
Speckle formats, hostile-file handling, concurrency and large-model limits are also
outside this local result.
