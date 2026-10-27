"""Measure the cost of Decimal money against float64 records (#117, ADR-023).

Run from the repository root: uv run --locked python -I docs/research/decimal-money-2026-10-27/bench_money.py
"""

import io
import json
import math
import random
import sys
import tempfile
import timeit
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from rangekeeper import Model
from rangekeeper.io import bundle, polars as rkpl
from rangekeeper.io import json as rkjson
from rangekeeper.schema.records import Flow

random.seed(117)
N = 120
dates = [date(2027 + (i // 12), 1 + i % 12, 1) for i in range(N)]
floats = [round(random.uniform(-2e6, 5e6), 2) for _ in range(N)]
texts = [f"{x:.2f}" for x in floats]
decimals = [Decimal(t) for t in texts]


def best(fn, number=200, repeat=7):
    return min(timeit.repeat(fn, number=number, repeat=repeat)) / number


rows = []


def row(name, seconds):
    rows.append((name, seconds))
    print(f"{name:<62} {seconds * 1e6:12.1f} us", flush=True)


# A. Today's float Flow of 120 movements
row("Flow.from_events (120, float, with check)", best(lambda: Flow.from_events(dates, floats, units="AUD"), 50))
flow = Flow.from_events(dates, floats, units="AUD")
data = flow.to_data()
row("Flow.to_data", best(lambda: flow.to_data()))
text = json.dumps(data)
row("json.dumps(flow data)", best(lambda: json.dumps(data)))
row("json.loads(flow text)", best(lambda: json.loads(text)))
row("Flow.total (fsum)", best(lambda: flow.total()))
row("io.polars.to_frame(flow)", best(lambda: rkpl.to_frame(flow), 50))

# B. Decimal deltas on 120 values
row("Decimal(str) x120", best(lambda: [Decimal(t) for t in texts]))
row("float(Decimal) x120 (boundary in)", best(lambda: [float(d) for d in decimals]))
row("Decimal(repr(float)) x120 (shortest round trip)", best(lambda: [Decimal(repr(x)) for x in floats]))
row("Decimal(format(float, '.15g')) x120 (to_amount)", best(lambda: [Decimal(format(x, ".15g")) for x in floats]))
q = Decimal("0.01")
row("quantize(0.01, HALF_EVEN) x120", best(lambda: [d.quantize(q, ROUND_HALF_EVEN) for d in decimals]))
row("str(Decimal) x120 (JSON text)", best(lambda: [str(d) for d in decimals]))
row("repr(float) x120", best(lambda: [repr(x) for x in floats]))
row("math.fsum floats x120", best(lambda: math.fsum(floats)))
row("sum Decimal x120 (exact)", best(lambda: sum(decimals, Decimal(0))))
row("Decimal.is_finite + type check x120", best(lambda: [type(d) is Decimal and d.is_finite() for d in decimals]))
row("float type + isfinite x120", best(lambda: [type(x) is float and math.isfinite(x) for x in floats]))
dec_text = json.dumps([str(d) for d in decimals])
row("json.dumps 120 decimal strings", best(lambda: json.dumps([str(d) for d in decimals])))
row("json.loads 120 strings + Decimal()", best(lambda: [Decimal(s) for s in json.loads(dec_text)]))
num_text = json.dumps(floats)
row("json.loads 120 numbers parse_float=Decimal", best(lambda: json.loads(num_text, parse_float=Decimal)))

# Polars
row("pl.Series Float64 from 120 floats", best(lambda: pl.Series(floats, dtype=pl.Float64)))
row("pl.Series Decimal(38,10) from 120 Decimals", best(lambda: pl.Series(decimals, dtype=pl.Decimal(38, 10))))
dser = pl.Series(decimals, dtype=pl.Decimal(38, 10))
row("cast Decimal(38,10) -> Float64 (120)", best(lambda: dser.cast(pl.Float64)))

# C. Parquet: physical encodings, small and large
def parquet(values, typ, n):
    table = pa.table({"v": pa.array(values, type=typ)})
    sink = io.BytesIO()
    pq.write_table(table, sink, compression="zstd")
    raw = sink.getvalue()
    w = best(lambda: pq.write_table(table, io.BytesIO(), compression="zstd"), 20, 5)
    r = best(lambda: pq.read_table(io.BytesIO(raw)), 20, 5)
    return len(raw), w, r


big = 1_000_000
bigf = [round(random.uniform(-2e6, 5e6), 2) for _ in range(big)]
bigd = [Decimal(f"{x:.2f}") for x in bigf]
bigs = [f"{x:.2f}" for x in bigf]
print()
for label, vals, typ in [
    ("float64", (floats, bigf), pa.float64()),
    ("decimal128(38,10)", (decimals, bigd), pa.decimal128(38, 10)),
    ("decimal128(38,18)", (decimals, bigd), pa.decimal128(38, 18)),
    ("string", (texts, bigs), pa.string()),
]:
    s_size, s_w, s_r = parquet(vals[0], typ, N)
    b_size, b_w, b_r = parquet(vals[1], typ, big)
    print(f"parquet {label:<20} 120: {s_size:7d} B w {s_w*1e6:7.0f}us r {s_r*1e6:7.0f}us | 1e6: {b_size/1e6:6.2f} MB w {b_w*1e3:6.1f}ms r {b_r*1e3:6.1f}ms")

# D. Example Model: today's cost, and the Decimal delta for its 144 magnitudes
print()
path = Path("examples/data/mixed_use_property/model.json")
mtext = path.read_text()
row("example Model: json.loads(kind=Model)", best(lambda: rkjson.loads(mtext, kind=Model), 3, 3))
model = rkjson.loads(mtext, kind=Model)
row("example Model: json.dumps", best(lambda: rkjson.dumps(model), 3, 3))
with tempfile.TemporaryDirectory() as tmp:
    counter = iter(range(10_000))
    row("example Model: bundle.write", best(lambda: bundle.write(Path(tmp) / f"b{next(counter)}", model), 3, 3))
    target = Path(tmp) / "read"
    bundle.write(target, model)
    row("example Model: bundle.read", best(lambda: bundle.Reader(target).model(), 3, 3))
mags = []
def collect(x):
    if isinstance(x, dict):
        if "magnitude" in x and "units" in x:
            mags.append(x["magnitude"])
        for v in x.values():
            collect(v)
    elif isinstance(x, list):
        for v in x:
            collect(v)
collect(json.loads(mtext))
print("example Model magnitudes:", len(mags))
row("144 magnitudes: Decimal(repr) + float() round trip", best(lambda: [float(Decimal(repr(float(m)))) for m in mags]))
print(sys.version)
