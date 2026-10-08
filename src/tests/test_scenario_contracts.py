"""Scenario contracts, content identities and replay capability are independent."""

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid5

import pytest

from rangekeeper.model.duration import Frequency, make_periods
from rangekeeper.model import Model, Metadata, Update, Provenance, Quantity
from rangekeeper.model.scenario import market, replay, ReplayUnavailableError
from rangekeeper.model.scenario.implementation import (
    calculation_manifest,
    SOURCE_PATHS,
    RESOURCE_PATHS,
)
from rangekeeper.shared.fingerprints import manifest_digest


def base():
    return Model.create(metadata=Metadata(id=UUID(int=10000), schema_version="0.7.0"))


def plan(**kwargs):
    return market.make_plan(
        id=UUID(int=10001),
        periods=make_periods(date(2026, 1, 1), frequency=Frequency.YEAR, count=3),
        seed=123,
        **kwargs,
    )


@pytest.mark.parametrize(
    "parameters",
    [
        {"cap_rate": 0},
        {"volatility_per_period": -0.01},
        {"initial_value": 0},
        {"space_period": 0},
        {"asset_asymmetry": 1},
        {"shock_likelihood": 1.1},
        {"noise_lower": 1, "noise_upper": 0},
    ],
)
def test_invalid_fixed_parameters_fail_before_sampling(parameters):
    with pytest.raises(ValueError):
        plan(parameters=parameters)


def test_estimated_cycles_share_fixed_combination_checks():
    with pytest.raises(ValueError, match="estimated asset period"):
        plan(method="market.estimates", parameters={"asset_period_difference": -10})
    result = market.generate(
        base(),
        plan(
            method="market.estimates",
            parameters={
                "space_amplitude": 0,
                "asset_amplitude": 0,
                "volatility_per_period": 0,
                "noise_lower": 0,
                "noise_upper": 0,
                "shock_likelihood": 0,
            },
        ),
        scenario_keys=["estimated"],
    )[0]
    assert [m.number for m in result.trend.flow.movements] == pytest.approx(
        [0.05, 0.051, 0.05202]
    )
    assert len(result.implied_reversion_cap_rates.flow.movements) == 2


def test_direct_generation_never_uses_the_process_adapter(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("sequential generation crossed the process adapter")

    monkeypatch.setattr(market, "_worker", forbidden)
    result = market.generate(base(), plan(), scenario_keys=["direct"])[0]
    assert result.realization.calculation.name == "rangekeeper.scenarios.market"
    assert result.realization.calculation.fingerprint.startswith(
        "scenario-calculation/v1:"
    )


def test_realized_revision_hash_covers_complete_content(monkeypatch):
    model, p = base(), plan()
    draws = market.sample(model, p, scenario_key="identity")
    first = market.realize(model, p, draws=draws)
    wire = deepcopy(first.model.to_data())
    wire["metadata"].pop("id")
    encoded = json.dumps(
        wire, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    expected = uuid5(
        first.realization.id, "realized-model/v1:" + hashlib.sha256(encoded).hexdigest()
    )
    assert first.model.id == expected
    original = market.construct_paths

    def changed(*args):
        paths, delays = original(*args)
        paths["trend"] = tuple(v + 0.01 for v in paths["trend"])
        return paths, delays

    monkeypatch.setattr(market, "construct_paths", changed)
    second = market.realize(model, p, draws=draws)
    assert first.model.id != second.model.id
    assert first.realization.id == second.realization.id
    assert first.realization.calculation == second.realization.calculation


def test_replay_unavailable_does_not_prevent_current_model_reading():
    result = market.generate(base(), plan(), scenario_keys=["readable"])[0]
    provenance = result.model.provenance.to_data()
    provenance["scenarios"][0]["calculation"][
        "fingerprint"
    ] = "scenario-calculation/v99:future"
    changed = result.model.revise(Update(provenance=Provenance.from_data(provenance)))
    assert Model.from_data(changed.to_data()).to_data() == changed.to_data()
    with pytest.raises(ReplayUnavailableError, match="unavailable"):
        replay(changed)
    provenance["scenarios"][0].pop("calculation")
    historical = result.model.revise(
        Update(provenance=Provenance.from_data(provenance))
    )
    with pytest.raises(ReplayUnavailableError):
        replay(historical)


def test_manifest_uses_portable_paths_and_explicit_source_dependencies(tmp_path):
    kernels = (
        "calculate_trend",
        "calculate_cycle",
        "calculate_autoregression",
        "accumulate_volatility",
        "calculate_shock",
    )
    for name in SOURCE_PATHS:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('"""ignored documentation"""\ndef value():\n    return 1\n')
    for name in RESOURCE_PATHS:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
    changed = tmp_path / "calculations/dynamics.py"
    kernel_source = "\n\n".join(f"def {name}():\n    return 1" for name in kernels)
    changed.write_text(kernel_source)
    versions = [{"name": "python", "version": "fixture"}]
    original = calculation_manifest(package=tmp_path, versions=versions)
    assert all(not Path(name).is_absolute() for name in original["sources"])
    assert {
        "schema/records.py",
        "schema/enums.py",
        "schema/validation.py",
    } <= original["sources"].keys()
    assert "_coordinates.py" not in original["sources"]
    assert "model/duration/period.py" not in original["sources"]
    # Record construction and typed enum decoding affect the calculated wire result.
    for name in ("schema/records.py", "schema/enums.py", "schema/validation.py"):
        source = tmp_path / name
        before_source = source.read_text()
        source.write_text("def value():\n    return 2\n")
        assert calculation_manifest(package=tmp_path, versions=versions) != original
        source.write_text(before_source)
    assert manifest_digest(original) == manifest_digest(
        calculation_manifest(package=tmp_path, versions=versions)
    )
    changed.write_text(
        '"""different documentation"""\n# ignored comment\n' + kernel_source
    )
    assert calculation_manifest(package=tmp_path, versions=versions) == original
    for name in kernels:
        changed.write_text(
            kernel_source.replace(
                f"def {name}():\n    return 1", f"def {name}():\n    return 2"
            )
        )
        assert manifest_digest(
            calculation_manifest(package=tmp_path, versions=versions)
        ) != manifest_digest(original), name
    changed.write_text(kernel_source)
    # Sampling and display files are deliberately outside calculation provenance.
    before = calculation_manifest(package=tmp_path, versions=versions)
    (tmp_path / "model/scenario/random.py").write_text('raise RuntimeError("sampling")')
    (tmp_path / "model/scenario/view.py").write_text('raise RuntimeError("display")')
    assert calculation_manifest(package=tmp_path, versions=versions) == before
    changed.unlink()
    with pytest.raises(FileNotFoundError):
        calculation_manifest(package=tmp_path, versions=versions)


@pytest.mark.parametrize("key", [None, 1, "", " "])
def test_sample_capture_generate_share_scenario_key_validation(key):
    model, p = base(), plan()
    for operation in (
        lambda: market.sample(model, p, scenario_key=key),
        lambda: market.capture(model, p, scenario_key=key, inputs={}),
        lambda: market.generate(model, p, scenario_keys=[key]),
    ):
        with pytest.raises(ValueError):
            operation()


def test_manifest_encoding_matches_frozen_digest():
    fixture = json.loads(
        (
            Path(__file__).parent / "fixtures/scenarios/calculation-manifest-v1.json"
        ).read_text()
    )
    assert manifest_digest(fixture["manifest"]) == fixture["fingerprint"]


@pytest.mark.parametrize(
    "parameters,field,values,message",
    [
        ({}, "noise", [1, 0, 0], "noise draws outside"),
        ({}, "events", [0, -0.1, 0], "shock event draws"),
        ({"volatility_per_period": 0}, "innovations", [0, 0.1, 0], "zero volatility"),
    ],
)
def test_capture_and_model_loading_reject_draws_outside_support(
    parameters, field, values, message
):
    model, p = base(), plan(parameters=parameters)
    inputs = {parameter.name: parameter.quantity for parameter in p.parameters}
    inputs.update(innovations=[0, 0, 0], noise=[0, 0, 0], events=[0.5, 0.5, 0.5])
    accepted = market.capture(model, p, scenario_key="support", inputs=inputs)
    inputs[field] = values
    with pytest.raises(ValueError, match=message):
        market.capture(model, p, scenario_key="support", inputs=inputs)
    wire = accepted.to_data()
    target = next(
        v
        for v in wire["system"]["formulations"][0]["values"]
        if v["key"] == "input_" + field
    )
    for movement, value in zip(target["flow"]["movements"], values):
        movement["magnitude"] = value
    with pytest.raises(ValueError, match=message):
        Model.from_data(wire)


def test_calculation_identity_includes_the_actual_currency_catalogue(monkeypatch):
    from rangekeeper.model.scenario import implementation
    from rangekeeper.shared.units import UnitSystem

    monkeypatch.setattr(
        implementation, "default_units", UnitSystem(currencies=("AUD", "USD"))
    )
    before = implementation.calculation_manifest(versions=[])
    monkeypatch.setattr(
        implementation, "default_units", UnitSystem(currencies=("AUD",))
    )
    after = implementation.calculation_manifest(versions=[])
    assert before["currencies"] == ["AUD", "USD"]
    assert after["currencies"] == ["AUD"]
    assert (
        before["sources"] == after["sources"]
        and before["versions"] == after["versions"]
    )
    assert manifest_digest(before) != manifest_digest(after)


def test_realized_identity_matches_frozen_wire_encoding(monkeypatch):
    from rangekeeper.model.scenario import CalculationProvenance

    monkeypatch.setattr(market, "version", lambda name: "fixture")
    monkeypatch.setattr(market.platform, "python_version", lambda: "fixture")
    monkeypatch.setattr(
        market,
        "calculation_provenance",
        lambda: CalculationProvenance(
            name="rangekeeper.scenarios.market",
            fingerprint="scenario-calculation/v1:fixture",
            versions=(),
        ),
    )
    model, p = base(), plan()
    inputs = {parameter.name: parameter.quantity for parameter in p.parameters}
    inputs.update(innovations=[0, 0, 0], noise=[0, 0, 0], events=[0.5, 0.5, 0.5])
    captured = market.capture(model, p, scenario_key="identity-fixture", inputs=inputs)
    result = market.realize(model, p, draws=captured)
    expected = json.loads(
        (
            Path(__file__).parent / "fixtures/scenarios/realized-identity-v1.json"
        ).read_text()
    )
    assert str(result.model.id) == expected["revision"]
    assert str(result.realization.id) == expected["realization"]
    payload = result.model.to_data()
    payload["metadata"].pop("id")
    assert (
        hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        == expected["payload_sha256"]
    )
