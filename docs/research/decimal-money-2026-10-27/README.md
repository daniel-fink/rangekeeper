# Decimal money cost — 2026-10-27

These measurements support [ADR-023](../../decisions/023-decimal-money.md). They
compare float64 records on `develop` at `1e32b8d` with the Decimal operations
that the design adds. The Decimal records are not implemented yet. So the
script measures each added operation separately and compares it with the
current cost of the same record operation.

Environment: macOS 15 (Darwin 24.6.0), Apple silicon, Python 3.14.2,
Polars 1.44.2, PyArrow 23.0.1, `uv sync --all-extras --group dev --locked`.
Each value is the best of several repeats from `timeit`.

Run the [benchmark script](bench_money.py) from the repository root:

```sh
uv run --locked python -I docs/research/decimal-money-2026-10-27/bench_money.py
```

## Flow of 120 monthly movements

| Operation | Time |
| --- | --- |
| `Flow.from_events`, float64, with `check` | 6857 µs |
| `Flow.to_data` | 135 µs |
| `json.dumps` of the Flow data | 73 µs |
| `json.loads` of the Flow text | 45 µs |
| `Flow.total` (`fsum`) | 1898 µs |
| `io.polars.to_frame` | 910 µs |
| `Decimal(str)` × 120 | 13 µs |
| `float(Decimal)` × 120 (`to_number`) | 12 µs |
| `Decimal(repr(float))` × 120 (shortest round trip) | 39 µs |
| `Decimal(format(float, ".15g"))` × 120 (`to_amount`) | 48 µs |
| `quantize(0.01, ROUND_HALF_EVEN)` × 120 | 13 µs |
| `str(Decimal)` × 120 | 7 µs |
| `math.fsum` of 120 floats | 1.5 µs |
| Exact `Decimal` sum of 120 values | 5.4 µs |
| `json.dumps` of 120 decimal strings | 14 µs |
| `json.loads` of 120 strings and `Decimal()` | 19 µs |
| `pl.Series`, `Float64`, 120 values | 3.4 µs |
| `pl.Series`, `Decimal(38, 10)`, 120 values | 63 µs |
| Cast `Decimal(38, 10)` to `Float64`, 120 values | 1.3 µs |

## Parquet encodings, zstd

| Physical type | 120 values: size, write, read | 10⁶ values: size, write, read |
| --- | --- | --- |
| `float64` | 1489 B, 43 µs, 161 µs | 7.04 MB, 26.8 ms, 11.1 ms |
| `decimal128(38, 10)` | 1555 B, 48 µs, 249 µs | 6.92 MB, 55.5 ms, 21.8 ms |
| `decimal128(38, 18)` | 1923 B, 49 µs, 248 µs | 9.69 MB, 62.9 ms, 20.9 ms |
| `string` | 1297 B, 42 µs, 190 µs | 5.26 MB, 55.9 ms, 22.4 ms |

## Example Model

`examples/data/mixed_use_property/model.json` has 144 Quantities, all in m, m²
or m³, and no Flows. It has no currency amounts, so ADR-023 does not change it.

| Operation | Time |
| --- | --- |
| `io.json.loads(kind=Model)` | 78.6 ms |
| `io.json.dumps` | 81.9 ms |
| `io.bundle.write` | 395 ms |
| `io.bundle.Reader(...).model()` | 216 ms |
| Decimal conversion and back for all 144 magnitudes | 85 µs |

## Result

At record sizes, the Decimal operations add less than 1 % to construction and
IO. A `string` column is the smallest Parquet encoding. At 10⁶ values it writes
and reads about two times slower than `float64`, the same as `decimal128`.
