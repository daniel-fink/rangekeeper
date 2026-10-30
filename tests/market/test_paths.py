"""The market paths document: access, construction, regeneration and storage (#298)."""

from collections.abc import Sequence
from datetime import date

import pytest

import rangekeeper as rk
from rangekeeper.errors import (
    Code,
    ContractError,
    MissingReferenceError,
    UnitError,
    UnknownExtensionError,
    ValidationError,
)
from rangekeeper.io import DirectoryStore, MemoryStore, json
from rangekeeper.market import (
    LibraryVersion,
    MarketPath,
    PathCapture,
    PathGenerator,
    PathParameter,
    Paths,
    PathSeries,
    generators,
)
from rangekeeper.schema.records import MarketPath as MarketPathRecord
from rangekeeper.schema.records import PathAmounts

YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2030, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)


def flow(*magnitudes: float, units: str = "ratio") -> rk.flow.Flow:
    return rk.flow.Flow.from_periods(periods=YEARS, magnitudes=magnitudes, units=units)


def histories() -> Paths:
    return Paths.from_flows(
        flows={
            "recovery": {"rent_index": flow(1, 1.1, 1.2), "cost": flow(1, 1, 1)},
            "downturn": {"rent_index": flow(1, 0.9, 0.8), "cost": flow(1, 1.1, 1.2)},
        },
        lag={"rent_index": "1 month", "cost": "0 days"},
        name="Histories",
    )


class Ramp:
    """A test generator: each path rises by its parameter, plus the seed."""

    def generate(
        self,
        *,
        parameters: Sequence[PathParameter],
        periods: Sequence[rk.duration.Period],
        seed: int | None,
        count: int,
    ) -> Paths:
        (step,) = parameters
        assert step.quantity is not None
        rise = step.quantity.number + (seed or 0) / 100
        members = [
            MarketPathRecord(
                key=f"path_{index + 1}",
                amounts=(
                    PathAmounts(
                        series=step.series,
                        magnitudes=tuple(
                            1 + rise * (index + 1) * i for i in range(len(periods))
                        ),
                    ),
                ),
            )
            for index in range(count)
        ]
        registration = generators.describe(self)
        return Paths.create(
            periods=periods,
            series=(
                PathSeries(
                    name=step.series,
                    units="ratio",
                    lag=rk.Quantity(text="0 days"),
                ),
            ),
            members=members,
            capture=PathCapture(
                generator=registration.name,
                fingerprint=registration.fingerprint,
                seed=seed,
                count=count,
                parameters=tuple(parameters),
                streams=(),
                versions=(LibraryVersion(name="ramp", version="1"),),
            ),
        )


RAMP = Ramp()
generators.register(name="test-ramp", implementation=RAMP, replace=True)


def ramp(seed: int) -> Paths:
    parameter = PathParameter(
        series="rent_index", name="step", quantity=rk.Quantity(text="2 %")
    )
    return RAMP.generate(parameters=(parameter,), periods=YEARS, seed=seed, count=3)


def test_paths_give_each_path_and_the_flow_of_each_series():
    paths = histories()
    assert paths.keys == ("recovery", "downturn")
    assert paths.names == ("rent_index", "cost")
    assert len(paths) == 2 and "recovery" in paths and list(paths) == list(paths.keys)
    assert paths.periods == tuple(YEARS)
    path = paths["downturn"]
    assert isinstance(path, MarketPath) and path.key == "downturn"
    assert path["rent_index"] == flow(1, 0.9, 0.8)
    assert list(path) == ["rent_index", "cost"]
    assert paths.metadata.name == "Histories"


def test_mean_gives_one_flow_period_by_period():
    mean = histories().mean(name="rent_index")
    assert mean.units == "ratio"
    assert [m.number for m in mean.movements] == pytest.approx([1, 1, 1])


def test_availability_is_the_end_of_each_period_plus_the_lag():
    paths = histories()
    assert paths.available(name="rent_index") == (
        date(2028, 2, 1),
        date(2029, 2, 1),
        date(2030, 2, 1),
    )
    assert paths.available(name="cost")[0] == date(2028, 1, 1)
    assert str(paths.series(name="rent_index").lag) == "1 month"


def test_a_missing_key_or_series_names_the_ones_that_exist():
    paths = histories()
    with pytest.raises(MissingReferenceError) as missing:
        paths["boom"]
    assert missing.value.candidates == ("recovery", "downturn")
    with pytest.raises(MissingReferenceError) as series:
        paths.mean(name="rent")
    assert series.value.candidates == ("rent_index", "cost")


def test_paths_from_data_have_no_generator_and_cannot_regenerate():
    paths = histories()
    capture = paths.capture
    assert (capture.generator, capture.seed, capture.count) == (None, None, 2)
    with pytest.raises(ContractError):
        paths.regenerate(seed=1)


def test_the_uuid_is_a_digest_of_the_content():
    assert histories().id == histories().id
    assert histories() == histories()
    renamed = Paths.from_flows(flows={"a": {"rent_index": flow(1, 1, 1)}}, name="A")
    other = Paths.from_flows(flows={"a": {"rent_index": flow(1, 1, 1)}}, name="B")
    assert renamed.id != other.id and renamed != other


def test_from_flows_checks_the_series_periods_units_and_lags():
    with pytest.raises(ContractError):
        Paths.from_flows(
            flows={"a": {"x": flow(1, 1, 1)}, "b": {"y": flow(1, 1, 1)}},
        )
    with pytest.raises(ContractError) as units:
        Paths.from_flows(
            flows={"a": {"x": flow(1, 1, 1)}, "b": {"x": flow(1, 1, 1, units="AUD")}},
        )
    assert units.value.code is Code.ALIGNMENT_DIFFER
    with pytest.raises(ContractError):
        Paths.from_flows(flows={"a": {"x": flow(1, 1, 1)}}, lag="-1 month")
    with pytest.raises(UnitError):
        Paths.from_flows(flows={"a": {"x": flow(1, 1, 1)}}, lag="1.5 months")
    with pytest.raises(ContractError):
        Paths.from_flows(flows={"a": {"x": flow(1, 1, 1)}}, lag={"y": "0 days"})
    dated = rk.flow.Flow(amounts={date(2027, 1, 1): 1.0}, units="ratio")
    with pytest.raises(ContractError):
        Paths.from_flows(flows={"a": {"x": dated}})


def test_validation_reports_a_document_that_disagrees_with_itself():
    data = histories().to_data()
    data["members"][1]["amounts"][0]["magnitudes"] = [1, 2]
    with pytest.raises(ValidationError) as short:
        Paths.from_data(data)
    assert "2 amounts for 3 Periods" in str(short.value)
    data = histories().to_data()
    data["members"][1]["key"] = "recovery"
    with pytest.raises(ValidationError) as twice:
        Paths.from_data(data)
    assert twice.value.code is Code.UNIQUE
    data = histories().to_data()
    data["capture"]["count"] = 3
    with pytest.raises(ValidationError):
        Paths.from_data(data)
    data = histories().to_data()
    data["capture"]["generator"] = "test-ramp"
    with pytest.raises(ValidationError):
        Paths.from_data(data)


def test_the_document_has_the_same_verbs_as_the_others():
    paths = histories()
    assert paths.validate().valid
    assert paths.check() is paths
    assert paths.check(resolver=MemoryStore()) is paths
    report = paths.validate(units=rk.quantity.UnitSystem(currencies=("USD",)))
    assert report.valid


def test_regenerate_finds_the_generator_and_makes_the_paths_again():
    paths = ramp(seed=1)
    assert isinstance(RAMP, PathGenerator)
    assert paths.capture.generator == "test-ramp"
    assert paths.capture.fingerprint == generators.describe(RAMP).fingerprint
    assert paths.regenerate(seed=1) == paths
    assert paths.regenerate(seed=1).id == paths.id
    other = paths.regenerate(seed=2)
    assert other != paths and other.keys == paths.keys
    assert other["path_1"]["rent_index"] != paths["path_1"]["rent_index"]


def test_regenerate_needs_a_registered_generator():
    data = ramp(seed=1).to_data()
    data["capture"]["generator"] = "missing"
    with pytest.raises(UnknownExtensionError):
        Paths.from_data(data).regenerate(seed=1)


def test_codecs_and_stores_keep_the_exact_revision(tmp_path):
    paths = histories()
    assert json.loads(text=json.dumps(paths), kind=Paths) == paths
    for store in (MemoryStore(), DirectoryStore(tmp_path / "store")):
        assert store.put(paths) == paths.id
        assert store.put(paths) == paths.id  # an identical write changes nothing
        assert store.load_paths(paths.id) == paths
    directory = DirectoryStore(tmp_path / "store")
    with pytest.raises(rk.errors.ReferenceTypeError):
        directory.load_model(paths.id)


def test_a_bundle_carries_the_paths(tmp_path):
    pytest.importorskip("pyarrow")
    from rangekeeper.io.bundle import Reader, write

    paths = ramp(seed=3)
    model = rk.Model(name="Plan")
    write(root=tmp_path / "bundle", model=model, documents=(paths,))
    reader = Reader(root=tmp_path / "bundle")
    assert reader.load_paths(paths.id) == paths
    copy = MemoryStore()
    reader.copy_to(copy)
    assert copy.load_paths(paths.id) == paths


def test_a_flow_fixes_a_flow_value_period_by_period():
    draft = rk.Model(name="Index").edit()
    project = draft.add_entity(code="project", classification="project")
    project.flow(key="rent_index", units="ratio", periods=YEARS)
    project.flow(key="rent", units="AUD", periods=YEARS)
    project.value(key="base_rent", units="AUD")
    project.equations("rent = rent_index * base_rent")
    model = draft.commit()
    paths = histories()
    spec = model.specify().fix(
        base_rent="100 AUD", rent_index=paths.mean(name="rent_index")
    )
    fixed = [row for row in spec.roles.rows if row.values["key"] == "rent_index"]
    assert [row.values["quantity"].number for row in fixed] == pytest.approx([1, 1, 1])
    longer = rk.flow.Flow.from_periods(
        periods=YEARS.extend(count=1), magnitudes=[1, 1, 1, 1], units="ratio"
    )
    with pytest.raises(ContractError) as differ:
        model.specify().fix(rent_index=longer)
    assert differ.value.code is Code.ALIGNMENT_DIFFER
    with pytest.raises(UnitError):
        model.specify().fix(rent_index=flow(1, 1, 1, units="AUD"))
