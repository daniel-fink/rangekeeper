# Document conversion to 1.0.0

This one-off tool converts stored 0.x documents and Bundles to the 1.0.0 formats
([#120](https://github.com/daniel-fink/rangekeeper/issues/120)). It is in the
repository, not in the wheel. The other route is to rebuild the documents from
their source pipelines; see the [upgrade guide](../../docs/guides/upgrading.md#document-formats-100).

## What it converts

The inputs are the formats that the 0.9 and 0.10 lines and 1.0.0a1 write:

| Document | Input formats | Output format |
| --- | --- | --- |
| Model | 0.7.0, 0.8.0 | 1.0.0 |
| Specification | 0.7.0 | 1.0.0 |
| Run | 0.4.0 | 1.0.0 |

The tool changes only what the 1.0.0 formats change:

| Change | Issue |
| --- | --- |
| `metadata.schema_version` becomes `1.0.0` | [#118](https://github.com/daniel-fink/rangekeeper/issues/118) |
| Period and Span `start_inclusive` and `end_exclusive` become `start` and `end` | [#119](https://github.com/daniel-fink/rangekeeper/issues/119) |
| `Specification.policy` becomes `rules`, and `Report.outcomes` becomes `rule_evidence` | [#95](https://github.com/daniel-fink/rangekeeper/issues/95) |
| A magnitude in ISO 4217 currency units, such as `AUD`, becomes the canonical text of its amount, at 15 significant digits (`0.30000000000000004` becomes `"0.3"`) | [#117](https://github.com/daniel-fink/rangekeeper/issues/117), [ADR-023](../../docs/decisions/023-decimal-money.md) |
| A query `Filter` with a `classification`, and each Label `Criterion`, gets `exclusive: true`. The 0.x formats matched them exactly; 1.0.0 also matches sub-types unless `exclusive` is true | [#121](https://github.com/daniel-fink/rangekeeper/issues/121) |

Everything else stays the same:

- **Identities.** Each document keeps its UUID and its `previous` lineage, so a
  Specification still pins its Model and a Run still names its documents. Put
  the converted documents in a new store or Bundle, never in the store that
  holds the originals: the same UUID with other content is a revision conflict.
- **Evidence.** Claim content is opaque evidence. It stays as the old version
  recorded it, including old field names. Run implementation fingerprints also
  stay as recorded.
- **Code.** The renames of Python names in
  [`rename_map.yaml`](../codemod/rename_map.yaml) change code, not data. Use the
  [codemod](../codemod/README.md) for them.

The tool checks each converted document as the 1.0 readers do. It does not
convert a document that is already 1.0.0 or that has another version.

## Use

From the repository root, with the locked environment:

```sh
uv sync --all-extras --locked
```

Convert JSON or YAML documents. Each output keeps its file name and format. The
tool finds the kind from the shape: a Run has a `report`, a Specification has a
`model` pin, and anything else is a Model.

```sh
uv run python -m tools.upgrade documents old/model.json old/spec.yaml old/run.json --output converted
```

Convert a Bundle into a new Bundle. The tool reads the old Parquet tables with
the 1.0.0a1 slot map ([`legacy_slots.json`](legacy_slots.json)), checks their
file hashes, converts each document and writes the new Bundle with
`rangekeeper.io.bundle.write`. Native Geometry files are copied from the old
Bundle.

```sh
uv run python -m tools.upgrade bundle old-bundle new-bundle
```

The tool never writes over an existing file or Bundle, and it never changes its
inputs.

## Tests

[`tests/samples`](tests/samples) holds documents and a Bundle that the published
1.0.0a1 package wrote: an investment Model with currency Flows, a Specification
with a policy, the feasible Run and its output Model. The tests convert them and
validate the Run against the converted documents.

```sh
uv run pytest tools/upgrade/tests
```
