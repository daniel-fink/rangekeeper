"""Record runtime timings (ADR-011): construction, replacement, decoding and access.

Run from the repository root:

    uv run python tools/performance/records.py --output records.json

Each value is the median time of one operation in microseconds.
"""

import argparse
import json
import statistics
import time
from datetime import date
from pathlib import Path

import yaml

from rangekeeper import Model
from rangekeeper.duration import Frequency, make_periods
from rangekeeper.flow import Flow

ROOT = Path(__file__).resolve().parents[2]


def median(operation, repeat):
    """Return the median duration of ``operation`` in microseconds."""
    times = []
    for _ in range(repeat):
        start = time.perf_counter()
        operation()
        times.append(time.perf_counter() - start)
    return round(statistics.median(times) * 1e6, 1)


def run(movements, repeat):
    """Time the record operations on one Flow and one example Model."""
    periods = make_periods(date(2000, 1, 1), frequency=Frequency.MONTH, count=movements)
    magnitudes = [float(i) for i in range(movements)]
    flow = Flow.from_periods(periods, magnitudes, units="AUD")
    data = flow.to_data()
    model = yaml.safe_load((ROOT / "examples/schema/model.yaml").read_text())
    loaded = Model.from_data(model)
    return dict(
        movements=movements,
        flow_construct=median(
            lambda: Flow.from_periods(periods, magnitudes, units="AUD"), repeat
        ),
        flow_from_data=median(lambda: Flow.from_data(data), repeat),
        flow_replace=median(lambda: flow.replace(units="USD"), repeat),
        flow_to_data=median(flow.to_data, repeat),
        movements_access=median(lambda: flow.movements, repeat),
        movement_fields=median(
            lambda: [(m.id, m.period, m.magnitude) for m in flow.movements], repeat
        ),
        model_from_data=median(lambda: Model.from_data(model), repeat),
        model_to_data=median(loaded.to_data, repeat),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeat", type=int, default=50)
    args = parser.parse_args()
    results = [run(count, args.repeat) for count in (12, 120)]
    for result in results:
        print(json.dumps(result), flush=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n")
