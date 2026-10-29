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
    # cell 21
    with pytest.raises(rk.errors.UnsupportedError) as raised:
        both_free_outcome.raise_for_status()
    error = raised.value
    assert error.code is rk.errors.Code.NONAFFINE_UNKNOWNS
    assert error.equation == "noi = coverage * debt_service"
    assert error.unknowns == ("coverage", "debt_service")
