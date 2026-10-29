"""Currency amounts in JSON, YAML, Parquet and JSON Schema (ADR-023)."""

import json as stdjson
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from jsonschema import Draft202012Validator

from rangekeeper import Model, Quantity
from rangekeeper.errors import Code
from rangekeeper.flow import Flow
from rangekeeper.io import json, yaml
from rangekeeper.model import Value, ValueKind
from rangekeeper.schema.runtime import exact_equal
from rangekeeper.schema.validation import schema_for
from rangekeeper.shared.errors import ValidationError

ROOT = Path(__file__).parents[2]


def money_model() -> Model:
    """Return a Model with a currency amount, a rate, an area and a currency Flow."""
    model = yaml.read(ROOT / "examples/schema/model.yaml", kind=Model)
    data = model.to_data()
    measures = {units: str(uuid4()) for units in ("AUD", "AUD/m^2", "m^2")}
    data["definitions"]["measures"] += [
        {"id": identity, "code": f"money_{units}", "name": units, "units": units}
        for units, identity in measures.items()
    ]

    def value(key, units, **content):
        return Value(
            id=uuid4(),
            key=key,
            kind=ValueKind.FLOW if "flow" in content else ValueKind.MEASUREMENT,
            measure=UUID(measures[units]),
            **content,
        ).to_data()

    values = [
        value(
            "price",
            "AUD",
            quantity=Quantity(magnitude=Decimal("1250000.5"), units="AUD"),
        ),
        value("rent", "AUD/m^2", quantity=Quantity(magnitude=450.5, units="AUD/m^2")),
        value("area", "m^2", quantity=Quantity(magnitude=1200.25, units="m^2")),
        value(
            "cash",
            "AUD",
            flow=Flow.from_events(
                dates=(date(2027, 1, 1), date(2028, 1, 1)),
                magnitudes=("-1250000.5", "0.000000000032"),
                units="AUD",
            ),
        ),
    ]
    data["system"]["entities"].append(
        {"id": str(uuid4()), "name": "Money", "characteristics": {"values": values}}
    )
    return Model.from_data(data)


def find(data, key):
    entities = data["system"]["entities"]
    values = entities[-1]["characteristics"]["values"]
    return next(v for v in values if v["key"] == key)


def test_json_writes_amounts_as_canonical_strings():
    data = stdjson.loads(json.dumps(money_model()))
    assert find(data, "price")["quantity"]["magnitude"] == "1250000.5"
    assert find(data, "rent")["quantity"]["magnitude"] == 450.5
    assert [m["magnitude"] for m in find(data, "cash")["flow"]["movements"]] == [
        "-1250000.5",
        "0.000000000032",
    ]


def test_json_is_strict_and_the_error_gives_the_canonical_text():
    data = stdjson.loads(json.dumps(money_model()))
    find(data, "price")["quantity"]["magnitude"] = 1.5
    with pytest.raises(ValidationError) as error:
        json.loads(stdjson.dumps(data), kind=Model)
    assert error.value.report.issues[0].code == Code.CURRENCY_AMOUNT
    assert "'1.5'" in str(error.value)
    find(data, "price")["quantity"]["magnitude"] = "1.50"
    with pytest.raises(ValidationError) as error:
        json.loads(stdjson.dumps(data), kind=Model)
    issue = error.value.report.issues[0]
    assert issue.code == Code.CURRENCY_AMOUNT
    assert issue.values["expected"] == "1.5"
    assert issue.path.endswith("/quantity/magnitude")
    find(data, "price")["quantity"]["magnitude"] = "1.5"
    find(data, "rent")["quantity"]["magnitude"] = "450.5"
    with pytest.raises(ValidationError) as error:
        json.loads(stdjson.dumps(data), kind=Model)
    assert error.value.report.issues[0].code == Code.CURRENCY_AMOUNT


def test_yaml_reads_numerals_from_their_source_text():
    model = money_model()
    text = yaml.dumps(model)
    assert "magnitude: '1250000.5'" in text
    authored = text.replace("magnitude: '1250000.5'", "magnitude: 1250000.50")
    assert authored != text
    assert exact_equal(yaml.loads(authored, kind=Model).to_data(), model.to_data())
    precise = text.replace("magnitude: '1250000.5'", "magnitude: 0.123456789012345")
    read = yaml.loads(precise, kind=Model).to_data()
    assert find(read, "price")["quantity"]["magnitude"] == "0.123456789012345"
    quoted = text.replace("magnitude: '1250000.5'", 'magnitude: "1250000.500"')
    assert exact_equal(yaml.loads(quoted, kind=Model).to_data(), model.to_data())


@pytest.mark.parametrize("codec", [json, yaml])
def test_codecs_round_trip_amounts_rates_and_geometry_exactly(codec):
    model = money_model()
    restored = codec.loads(codec.dumps(model), kind=Model)
    assert exact_equal(restored.to_data(), model.to_data())
    price = restored.value(UUID(find(model.to_data(), "price")["id"]))
    assert price.quantity.magnitude == Decimal("1250000.5")


def test_bundle_round_trips_amounts_and_stores_canonical_text(tmp_path):
    pytest.importorskip("pyarrow")
    duckdb = pytest.importorskip("duckdb")
    from rangekeeper.io.bundle import Reader, write

    model = money_model()
    write(tmp_path / "bundle", model)
    restored = Reader(tmp_path / "bundle").model()
    assert exact_equal(restored.to_data(), model.to_data())
    tables = list((tmp_path / "bundle").rglob("Quantity.parquet"))
    assert tables
    texts = duckdb.sql(
        f"select magnitude.v0 as text from read_parquet('{tables[0]}') "
        "where magnitude.tag = 0"
    ).fetchall()
    assert ("1250000.5",) in texts
    (amount,) = duckdb.sql(
        f"select cast(magnitude.v0 as decimal(38, 10)) from read_parquet('{tables[0]}') "
        "where magnitude.v0 = '1250000.5'"
    ).fetchone()
    assert amount == Decimal("1250000.5")


def test_json_schema_accepts_amount_text_and_numbers_only():
    validator = Draft202012Validator(schema_for("Quantity"))
    for magnitude in ("1.5", 1.5, "0", "-0.01"):
        assert validator.is_valid({"magnitude": magnitude, "units": "AUD"})
    for magnitude in ("1.50", "-0", "1e3", "01", "+1", ".5", "1."):
        assert not validator.is_valid({"magnitude": magnitude, "units": "AUD"})
