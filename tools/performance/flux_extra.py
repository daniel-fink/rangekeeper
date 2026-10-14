"""Comparable hierarchy and mixed-grid workloads, including the pre-005 API."""

from datetime import date
from pathlib import Path
from uuid import uuid4
import argparse
import importlib
import json
import math
import resource
import time

from rangekeeper.model import (
    Model,
    Metadata,
    Definitions,
    System,
    Assembly,
    Entity,
    Measure,
    Value,
    Characteristics,
)
from rangekeeper.schema.records import Flow
from rangekeeper.schema.enums import ValueKind
from rangekeeper.model.duration import make_periods, Frequency
from rangekeeper.model.system import View, Hierarchy
from rangekeeper.calculations import series
from rangekeeper.schema.behaviors.flow import MissingValueHandling as Missing


def hierarchy_case(legacy):
    start = time.perf_counter()
    months = make_periods(date(2000, 1, 1), frequency=Frequency.MONTH, count=120)
    years = make_periods(date(2000, 1, 1), frequency=Frequency.YEAR, count=10)
    measure = Measure(id=uuid4(), code="money", name="Money", units="AUD")
    entities = []
    buildings = []
    for b in range(100):
        children = []
        for c in range(10):
            n = b * 10 + c + 1
            value = Value(
                id=uuid4(),
                key="cashflow",
                kind=ValueKind.FLOW,
                measure=measure.id,
                flow=Flow.from_periods(months, [float(n)] * 120, units="AUD"),
            )
            entity = Entity(
                id=uuid4(),
                name=f"Contributor {n}",
                characteristics=Characteristics(values=(value,)),
            )
            entities.append(entity)
            children.append(entity.id)
        buildings.append(
            Assembly(id=uuid4(), name=f"Building {b+1}", entities=children)
        )
    root = Assembly(
        id=uuid4(), name="Portfolio", entities=tuple(b.id for b in buildings)
    )
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="0.7.0"),
        definitions=Definitions(measures=(measure,)),
        system=System(entities=entities, assemblies=(*buildings, root)),
    )
    hierarchy = Hierarchy(View(model), membership_root=root.id)
    construction = time.perf_counter() - start
    start = time.perf_counter()
    if legacy:
        # Explicit baseline composition: original contributor flows, one temporal
        # resampling per contributor, then an aggregate for each requested subtree.
        method = getattr(series, "Resampling" + "Reduction").SUM
        selected = {
            e.id: series.resample(
                e.characteristics.values[0].flow, periods=years, **{"reduction": method}
            ).flow
            for e in entities
        }
        populations = {}
        results = {}
        for owner in hierarchy.postorder():
            children = hierarchy.children(owner)
            population = ([selected[owner]] if owner in selected else []) + [
                f for child in children for f in populations[child]
            ]
            populations[owner] = population
            results[owner] = series.aggregate(population).flow
        total = results[root.id]
        first = results[buildings[0].id]
    else:
        from rangekeeper.model.system import Reduction

        result = Reduction.flows(
            key="cashflow", periods=years, resampling=series.ResamplingMethod.SUM
        ).execute(hierarchy)
        total = result.root_value
        first = result.value(buildings[0].id)
    elapsed = time.perf_counter() - start
    assert all(m.number == 6006000 for m in total.movements)
    assert first.movements[0].number == 660
    return dict(
        case="hierarchy_100_by_10_by_120",
        construction=construction,
        execute=elapsed,
        maxrss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    )


def mixed_case(legacy):
    monthly = make_periods(date(2000, 1, 1), frequency=Frequency.MONTH, count=24)
    annual = make_periods(date(2000, 1, 1), frequency=Frequency.YEAR, count=2)
    flows = {}
    for i in range(100):
        periods = monthly[i % 12 :] if i % 2 else annual
        values = [float(i + 1)] * len(periods)
        if i % 3 == 0:
            values[-1] = None
        flows[str(i)] = Flow.from_periods(periods, values, units="AUD")
    expected = math.fsum(
        m.magnitude
        for f in flows.values()
        for m in f.movements
        if m.magnitude is not None
    )
    start = time.perf_counter()
    if legacy:
        method = getattr(series, "Resampling" + "Reduction").SUM
        parts = [
            series.resample(
                f, periods=annual, missing=Missing.SKIP, **{"reduction": method}
            ).flow
            for f in flows.values()
        ]
        result = series.aggregate(parts, missing=Missing.SKIP).flow
    else:
        from rangekeeper.model.flux import Stream

        result = (
            Stream(flows, missing=Missing.SKIP)
            .resample(annual, method=series.ResamplingMethod.SUM)
            .sum()
        )
    elapsed = time.perf_counter() - start
    assert result.total().magnitude == expected
    return dict(
        case="mixed_sparse_100_lines",
        execute=elapsed,
        maxrss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = []
    for operation in (mixed_case, hierarchy_case):
        result = operation(args.baseline)
        results.append(result)
        print(json.dumps(result), flush=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n")
