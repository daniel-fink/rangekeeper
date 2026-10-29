# Document conversion to 1.0.0

This one-off tool converts the stored documents and Bundles of earlier releases
to the current formats
([#120](https://github.com/daniel-fink/rangekeeper/issues/120),
[#386](https://github.com/daniel-fink/rangekeeper/issues/386)). It is in the
repository, not in the wheel. The other route is to rebuild the documents from
their source pipelines; see the upgrade guide for
[0.x documents](../../docs/guides/upgrading.md#document-formats-100) and for
[1.0.0a2 documents](../../docs/guides/upgrading.md#stored-query-filters).

## What it converts

`--from` names the release that wrote the input. A 1.0.0 document does not
record the release that wrote it, so the tool cannot find it from the data.

| `--from` | Release that wrote the input | Model | Specification | Run |
| --- | --- | --- | --- | --- |
| `0.x` (default) | the 0.9 and 0.10 lines and 1.0.0a1 | 0.7.0, 0.8.0 | 0.7.0 | 0.4.0 |
| `1.0.0a2` | 1.0.0a2 | 1.0.0 | 1.0.0 | 1.0.0 |

The output formats are all 1.0.0.

### From 0.x

The tool changes only what the 1.0.0 formats change:

| Change | Issue |
| --- | --- |
| `metadata.schema_version` becomes `1.0.0` | [#118](https://github.com/daniel-fink/rangekeeper/issues/118) |
| Period and Span `start_inclusive` and `end_exclusive` become `start` and `end` | [#119](https://github.com/daniel-fink/rangekeeper/issues/119) |
| `Specification.policy` becomes `rules`, and `Report.outcomes` becomes `rule_evidence` | [#95](https://github.com/daniel-fink/rangekeeper/issues/95) |
| A magnitude in ISO 4217 currency units, such as `AUD`, becomes the canonical text of its amount, at 15 significant digits (`0.30000000000000004` becomes `"0.3"`) | [#117](https://github.com/daniel-fink/rangekeeper/issues/117), [ADR-023](../../docs/decisions/023-decimal-money.md) |
| A query `Filter` with a `classification`, and each Label `Criterion`, gets `exclusive: true`. The 0.x formats matched them exactly; 1.0.0 also matches sub-types unless `exclusive` is true | [#121](https://github.com/daniel-fink/rangekeeper/issues/121) |

### From 1.0.0a2

The format version stays 1.0.0. The tool changes one meaning: a query `Filter`
with a `classification`, and each Label `Criterion`, gets `exclusive: true`.
1.0.0a2 matched them exactly; later releases also match sub-types unless
`exclusive` is true ([#121](https://github.com/daniel-fink/rangekeeper/issues/121)).
A Bundle that 1.0.0a2 wrote pins the 1.0.0a2 slot map
([`alpha2_slots.json`](alpha2_slots.json)), so the current Reader does not
open it; the tool reads it with that map.

Convert only the documents that 1.0.0a2 wrote. In a later document, a Filter
without `exclusive` asks for sub-types, and the conversion would make it exact.
No release before #121 wrote `exclusive`, so the tool refuses a document with
a Filter or Criterion that has it.

### What stays the same

Date Values (`ValueKind.DATE`, with `date` or `never`) and the `date` and `never`
Expression literals are new in 1.0.0
([#280](https://github.com/daniel-fink/rangekeeper/issues/280)). The 0.x formats
have no date kind, so the tool adds nothing for them. A 0.x property Value with
date content stays a property Value; declare a date Value to use it in equations.

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
convert a document whose format the `--from` release does not write.

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
uv run python -m tools.upgrade documents --from 1.0.0a2 alpha/model.json --output converted
```

Convert a Bundle into a new Bundle. The tool reads the old Parquet tables with
the slot map of the release that wrote them: the 1.0.0a1 slot map
([`legacy_slots.json`](legacy_slots.json)) for 0.x, or the 1.0.0a2 slot map
([`alpha2_slots.json`](alpha2_slots.json)). It checks the schema pin and the
file hashes, converts each document and writes the new Bundle with
`rangekeeper.io.bundle.write`. Native Geometry files are copied from the old
Bundle.

```sh
uv run python -m tools.upgrade bundle old-bundle new-bundle
uv run python -m tools.upgrade bundle --from 1.0.0a2 alpha-bundle new-bundle
```

The tool never writes over an existing file or Bundle, and it never changes its
inputs.

## Tests

[`tests/samples`](tests/samples) holds documents and a Bundle that the published
1.0.0a1 package wrote: an investment Model with currency Flows, a Specification
with a policy, the feasible Run and its output Model. The tests convert them and
validate the Run against the converted documents.

[`tests/samples/1.0.0a2`](tests/samples/1.0.0a2) holds a Model and its Bundle
that the published 1.0.0a2 package wrote, with a query Filter that has a
classification and a Label Criterion. Its `build.py` gives the command that
wrote them.

```sh
uv run pytest tools/upgrade/tests
```
