import pint
import pytest

import rangekeeper as rk


units = rk.measure.Index.registry


def area_measure(**changes):
    values = {
        "code": "project.area",
        "name": "Area",
        "units": units.sqm,
        "definition": "Total floor area",
    }
    values.update(changes)
    return rk.measure.Measure(**values)


def count_measure():
    return rk.measure.Measure(
        code="project.bedroom-count",
        name="Bedroom Count",
        units=units.dimensionless,
    )


class TestCharacteristics:
    def test_module_is_public(self):
        assert rk.graph.characteristics.Characteristics is not None

    def test_use_and_tenure_are_kinds(self):
        uses = rk.graph.Kind(
            code="abs.fcb",
            name="Functional Classification of Buildings",
            scheme="ABS FCB",
            edition="2021",
        )
        office = uses.define(code="231", name="Offices")
        tenures = rk.graph.Kind(
            code="abs.tend",
            name="Tenure Type",
            scheme="ABS TEND",
            edition="2026",
        )
        rented = tenures.define(code="4", name="Rented")

        characteristics = rk.graph.characteristics.Characteristics(
            use=office,
            tenure=rented,
        )

        assert characteristics.use is office
        assert characteristics.use.scheme == "ABS FCB"
        assert characteristics.tenure is rented
        assert characteristics.tenure.scheme == "ABS TEND"

        with pytest.raises(TypeError, match="use must be a Kind"):
            rk.graph.characteristics.Characteristics(use="office")
        with pytest.raises(TypeError, match="tenure must be a Kind"):
            rk.graph.characteristics.Characteristics(tenure="rented")

    def test_compatible_quantity_preserves_supplied_units(self):
        characteristics = rk.graph.characteristics.Characteristics()
        measure = area_measure()
        supplied = 1_000 * units.sqft

        characteristics.set_measure(measure, supplied)

        assert characteristics.require_measure(measure) is supplied
        assert characteristics.require_measure(measure).units == units.sqft

    def test_incompatible_dimensions_are_rejected(self):
        characteristics = rk.graph.characteristics.Characteristics()

        with pytest.raises(pint.DimensionalityError):
            characteristics.set_measure(area_measure(), 10 * units.meter)

    def test_multiple_measures_and_missing_behavior(self):
        characteristics = rk.graph.characteristics.Characteristics()
        area = area_measure()
        count = count_measure()
        area_quantity = 100 * units.sqm
        count_quantity = 3 * units.dimensionless

        characteristics.set_measure(area, area_quantity)
        characteristics.set_measure(count, count_quantity)

        assert characteristics.get_measure(area) is area_quantity
        assert characteristics.require_measure(count) is count_quantity

        missing = rk.measure.Measure(
            code="project.parking-count",
            name="Parking Count",
            units=units.dimensionless,
        )
        assert characteristics.get_measure(missing) is None
        with pytest.raises(KeyError, match="project.parking-count"):
            characteristics.require_measure(missing)

    def test_remove_measure(self):
        measure = area_measure()
        quantity = 100 * units.sqm
        characteristics = rk.graph.characteristics.Characteristics(
            measures={measure: quantity}
        )

        assert characteristics.remove_measure(measure) is quantity
        assert characteristics.get_measure(measure) is None
        with pytest.raises(KeyError, match="project.area"):
            characteristics.remove_measure(measure)

    def test_mutable_defaults_are_isolated(self):
        first = rk.graph.characteristics.Characteristics()
        second = rk.graph.characteristics.Characteristics()

        first.set_measure(area_measure(), 100 * units.sqm)
        first.features["balcony"] = True

        assert second.measures == {}
        assert second.features == {}

    def test_reconstructed_measure_uses_stable_identity(self):
        original = area_measure()
        reconstructed = rk.measure.Measure.from_record(original.to_record())
        quantity = 100 * units.sqm
        characteristics = rk.graph.characteristics.Characteristics(
            measures={original: quantity}
        )

        assert characteristics.require_measure(reconstructed) is quantity
        characteristics.set_measure(reconstructed, 200 * units.sqft)
        assert len(characteristics.measures) == 1
        assert characteristics.require_measure(original).magnitude == 200
        assert characteristics.require_measure(original).units == units.sqft

    def test_conflicting_reconstruction_is_rejected(self):
        original = area_measure()
        conflicting = area_measure(definition="A different definition")
        characteristics = rk.graph.characteristics.Characteristics(
            measures={original: 100 * units.sqm}
        )

        with pytest.raises(ValueError, match="conflicting definitions"):
            characteristics.get_measure(conflicting)

    def test_initial_mapping_is_validated_and_copied(self):
        measure = area_measure()
        supplied = {measure: 100 * units.sqm}
        characteristics = rk.graph.characteristics.Characteristics(measures=supplied)

        supplied.clear()
        assert characteristics.require_measure(measure).magnitude == 100

        with pytest.raises(pint.DimensionalityError):
            rk.graph.characteristics.Characteristics(
                measures={measure: 100 * units.meter}
            )

    def test_measure_and_quantity_types_are_validated(self):
        characteristics = rk.graph.characteristics.Characteristics()

        with pytest.raises(TypeError, match="measure must be"):
            characteristics.set_measure("area", 100 * units.sqm)
        with pytest.raises(TypeError, match="Pint Quantity"):
            characteristics.set_measure(area_measure(), 100)
