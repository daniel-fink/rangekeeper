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

    def test_labels_accept_multiple_classification_keys(self):
        uses = rk.graph.Taxonomy(
            code="ABS FCB",
            name="Functional Classification of Buildings",
        ).define(code="abs.fcb", name="Building Uses")
        office = uses.define(code="231", name="Offices")
        retail = uses.define(code="233", name="Shops")
        tenures = rk.graph.Taxonomy(
            code="ABS TEND",
            name="Tenure Type",
        ).define(code="abs.tend", name="Tenures")
        rented = tenures.define(code="4", name="Rented")

        characteristics = rk.graph.characteristics.Characteristics(
            labels={"use": [office, retail], "tenure": (rented,)},
        )

        assert characteristics.labels["use"] == (office, retail)
        assert characteristics.labels["tenure"] == (rented,)
        assert characteristics.labels["use"][0].taxonomy.code == "ABS FCB"
        assert characteristics.labels["tenure"][0].taxonomy.code == "ABS TEND"

    @pytest.mark.parametrize("key", ["", "   ", 1])
    def test_label_key_is_a_non_empty_string(self, key):
        with pytest.raises((TypeError, ValueError), match="label key"):
            rk.graph.Characteristics(labels={key: ()})

    @pytest.mark.parametrize("values", ["office", 1, ["office"]])
    def test_label_values_are_classification_iterables(self, values):
        with pytest.raises(TypeError, match="label values"):
            rk.graph.Characteristics(labels={"use": values})

    def test_labels_mapping_is_copied_and_values_are_normalized(self):
        office = rk.graph.Taxonomy(code="project.use", name="Uses").define(
            code="office", name="Office"
        )
        supplied_values = [office]
        supplied = {"use": supplied_values}

        characteristics = rk.graph.Characteristics(labels=supplied)
        supplied.clear()
        supplied_values.clear()

        assert characteristics.labels == {"use": (office,)}

    def test_duplicate_scheme_aware_label_keys_are_rejected(self):
        first = rk.graph.Taxonomy(code="ABS FCB", name="Uses").define(
            code="231", name="Office"
        )
        duplicate = rk.graph.Taxonomy(code="ABS FCB", name="Other Uses").define(
            code="231", name="Offices"
        )

        with pytest.raises(ValueError, match="repeat"):
            rk.graph.Characteristics(labels={"use": (first, duplicate)})

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
        first.labels["use"] = ()

        assert second.labels == {}
        assert second.measures == {}
        assert second.features == {}

    def test_features_accept_rich_runtime_values(self):
        runtime_value = object()
        characteristics = rk.graph.Characteristics(
            features={"flow": runtime_value, "events": [{"year": 2030}]}
        )

        assert characteristics.features["flow"] is runtime_value
        assert characteristics.features["events"] == [{"year": 2030}]

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
