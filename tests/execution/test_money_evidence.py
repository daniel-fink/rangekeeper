"""Currency amounts in solved Runs: convention, assignments and residuals (ADR-023)."""

from decimal import Decimal

from rangekeeper import Quantity, money
from rangekeeper.run import ImplementationKind, SolutionStatus
from tests.execution.test_execution import (
    CAPITAL,
    binary,
    execute,
    formulation,
    literal,
    output,
    reference,
    setup,
    spec,
)


def test_a_solved_run_records_the_money_convention():
    store, model = setup()
    run = execute(store, spec(model=model))
    assert run.report.status.solution == SolutionStatus.FEASIBLE
    conventions = [
        item
        for item in run.report.runtime.implementations
        if item.kind is ImplementationKind.CONVENTION
    ]
    assert [(item.name, item.version) for item in conventions] == [
        ("rangekeeper.money", money.CONVENTION)
    ]


def test_an_assigned_amount_is_copied_without_change():
    store, model = setup()
    specification = spec("specification-inverse", model=model)
    (assigned,) = [
        a.quantity
        for a in specification.record.assignments
        if a.target.target == CAPITAL
    ]
    assert assigned.magnitude == Decimal("10000000")
    run = execute(store, specification)
    assert run.report.status.solution == SolutionStatus.FEASIBLE
    published = output(store, run).value(CAPITAL).quantity
    assert published.to_data() == assigned.to_data()


def test_residuals_and_tolerances_in_currency_units_are_amounts():
    store, _ = setup()
    predicate = binary("equal", reference(CAPITAL), literal(11000000))
    run = execute(store, spec(formulations=[formulation(predicate)]))
    assert run.report.status.solution == SolutionStatus.FEASIBLE
    found = [
        quantity
        for diagnostic in run.report.diagnostics
        for quantity in (diagnostic.residual, diagnostic.tolerance)
        if quantity is not None and money.is_currency(quantity.units)
    ]
    assert found
    assert all(type(q.to_data()["magnitude"]) is str for q in found)
    residual = Quantity(magnitude=3.2e-11, units="AUD")
    assert residual.to_data()["magnitude"] == "0.000000000032"
