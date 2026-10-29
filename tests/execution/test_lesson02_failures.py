"""Lesson 02 cells 20–21: a product of two unknowns names its equation (#289)."""

import pytest

import rangekeeper as rk
from tests.execution.lesson02 import back, q


def test_cells_20_and_21_name_the_nonaffine_equation_and_unknowns():
    # cell 20
    both_free = back().fix(land_cost=q("20e6 AUD")).free("leverage", "coverage")
    both_free_outcome = rk.execution.solve(specification=both_free)
    assert both_free_outcome.status is rk.execution.Status.UNSUPPORTED
    (diagnostic,) = (
        item
        for item in both_free_outcome.diagnostics
        if item.code == rk.errors.Code.NONAFFINE_UNKNOWNS
    )
    assert diagnostic.values["equation"] == "noi = coverage * debt_service"
    assert list(diagnostic.values["unknowns"]) == ["coverage", "debt_service"]
    model = both_free.model
    assert [model.key_of(ref.target) for ref in diagnostic.references] == [
        "coverage",
        "debt_service",
    ]
    # cell 21
    with pytest.raises(rk.errors.UnsupportedError) as raised:
        both_free_outcome.raise_for_status()
    error = raised.value
    assert error.code is rk.errors.Code.NONAFFINE_UNKNOWNS
    assert error.equation == "noi = coverage * debt_service"
    assert error.unknowns == ("coverage", "debt_service")


def test_the_unknowns_of_two_entities_with_one_key_are_dotted_keys():
    draft = rk.Model(name="Two buildings").edit()
    for code in ("a", "b"):
        building = draft.add_entity(code=code)
        for key in ("noi", "coverage", "debt_service"):
            building.value(key=key, units="AUD" if key != "coverage" else "ratio")
        building.equations("noi = coverage * debt_service")
    model = draft.commit()
    specification = model.specify().fix({"a.noi": "1 AUD", "b.noi": "2 AUD"})
    outcome = rk.execution.solve(specification=specification)
    (diagnostic,) = (
        item
        for item in outcome.diagnostics
        if item.code == rk.errors.Code.NONAFFINE_UNKNOWNS
    )
    assert list(diagnostic.values["unknowns"]) == ["a.coverage", "a.debt_service"]
    assert [model.key_of(ref.target) for ref in diagnostic.references] == [
        "a.coverage",
        "a.debt_service",
    ]
    assert diagnostic.values["equation"] == "a.noi = a.coverage * a.debt_service"
