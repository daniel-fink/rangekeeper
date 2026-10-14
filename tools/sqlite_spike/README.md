# Portable Model SQLite experiment

This is the earlier development experiment, not an installed RK API or a
conforming implementation of the agreed Model/Geometry Package contract. Read
[ADR-008](../../docs/decisions/008-sqlite-model-package.md) for that contract,
its implementation steps and the historical mapping. The prototype still allows
different geometry under one legacy Model UUID. The new contract forbids this.
No public RK schema fields are changed here.

From the Rangekeeper repository root, use its development environment. The core
prototype uses RK and Python's standard library. Tests also use pytest and PyYAML.

```sh
.venv/bin/python -m pytest tools/sqlite_spike/test_package.py -q --confcutdir=tools/sqlite_spike
.venv/bin/python tools/sqlite_spike/verify.py --output tools/sqlite_spike/output/my-review
.venv/bin/python tools/sqlite_spike/verify.py --inspect tools/sqlite_spike/output/my-review/mixed-use.rk.sqlite
```

Choose a new output directory for each run. The tool does not overwrite existing
outputs. `output/` is ignored. The build uses the checked-in
[mixed-use capture](../../examples/data/mixed_use_property);
it copies only the finished database to the review directory, removes its temporary
capture/build location and verifies in a fresh process. That process blocks network
access and reads of the original capture. No source service or Payload is started.

Outputs include the mixed-use database, a small planar-quad database, generated
SQL, measured results and `review.html`. Open the HTML to compare two triangle
layouts produced from the same stored quad. This is a headless conversion proof;
it does not test WebGL or iOS. `result.json` records source hashes, environment,
query timings and remaining limits.

## Stock generator assessment

Use a separate temporary virtual environment so LinkML does not become an RK
runtime dependency. Install the repository's pinned schema requirements there:

```sh
.venv/bin/python -m venv /tmp/rk-sqlite-schema-env
/tmp/rk-sqlite-schema-env/bin/python -m pip install -r tools/schema/requirements.txt
/tmp/rk-sqlite-schema-env/bin/python tools/sqlite_spike/probe_linkml.py --output /tmp/rk-sqlite-generator-result
```

The probe records dependency versions, input schema hashes, generated DDL and
SQLite acceptance/errors. It checks both default relational and direct-mapping
settings. Read its result before selecting a production generator.

## Query example

From `tools/sqlite_spike`, with the repository environment active:

```python
from package import Reader

with Reader("output/my-review/mixed-use.rk.sqlite") as reader:
    reader.verify()  # Full scan before trusting a newly received package.
    rows = reader.objects(limit=25)
    record = reader.object(rows[0]["canonical_id"])
    print(record)
```

The Model reconstructs from the generated record tables. The original document is
retained for independent comparison. SQL NULL and JSON `null` have different
meanings. For example, `json_extract(name, '$')` reads an Entity name, while
`name IS NULL` identifies absence and `name = 'null'` identifies explicit null.

Geometry records are individually compressed and loaded only when requested.
Renderer caches belong outside the immutable file. The prototype's content digest
includes geometry; its legacy Model UUID alone does not yet identify that geometry.

Do not point Payload's schema push/migrations at these files. There is no HTTP/MCP
query service, public schema migration, permission model or native viewer adapter
in this earlier experiment.
