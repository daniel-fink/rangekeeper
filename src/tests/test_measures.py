import locale
import math
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pint
import pytest
import scipy.stats as ss
from pytest import approx

import rangekeeper as rk

# Pytests file.
# Note: gathers tests according to a naming convention.
# By default any file that is to contain tests must be named starting with 'test_',
# classes that hold tests must be named starting with 'Test',
# and any function in a file that should be treated as a test must also start with 'test_'.


locale = locale.setlocale(locale.LC_ALL, "en_AU")
units = rk.measure.Index.registry


class TestMeasures:
    currency = rk.measure.register_currency(registry=units)

    def test_currency(self):
        assert TestMeasures.currency.name == "Australian Dollar"
        assert TestMeasures.currency.units == "AUD"
        assert TestMeasures.currency.units.dimensionality == "[currency]"

    gfa = rk.measure.Measure(name="Gross Floor Area", units=units.meter**2)

    nsa = rk.measure.Measure(name="Net Sellable Area", units=units.sqm)

    rent = rk.measure.Measure(name="Rent", units=currency.units)

    rent_per_nsa = rk.measure.Measure(
        name="Rent per sqm of NSA", units=rent.units / nsa.units
    )

    def test_custom_derivative(self):
        assert (1 * TestMeasures.gfa.units).to("sqm") == units.Quantity("1 * sqm")
        assert TestMeasures.rent_per_nsa.units == "AUD / squaremeter"

    def test_eval_units(self):
        area = 100 * units.sqm
        value = 5 * (units.AUD / units.sqm)
        assert area * value == units.Quantity("500 AUD")

        result = eval("100 * units.sqm * 5 * (units.AUD / units.sqm)")
        assert result == area * value
        assert result.units == "AUD"
        area_check = area.to("km ** 2")
        print(area.to("km ** 2"))
        assert area_check.magnitude == approx(0.0001)

        quantity_check = 100 * rk.measure.Index.registry.dimensionless
        print(quantity_check)
        assert quantity_check.units == units.dimensionless

        print((value / (5 * units.hour)).units)


# class TestSpace:
# parent_type = graph.Type(
#     name='ParentType')
# child_type = graph.Type(
#     name='ChildType',
#     parent=parent_type)
# grandchild01_type = graph.Type(
#     name='Grandchild01Type')
# grandchild02_type = graph.Type(
#     name='Grandchild02Type')
# grandchild01_type.set_parent(child_type)
# grandchild02_type.set_parent(child_type)
# parent_type.set_children([child_type])
#
# def test_type_hierarchy(self):
#     assert TestSpace.parent_type.children == [TestSpace.child_type]
#     assert TestSpace.child_type.children == [TestSpace.grandchild01_type,
#                                              TestSpace.grandchild02_type]
#     assert TestSpace.grandchild01_type.__str__() == 'ParentType.ChildType.Grandchild01Type'
#     print(TestSpace.grandchild02_type)

# def test_space_init(self):
#     measurements = {
#         TestMeasures.gfa: 12.3 * TestMeasures.gfa.units,
#         TestMeasures.nsa: 4.56 * TestMeasures.nsa.units
#         }
#     parent_space = rk.space.Space(
#         name='Parent',
#         type='parent_type',
#         measurements=measurements)
#
#     assert parent_space.measurements[TestMeasures.gfa].units.dimensionality == '[length] ** 2'
#
#     parent_space.measurements[TestMeasures.rent] = 9.81 * TestMeasures.rent_per_nsa.units * \
#                                                    parent_space.measurements[TestMeasures.nsa]
#     assert parent_space.measurements[TestMeasures.rent].units == 'AUD'
#
