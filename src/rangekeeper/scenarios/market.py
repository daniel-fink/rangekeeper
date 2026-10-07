"""Recorded random inputs and pure realization of normalized market scenarios."""

from collections.abc import Sequence, Mapping
from concurrent.futures import ProcessPoolExecutor
from importlib.metadata import version
import json
import hashlib
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
from .._schema.records import Reference


from .contracts import method, check_values, check_inputs
from ..model._scenario import validate_plan
from .components import _parameters
from .implementation import calculation_provenance
from ..duration import PeriodTiming
from .._schema.enums import ValueKind
from ..model.scenario import ScenarioParameter, Distribution
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


def make_plan(
    *,
    periods: Sequence,
    seed: int,
    parameters: Mapping[str, float | Quantity | Distribution] | None = None,
    components: Sequence[Sequence[ScenarioParameter]] = (),
    id: UUID | None = None,
    method: str = "market",
) -> ScenarioPlan:
    """Record the selected market contract, defaults and explicit parameter groups."""
    from uuid import uuid4
    from .contracts import method as contract_for

    contract = contract_for(method)
    values: dict[str, float | Quantity | Distribution] = {
        name: rule.default
        for name, rule in contract.parameters.items()
        if rule.default is not None
    }
    declared = dict(parameters or {})
    for component in components:
        for parameter in component:
            if parameter.name in declared:
                raise ValueError(f"duplicate component parameter: {parameter.name}")
            if (parameter.quantity is None) == (parameter.distribution is None):
                raise ValueError(
                    "component requires exactly one quantity or distribution"
                )
            declared[parameter.name] = (
                parameter.quantity
                if parameter.quantity is not None
                else cast(Distribution, parameter.distribution)
            )
    if set(declared) - set(contract.parameters):
        raise ValueError("unknown market parameter")
    values.update(declared)
    plan = ScenarioPlan(
        id=id or uuid4(),
        method=method,
        seed=seed,
        periods=tuple(periods),
        parameters=_parameters(**dict(sorted(values.items()))),
    )
    validate(plan)
    return plan


def validate(plan: ScenarioPlan) -> None:
    """Validate a complete plan without randomness or numerical generation."""
    validate_plan(plan.to_data())


def _scenario_key(key):
    if not isinstance(key, str) or not key.strip():
        raise ValueError("scenario key must be nonempty")
    return key


def _identity(model, plan, key):
    return uuid5(
        model.id,
        json.dumps([plan.to_data(), key], sort_keys=True, separators=(",", ":")),
    )


def _flow(plan, amounts, owner: UUID):
    return Flow(
        units="dimensionless",
        movements=tuple(
            Movement(
                id=uuid5(
                    owner,
                    "movement/"
                    + p.start_inclusive.isoformat()
                    + "/"
                    + p.end_exclusive.isoformat(),
                ),
                key=f"p{i + 1}",
                period=p,
                date=p.resolve(timing=PeriodTiming.LAST),
                magnitude=float(x),
            )
            for i, (p, x) in enumerate(zip(plan.periods, amounts))
        ),
    )


def _sample(model: Model, plan: ScenarioPlan, key: str) -> Model:
    """Sample inputs once, then use the same recording path as supplied captures."""
    inputs: dict[str, Quantity | Sequence[float]] = {}
    streams: list[RandomStream] = []
    parameters: dict[str, float] = {}
    contract = method(plan.method)

    def generator(name):
        component = "volatility" if name == "volatility_per_period" else name
        streams.append(
            RandomStream(name=name, identifier=stream_identifier(key, component))
        )
        return create_generator(plan.seed, scenario_key=key, component=component)

    for parameter in plan.parameters:
        name = parameter.name
        count = 1 if contract.scalar_parameters else len(plan.periods)
        sampled = (
            parameter.distribution.sample(size=count, generator=generator(name))
            if parameter.distribution is not None
            else (cast(Quantity, parameter.quantity).magnitude,) * count
        )
        if contract.scalar_parameters:
            parameters[name] = sampled[0]
            inputs[name] = Quantity(magnitude=sampled[0], units="dimensionless")
        else:
            inputs[name] = sampled
    check_values(plan.method, parameters)
    if contract.scalar_parameters:
        count = len(plan.periods)
        inputs.update(
            innovations=generator("innovations").normal(
                0, parameters["volatility_per_period"], count
            ),
            noise=generator("noise").uniform(
                parameters["noise_lower"], parameters["noise_upper"], count
            ),
            events=generator("events").uniform(0, 1, count),
        )
    return _record_inputs(model, plan, key, inputs, streams, "numpy.SeedSequence/PCG64")


def _record_inputs(model, plan, key, inputs, streams, algorithm):
    root = _identity(model, plan, key)
    values = []
    for name, content in inputs.items():
        common = dict(
            id=uuid5(root, name), key="input_" + name, measure=uuid5(root, "measure")
        )
        if isinstance(content, Quantity):
            if content.units != "dimensionless":
                raise ValueError("captured parameters require dimensionless units")
            values.append(Value(**common, kind=ValueKind.MEASUREMENT, quantity=content))
        else:
            amounts = tuple(content)
            if len(amounts) != len(plan.periods) or any(
                isinstance(x, bool) or not math.isfinite(x) for x in amounts
            ):
                raise ValueError(
                    "captured draws require finite values for every period"
                )
            values.append(
                Value(
                    **common,
                    kind=ValueKind.FLOW,
                    flow=_flow(plan, amounts, uuid5(root, name)),
                )
            )
    return _capture(model, plan, key, root, values, streams, algorithm)


def _capture(model, plan, key, root, values, streams, algorithm):
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
                target=Reference(target=m.id),
                available_at=cast(Any, m.period).resolve(timing=PeriodTiming.LAST),
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
    return _sample(model, plan, _scenario_key(scenario_key))


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
    return _record_inputs(
        model,
        plan,
        _scenario_key(scenario_key),
        dict(sorted(inputs.items())),
        (),
        "supplied",
    )


def captured_inputs(draws: Model, plan: ScenarioPlan):
    """Resolve the one matching captured plan; reject incomplete or reordered draws."""
    matches = (
        [r for r in draws.provenance.scenarios or () if r.plan.id == plan.id]
        if draws.provenance
        else []
    )
    if len(matches) != 1 or matches[0].plan != plan:
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
    contract = method(plan.method)
    if set(arrays) != set(contract.arrays) or set(parameters) != (
        set(contract.parameters) if contract.scalar_parameters else set()
    ):
        raise ValueError("captured input inventory mismatch")
    check_inputs(plan.method, parameters, arrays)
    for parameter in plan.parameters:
        captured = (
            arrays[parameter.name]
            if not contract.scalar_parameters
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

    Input Values and provenance are retained. Paths use stable Movement UUIDs, period labels and
    dates. Forward-derived ratios carry availability at the next period end.
    """
    validate(plan)
    return _realize(model, plan, draws=draws)


def _realize(model, plan, *, draws):
    record, parameters, arrays = captured_inputs(draws, plan)
    if draws.metadata.previous != model.id:
        raise ValueError("draw document must derive from the supplied base Model")
    paths, delays = construct_paths(plan.method, parameters, arrays)
    measure_id = draws.value(record.inputs[0].value).measure
    values = tuple(
        Value(
            id=uuid5(record.id, "output/" + name),
            key=name,
            kind=ValueKind.FLOW,
            measure=measure_id,
            flow=_flow(plan, amounts, uuid5(record.id, "output/" + name)),
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
    updated["calculation"] = calculation_provenance().to_data()
    updated["outputs"] = [Binding(name=v.key, value=v.id).to_data() for v in values]
    updated["availability"].extend(
        (
            ObservationAvailability(
                target=Reference(target=m.id),
                available_at=plan.periods[i + delays.get(v.key, 0)].resolve(
                    timing=PeriodTiming.LAST
                ),
            ).to_data()
            for v in values
            for i, m in enumerate(cast(Flow, v.flow).movements)
        )
    )
    data["provenance"]["scenarios"] = [
        updated if r["id"] == str(record.id) else r
        for r in data["provenance"]["scenarios"]
    ]
    data["metadata"] = {**model.metadata.to_data(), "previous": str(model.id)}
    data["metadata"].pop("id", None)
    digest = hashlib.sha256(
        json.dumps(
            data,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    data["metadata"]["id"] = str(uuid5(record.id, "realized-model/v1:" + digest))
    output = model.revise(
        Update(
            definitions=Definitions.from_data(data["definitions"]),
            system=System.from_data(data["system"]),
            provenance=Provenance.from_data(data["provenance"]),
            metadata=Metadata.from_data(data["metadata"]),
        )
    )

    return Market(output, ScenarioRealization.from_data(updated))


def _worker(payload):
    """Process boundary accepts and returns only detached dictionaries and strings."""
    model_data, plan_data, key = payload
    model, plan = Model.from_data(model_data), ScenarioPlan.from_data(plan_data)
    validate(plan)
    result = _generate_one(model, plan, key)
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
    if workers == 1:
        return tuple(_generate_one(model, plan, key) for key in keys)
    model_data, plan_data = model.to_data(), plan.to_data()
    payloads = [(model_data, plan_data, key) for key in keys]
    with ProcessPoolExecutor(
        max_workers=workers, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        return tuple(
            Market(Model.from_data(m), ScenarioRealization.from_data(r))
            for m, r in pool.map(_worker, payloads)
        )


def _generate_one(model, plan, key):
    return _realize(model, plan, draws=_sample(model, plan, _scenario_key(key)))
