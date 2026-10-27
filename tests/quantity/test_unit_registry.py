"""Curated unit registry (ADR-016): aliases, traps, suggestions and Model.unit_system."""

import csv
import gzip
import json
import re
from pathlib import Path
from uuid import uuid4

import pytest

from rangekeeper.model import (
    Characteristics,
    Definitions,
    Entity,
    Measure,
    Metadata,
    Model,
    System,
    Update,
    Value,
    ValueKind,
)
from rangekeeper.model.system import View, reducers
from rangekeeper.model.system.reduction import Reduction
from rangekeeper.model.system.selection import select_value
from rangekeeper.model.system.table import ValueColumn, to_table
from rangekeeper.quantity import Quantity, UnitSystem, default_units, minor_unit
from rangekeeper.shared.errors import UnitError, ValidationError

ROOT = Path(__file__).resolve().parents[2]

# Unit text in the walkthrough's proposed cells (#201) and lesson data.
WALKTHROUGH_UNITS = (
    "AUD",
    "USD",
    "ratio",
    "% pa",
    "AUD pa",
    "USD pa",
    "AUD per sqm pa",
    "AUD per sqm",
    "USD per month",
    "1/year",
    "sqm",
    "%",
    "year",
    "dwelling",
    "dimensionless",
    "m²",
    "AUD/year",
    "AUD/month",
    "AUD/day",
    "AUD/meter**2",
    "AUD/meter**2/month",
    "AUD/dwelling/month",
    "AUD**2/day**2",
    "centimeter ** 2",
    "cm",
    "percent",
    "month",
    "second",
    "foot",
    "squaremeter",
)


def _units_in(value, found):
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and (key == "units" or key.endswith("_units")):
                found.add(item)
            _units_in(item, found)
    elif isinstance(value, list):
        for item in value:
            _units_in(item, found)


def example_units() -> set[str]:
    """Collect every unit string in examples/ data files, code and notebooks."""
    found: set[str] = set()
    for path in (ROOT / "examples").rglob("*"):
        parts = path.relative_to(ROOT).parts
        if any(part.startswith(".") or part.endswith(".egg-info") for part in parts):
            continue
        if path.suffix in (".py", ".ipynb", ".md"):
            found.update(
                re.findall(
                    r"units\\?[\"']?\s*[=:]\s*\\?[\"']([^\"'\\]+)",
                    path.read_text(encoding="utf-8"),
                )
            )
        if path.suffix == ".json":
            _units_in(json.loads(path.read_text(encoding="utf-8")), found)
        elif path.name.endswith(".json.gz"):
            _units_in(json.loads(gzip.decompress(path.read_bytes())), found)
        elif path.suffix == ".csv":
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    found.update(
                        value
                        for key, value in row.items()
                        if key and "unit" in key.lower() and value
                    )
    return found


def test_example_data_records_units():
    assert {"meter", "meter ** 2", "AUD", "dimensionless", "m²"} <= example_units()


@pytest.mark.parametrize(
    "text", sorted(example_units() | set(WALKTHROUGH_UNITS)), ids=repr
)
def test_unit_text_round_trips(text):
    canonical = default_units.multiply(text, "dimensionless")
    assert default_units.multiply(canonical, "dimensionless") == canonical
    assert default_units.compatible(text, canonical)
    converted = default_units.convert(Quantity(magnitude=1, units=text), to=canonical)
    assert converted.magnitude == pytest.approx(1)


@pytest.mark.parametrize(
    "alias,canonical,factor",
    [
        ("sqm", "meter ** 2", 1),
        ("squaremeter", "m^2", 1),
        ("sqft", "foot ** 2", 1),
        ("squarefoot", "sqft", 1),
        ("sqft", "sqm", 0.09290304),
        ("pa", "1/year", 1),
        ("AUD pa", "AUD/year", 1),
        ("metre", "meter", 1),
        ("litre", "dm ** 3", 1),
        ("ha", "sqm", 10_000),
        ("km", "m", 1000),
        ("GL", "m ** 3", 1e6),
        ("µm", "um", 1),
        ("%", "ratio", 0.01),
        ("percent", "dimensionless", 0.01),
        ("count", "dimensionless", 1),
        ("ratio", "dimensionless", 1),
        ("dwellings", "dwelling", 1),
        ("yr", "year", 1),
        ("quarter", "month", 3),
        ("hr", "minute", 60),
    ],
)
def test_aliases(alias, canonical, factor):
    converted = default_units.convert(Quantity(magnitude=1, units=alias), to=canonical)
    assert converted.magnitude == pytest.approx(factor)


def test_per_annum_is_per_year_not_picoyear():
    seven = default_units.parse_quantity("7 % pa")
    assert seven == Quantity(magnitude=7.0, units="% pa")
    assert default_units.convert(seven, to="1/year").magnitude == pytest.approx(0.07)
    assert default_units.compatible("AUD pa", "AUD/year")
    assert not default_units.compatible("AUD pa", "AUD")


def test_per_is_division():
    rent = default_units.parse_quantity("750 AUD per sqm pa")
    assert rent.magnitude == 750
    assert default_units.compatible(rent.units, "AUD / m ** 2 / year")
    assert default_units.compatible("per sqm", "1 / sqm")


def test_quantity_text():
    assert default_units.parse_quantity("20e6 AUD") == Quantity(
        magnitude=20e6, units="AUD"
    )
    assert default_units.parse_quantity("-5 %").magnitude == -5
    with pytest.raises(UnitError) as error:
        default_units.parse_quantity("5")
    assert error.value.suggestions == ("5 dimensionless",)
    with pytest.raises(UnitError):
        default_units.parse_quantity("AUD 5")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("0.5 dwelling per 100 sqm", "0.005 dwelling per sqm"),
        ("10 AUD/100 sqm", "0.1 AUD/sqm"),
        ("2 dwelling per 1000 sqm", "0.002 dwelling per sqm"),
    ],
)
def test_numbers_inside_units_fail_with_rescaled_suggestion(text, expected):
    with pytest.raises(UnitError) as error:
        default_units.parse_quantity(text)
    assert error.value.suggestions == (expected,)
    assert expected in str(error.value)


@pytest.mark.parametrize(
    "text,suggestions",
    [
        ("pct", ("%", "percent")),
        ("$", ("AUD", "USD", "CAD", "NZD", "SGD", "HKD")),
        ("A$", ("AUD",)),
        ("US$/sqm", ("USD",)),
        ("€", ("EUR",)),
        ("£", ("GBP",)),
        ("ms", ("s",)),
        ("kyr", ("yr",)),
        ("Myr", ("yr",)),
        ("kiloyear", ("year",)),
        ("millisecond", ("second",)),
        ("kAUD", ("AUD",)),
        ("AUDm", ("AUD",)),
        ("aud", ("AUD",)),
        ("Pa", ("pa",)),
        ("SQM", ("sqm",)),
        ("m2", ("sqm", "m^2")),
        ("p.a.", ("pa",)),
        ("a", ("year", "pa")),
        ("dwelling per 100 sqm", ("0.01 dwelling per sqm",)),
    ],
)
def test_traps_fail_with_suggestions(text, suggestions):
    with pytest.raises(UnitError) as error:
        default_units.validate_units(text)
    assert error.value.suggestions == suggestions
    assert "did you mean" in str(error.value) or "such as" in str(error.value)


def test_close_spellings_are_suggested():
    with pytest.raises(UnitError) as error:
        default_units.validate_units("metr")
    assert "meter" in error.value.suggestions
    with pytest.raises(UnitError) as error:
        default_units.validate_units("dwellng")
    assert "dwelling" in error.value.suggestions


@pytest.mark.parametrize(
    "text", ["kelvin", "degC", "kg", "kWh", "furlong", "AUD million", "pc", "", " "]
)
def test_units_outside_the_registry_fail(text):
    with pytest.raises(UnitError):
        default_units.validate_units(text)


def test_scaled_currency_and_restricted_catalogue():
    with pytest.raises(UnitError, match="scale"):
        default_units.validate_units("AUD million")
    with pytest.raises(UnitError, match="outside this unit system"):
        UnitSystem(currencies=("AUD",)).validate_units("USD")


@pytest.mark.parametrize(
    "code,expected",
    [
        ("AUD", 2),
        ("JPY", 0),
        ("KWD", 3),
        ("CLF", 4),
        ("MGA", 2),
        ("MRU", 2),
        ("XAU", None),
        ("XXX", None),
    ],
)
def test_minor_units(code, expected):
    assert minor_unit(code) == expected
    assert default_units.minor_unit(code) == expected


def test_every_currency_has_a_minor_unit_or_none():
    for code in default_units.currencies:
        assert minor_unit(code) in (None, 0, 1, 2, 3, 4)
    with pytest.raises(UnitError):
        minor_unit("ABC")
    with pytest.raises(UnitError):
        UnitSystem(currencies=("AUD",)).minor_unit("USD")


def test_register_and_alias_return_new_systems():
    extended = default_units.register("storey", aliases=("storeys_",)).alias(
        "level", "storey"
    )
    assert extended.compatible("storey", "level")
    assert not extended.compatible("storey", "dwelling")
    assert extended.multiply("AUD", "level") == "AUD * storey"
    land = default_units.register("rood", definition="1011.7141056 * sqm")
    assert land.convert(
        Quantity(magnitude=1, units="rood"), to="sqm"
    ).magnitude == pytest.approx(1011.7141056)
    with pytest.raises(UnitError):
        default_units.validate_units("storey")
    assert extended != default_units and default_units.definitions == ()
    for call in (
        lambda: default_units.register("sqm"),
        lambda: default_units.register("AUD"),
        lambda: default_units.register("two words"),
        lambda: default_units.alias("pa", "year"),
        lambda: default_units.alias("level", "storey"),
        lambda: default_units.register("bad", definition="1 * nothing"),
    ):
        with pytest.raises(UnitError):
            call()


def model_with(units: UnitSystem, *, unit: str = "storey") -> Model:
    measure = Measure(id=uuid4(), code="height", name="Height", units=unit)
    value = Value(
        id=uuid4(),
        key="levels",
        kind=ValueKind.MEASUREMENT,
        measure=measure.id,
        quantity=Quantity(magnitude=12, units=unit),
    )
    entity = Entity(
        id=uuid4(), code="A", characteristics=Characteristics(values=(value,))
    )
    return Model.create(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
        definitions=Definitions(measures=(measure,)),
        system=System(entities=(entity,)),
        units=units,
    )


def test_model_unit_system_is_public_and_kept_by_revisions():
    storeys = default_units.register("storey").alias("level", "storey")
    model = model_with(storeys)
    assert model.unit_system is storeys
    revised = model.revise(
        Update(
            metadata=model.metadata.replace(id=uuid4(), previous=model.id, name="next")
        )
    )
    assert revised.unit_system is storeys
    assert (
        Model.from_data(model_with(default_units, unit="m").to_data()).unit_system
        == default_units
    )
    with pytest.raises((UnitError, ValidationError)):
        model_with(default_units)


def test_derived_operations_default_to_the_model_unit_system():
    storeys = default_units.register("storey").alias("level", "storey")
    model = model_with(storeys)
    view = View(model)
    population = view.quantities("levels", units="level")
    assert [q.magnitude for q in population.quantities] == [12]
    table = to_table(view, columns=(ValueColumn("levels", "levels", "level"),))
    assert table.rows[0].values["levels"] == 12
    aggregation = view.aggregate(
        Reduction(select=select_value("levels"), reducer=reducers.sum, units="level")
    )
    assert aggregation[model.find_entities(code="A")[0].id].magnitude == 12
    with pytest.raises(UnitError):
        to_table(
            view,
            columns=(ValueColumn("levels", "levels", "level"),),
            units=default_units,
        )


def test_registry_spellings_are_unique():
    spellings = default_units._spellings()
    assert len(spellings) == len(set(spellings))
