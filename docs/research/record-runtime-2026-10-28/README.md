# Record runtime costs — 2026-10-28

Construction, replacement, decoding and field access of generated records, for
the record runtime changes of [ADR-011](../../decisions/011-records-and-validation.md).
Each later change in that epic adds a column.

## Procedure

From the repository root, on macOS (Apple silicon), Python 3.13.11:

```sh
uv run --locked python tools/performance/records.py --output records.json --repeat 30
```

Each value is the median of 30 runs of one operation, in microseconds. The Flow
has monthly period Movements. The Model is `examples/schema/model.yaml`.

| Column | Source |
| --- | --- |
| develop | `develop` at f01bb77, before the epic |
| #107 | Generated per-field encoders and decoders, generated slots, cached children |

## Results

| Operation | Movements | develop | #107 |
| --- | ---: | ---: | ---: |
| `Flow.from_periods` | 12 | 1077.9 | 867.6 |
| `Flow.from_periods` | 120 | 10332.6 | 7900.8 |
| `Flow.from_data` | 120 | 3167.5 | 3200.9 |
| `flow.replace(units=...)` | 12 | 365.1 | 341.6 |
| `flow.replace(units=...)` | 120 | 3487.3 | 3258.8 |
| `flow.to_data()` | 120 | 240.3 | 237.2 |
| `flow.movements` | 120 | 68.7 | 0.2 |
| Read `id`, `period`, `magnitude` of each Movement | 120 | 441.0 | 104.8 |
| `Model.from_data` | — | 5658.9 | 5099.7 |
| `model.to_data()` | — | 124.4 | 124.4 |

## Reading

- Field reads no longer interpret slot metadata, and decoded children stay in a
  cache, so repeated access to `flow.movements` costs one dictionary lookup.
- Construction encodes each field with the encoder that the generator selected.
- jsonschema still validates the whole tree at each construction, `from_data`
  and `replace`. That cost dominates `from_data` and `replace`; the validation
  tiers ([#110](https://github.com/daniel-fink/rangekeeper/issues/110)) and the
  changed-field replacement ([#108](https://github.com/daniel-fink/rangekeeper/issues/108))
  remove it.
