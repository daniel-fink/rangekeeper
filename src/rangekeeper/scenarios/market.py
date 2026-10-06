"""Recorded random inputs and pure realization of normalized market scenarios."""

from collections.abc import Sequence, Mapping
from concurrent.futures import ProcessPoolExecutor
from importlib.metadata import version
import json
from typing import Any, cast
import multiprocessing
import math
import platform
from uuid import UUID, uuid5

from ..model import (
    Model,
    Metadata,
    Update,
    Definitions,
    System,
    Provenance,
    Measure,
    Formulation,
    Value,
    Quantity,
)
from ..model.flow import Flow, Movement
from ..model.scenario import (
    ScenarioPlan,
    ScenarioRealization,
    Binding,
    RandomStream,
    LibraryVersion,
    ObservationAvailability,
)
from .._schema.records import ValueReference
from ..duration.period import resolve_period_date
from ..calculations.distribution import sample as sample_distribution
from .plan import make_plan, validate
from .components import (
    make_trend,
    make_volatility,
    make_cyclicality,
    make_noise,
    make_black_swan,
)
from .random import create_generator, stream_identifier
from .view import Market
from ._paths import construct_paths


def _identity(model, plan, key):
    return uuid5(
        model.id,
        json.dumps([plan.to_data(), key], sort_keys=True, separators=(",", ":")),
    )


def _flow(plan, amounts):
    return Flow(
        units="dimensionless",
        movements=tuple(
            Movement(
                key=f"p{i+1}",
                period=p,
                date=resolve_period_date(p, timing="last_day"),
                magnitude=float(x),
            )
            for i, (p, x) in enumerate(zip(plan.periods, amounts))
        ),
    )


def _sample(model: Model, plan: ScenarioPlan, key: str) -> Model:
    """Create an immutable draw document; the caller owns all persistence."""
    root = _identity(model, plan, key)
    measure_id = uuid5(root, "measure")
    values, streams = [], []

    def generator(name):
        # Component identifiers are part of the seeded algorithm. Preserve the
        # v1 identity when the public parameter name changes in v2.
        component = "volatility" if name == "volatility_per_period" else name
        streams.append(
            RandomStream(name=name, identifier=stream_identifier(key, component))
        )
        return create_generator(plan.seed, scenario_key=key, component=component)

    parameters = {}
    for parameter in plan.parameters:
        name = parameter.name
        assert parameter.distribution is not None or parameter.quantity is not None
        if plan.method == "independent.v2":
            array = (
                sample_distribution(
                    parameter.distribution,
                    size=len(plan.periods),
                    generator=generator(name),
                )
                if parameter.distribution
                else (cast(Quantity, parameter.quantity).magnitude,) * len(plan.periods)
            )
            values.append(
                Value(
                    id=uuid5(root, name),
                    key="input_" + name,
                    kind="flow",
                    measure=measure_id,
                    flow=_flow(plan, array),
                )
            )
        else:
            magnitude = (
                sample_distribution(
                    parameter.distribution, size=1, generator=generator(name)
                )[0]
                if parameter.distribution
                else cast(Quantity, parameter.quantity).magnitude
            )
            parameters[name] = magnitude
            values.append(
                Value(
                    id=uuid5(root, name),
                    key="input_" + name,
                    kind="measurement",
                    measure=measure_id,
                    quantity=Quantity(magnitude=magnitude, units="dimensionless"),
                )
            )
    if plan.method.startswith("market."):
        count = len(plan.periods)
        arrays = dict(
            innovations=generator("innovations").normal(
                0, parameters["volatility_per_period"], count
            ),
            noise=generator("noise").uniform(
                parameters["noise_lower"], parameters["noise_upper"], count
            ),
            events=generator("events").uniform(0, 1, count),
        )
        for name, array in arrays.items():
            values.append(
                Value(
                    id=uuid5(root, name),
                    key="input_" + name,
                    kind="flow",
                    measure=measure_id,
                    flow=_flow(plan, array),
                )
            )
    return _capture(model, plan, key, values, streams, "numpy.SeedSequence/PCG64")


def _capture(model, plan, key, values, streams, algorithm):
    root = _identity(model, plan, key)
    measure_id = uuid5(root, "measure")
    realization = ScenarioRealization(
        id=root,
        plan=plan,
        key=key,
        generator=algorithm,
        versions=(
            LibraryVersion(name="python", version=platform.python_version()),
            *(
                LibraryVersion(name=name, version=version(name))
                for name in ("numpy", "scipy")
            ),
        ),
        streams=tuple(streams),
        inputs=tuple(
            Binding(name=v.key.removeprefix("input_"), value=v.id) for v in values
        ),
        outputs=(),
        availability=tuple(
            ObservationAvailability(
                target=ValueReference(value=v.id, movement=m.key),
                available_at=resolve_period_date(
                    cast(Any, m.period), timing="last_day"
                ),
            )
            for v in values
            if v.flow is not None
            for m in v.flow.movements
        ),
    )
    system = cast(dict[str, Any], model.system.to_data() if model.system else {})
    system.setdefault("formulations", []).append(
        Formulation(
            id=uuid5(root, "formulation"), name=f"Scenario {key}", values=tuple(values)
        ).to_data()
    )
    definitions = cast(
        dict[str, Any], model.definitions.to_data() if model.definitions else {}
    )
    definitions.setdefault("measures", []).append(
        Measure(
            id=measure_id,
            code=f"scenario_{root.hex}",
            name="Normalized scenario quantity",
            units="dimensionless",
        ).to_data()
    )
    provenance = cast(
        dict[str, Any], model.provenance.to_data() if model.provenance else {}
    )
    provenance.setdefault("scenarios", []).append(realization.to_data())
    # Include recorded algorithm/version evidence in revision identity. Different
    # capture environments must not write different content under the same UUID.
    revision = uuid5(
        root, json.dumps([definitions, system, provenance], sort_keys=True)
    )
    return model.revise(
        Update(
            definitions=Definitions.from_data(definitions),
            system=System.from_data(system),
            provenance=Provenance.from_data(provenance),
            metadata=Metadata.from_data(
                {
                    **model.metadata.to_data(),
                    "id": str(revision),
                    "previous": str(model.id),
                }
            ),
        )
    )


def sample(model: Model, plan: ScenarioPlan, *, scenario_key: str) -> Model:
    """Return captured inputs only, for explicit inspection before realize().

    This draws randomness from stable streams. It does not construct output paths
    or write files. Use capture() when the inputs are already known.
    """
    validate(plan)
    if not isinstance(scenario_key, str) or not scenario_key.strip():
        raise ValueError("scenario key must be nonempty")
    return _sample(model, plan, scenario_key)


def capture(
    model: Model,
    plan: ScenarioPlan,
    *,
    scenario_key: str,
    inputs: Mapping[str, Quantity | Sequence[float]],
) -> Model:
    """Record supplied parameters and innovations without drawing randomness.

    Quantities supply scalar parameters; sequences supply one draw per declared
    period. All normalized market quantities are dimensionless. Canonical keys
    p1, p2, ... are assigned in the plan's explicit period order. Missing, extra,
    nonfinite or wrongly sized inputs fail; no input or store is changed.
    """
    validate(plan)
    if not scenario_key.strip():
        raise ValueError("scenario key must be nonempty")
    root = _identity(model, plan, scenario_key)
    values = []
    for name, content in sorted(inputs.items()):
        common: dict[str, Any] = dict(
            id=uuid5(root, name), key="input_" + name, measure=uuid5(root, "measure")
        )
        if isinstance(content, Quantity):
            if content.units != "dimensionless":
                raise ValueError("captured parameters require dimensionless units")
            values.append(Value(**common, kind="measurement", quantity=content))
        else:
            amounts = tuple(content)
            if len(amounts) != len(plan.periods) or any(
                not math.isfinite(x) for x in amounts
            ):
                raise ValueError(
                    "captured draws require finite values for every period"
                )
            values.append(Value(**common, kind="flow", flow=_flow(plan, amounts)))
    result = _capture(model, plan, scenario_key, values, (), "supplied")
    captured_inputs(result, plan)
    return result


def captured_inputs(draws: Model, plan: ScenarioPlan):
    """Resolve the one matching captured plan; reject incomplete or reordered draws."""
    matches = (
        [r for r in draws.provenance.scenarios or () if r.plan.id == plan.id]
        if draws.provenance
        else []
    )
    if len(matches) != 1 or matches[0].plan.to_data() != plan.to_data():
        raise ValueError("draws must contain exactly one matching recorded plan")
    record = matches[0]
    parameters, arrays = {}, {}
    for binding in record.inputs:
        value = draws.value(binding.value)
        if value.quantity is not None:
            if value.quantity.units != "dimensionless":
                raise ValueError("captured quantities must be dimensionless")
            parameters[binding.name] = value.quantity.magnitude
        elif value.flow is not None:
            if value.flow.units != "dimensionless":
                raise ValueError("captured draws must be dimensionless")
            movements = value.flow.movements
            if len(movements) != len(plan.periods) or any(
                m.period != p or m.key != f"p{i+1}"
                for i, (m, p) in enumerate(zip(movements, plan.periods))
            ):
                raise ValueError("captured draw coordinates must match the plan")
            if any(m.magnitude is None for m in movements):
                raise ValueError("captured draws cannot be unresolved")
            arrays[binding.name] = tuple(cast(float, m.magnitude) for m in movements)
        else:
            raise ValueError("captured input must be a resolved numerical Value")
    required_arrays = (
        {"innovations", "noise", "events"}
        if plan.method.startswith("market.")
        else {"space_factor", "asset_cap"}
    )
    if set(arrays) != required_arrays or (
        plan.method.startswith("market.")
        and set(parameters) != {p.name for p in plan.parameters}
    ):
        raise ValueError("captured input inventory mismatch")
    for parameter in plan.parameters:
        captured = (
            arrays[parameter.name]
            if plan.method == "independent.v2"
            else (parameters[parameter.name],)
        )
        if parameter.quantity is not None and any(
            x != parameter.quantity.magnitude for x in captured
        ):
            raise ValueError("captured parameter differs from fixed plan input")
        if parameter.distribution is not None and any(
            not parameter.distribution.lower <= x <= parameter.distribution.upper
            for x in captured
        ):
            raise ValueError("captured parameter outside distribution support")
    return record, parameters, arrays


def realize(model: Model, plan: ScenarioPlan, *, draws: Model) -> Market:
    """Construct paths from recorded draws only. No RNG, mutation, store or file IO.

    Input Values and provenance are retained. Paths use stable Movement keys and
    dates. Forward-derived ratios carry availability at the next period end.
    """
    validate(plan)
    record, parameters, arrays = captured_inputs(draws, plan)
    if draws.metadata.previous != model.id:
        raise ValueError("draw document must derive from the supplied base Model")
    paths, delays = construct_paths(plan.method, parameters, arrays)
    measure_id = draws.value(record.inputs[0].value).measure
    values = tuple(
        Value(
            id=uuid5(record.id, "output/" + name),
            key=name,
            kind="flow",
            measure=measure_id,
            flow=_flow(plan, amounts),
        )
        for name, amounts in paths.items()
    )
    data = cast(dict[str, Any], draws.to_data())
    formulation = next(
        f
        for f in data["system"]["formulations"]
        if f["id"] == str(uuid5(record.id, "formulation"))
    )
    formulation["values"].extend(v.to_data() for v in values)
    updated = cast(dict[str, Any], record.to_data())
    updated["outputs"] = [Binding(name=v.key, value=v.id).to_data() for v in values]
    updated["availability"].extend(
        ObservationAvailability(
            target=ValueReference(value=v.id, movement=m.key),
            available_at=resolve_period_date(
                plan.periods[i + delays.get(v.key, 0)], timing="last_day"
            ),
        ).to_data()
        for v in values
        for i, m in enumerate(cast(Flow, v.flow).movements)
    )
    data["provenance"]["scenarios"] = [
        updated if r["id"] == str(record.id) else r
        for r in data["provenance"]["scenarios"]
    ]
    output = model.revise(
        Update(
            definitions=Definitions.from_data(data["definitions"]),
            system=System.from_data(data["system"]),
            provenance=Provenance.from_data(data["provenance"]),
            metadata=Metadata.from_data(
                {
                    **model.metadata.to_data(),
                    "id": str(
                        uuid5(
                            record.id,
                            json.dumps(
                                draws.to_data(), sort_keys=True, separators=(",", ":")
                            ),
                        )
                    ),
                    "previous": str(model.id),
                }
            ),
        )
    )
    return Market(output, ScenarioRealization.from_data(updated))


def _worker(payload):
    """Process boundary accepts and returns only detached dictionaries and strings."""
    model_data, plan_data, key = payload
    model, plan = Model.from_data(model_data), ScenarioPlan.from_data(plan_data)
    result = realize(model, plan, draws=sample(model, plan, scenario_key=key))
    return result.model.to_data(), result.realization.to_data()


def generate(
    model: Model, plan: ScenarioPlan, *, scenario_keys: Sequence[str], workers: int = 1
) -> tuple[Market, ...]:
    """Generate ordered, independent realizations; worker count cannot affect content.

    Duplicate/blank keys and nonpositive worker counts fail. Random generators and
    record wrappers never cross the process boundary. Persistence is explicit.
    """
    validate(plan)
    keys = tuple(scenario_keys)
    if (
        type(workers) is not int
        or workers < 1
        or any(not isinstance(k, str) or not k.strip() for k in keys)
        or len(set(keys)) != len(keys)
    ):
        raise ValueError("unique nonempty keys and positive worker count required")
    payloads = [(model.to_data(), plan.to_data(), key) for key in keys]
    if workers == 1:
        output = map(_worker, payloads)
        return tuple(
            Market(Model.from_data(m), ScenarioRealization.from_data(r))
            for m, r in output
        )
    with ProcessPoolExecutor(
        max_workers=workers, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        return tuple(
            Market(Model.from_data(m), ScenarioRealization.from_data(r))
            for m, r in pool.map(_worker, payloads)
        )
