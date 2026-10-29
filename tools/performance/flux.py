"""ADR-005 complete-operation timings. Run with PYTHONPATH=src from repository root."""

import argparse
import json
import resource
import time
from datetime import date
from pathlib import Path

from rangekeeper.duration import Frequency, Periods
from rangekeeper.flow import Flow, ResampleMethod, Stream


def run(count, months):
    start = time.perf_counter()
    periods = Periods(start=date(2000, 1, 1), frequency=Frequency.MONTH, count=months)
    annual = Periods(
        start=date(2000, 1, 1), frequency=Frequency.YEAR, count=months // 12
    )
    flows = {
        str(i): Flow.from_periods(periods, [float(i + 1)] * months, units="AUD")
        for i in range(count)
    }
    construction = time.perf_counter() - start
    stream = Stream(flows=flows)
    start = time.perf_counter()
    grouped = stream.resample(periods=annual, method=ResampleMethod.SUM)
    result = grouped.sum()
    first = time.perf_counter() - start
    start = time.perf_counter()
    grouped.sum()
    repeated = time.perf_counter() - start
    start = time.perf_counter()
    _ = grouped.flows
    materialize = time.perf_counter() - start
    assert result.movements[0].number == 12 * count * (count + 1) / 2
    return dict(
        flows=count,
        months=months,
        construction=construction,
        resample_and_sum=first,
        repeated_sum=repeated,
        materialize_lines=materialize,
        maxrss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--large", action="store_true")
    args = parser.parse_args()
    results = []
    for count, months in [(3, 132), (100, 120)] + ([(1000, 360)] if args.large else []):
        result = run(count, months)
        results.append(result)
        print(json.dumps(result), flush=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n")
