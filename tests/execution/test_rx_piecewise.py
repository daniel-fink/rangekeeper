"""``rx.max`` written in text or with ``rx`` reaches the piecewise solve (#278, #308).

The catalogue's ``rx.max`` and ``rx.min`` have the Function codes that
``execution.piecewise`` recognises. A Flow-valued ``rx.max`` reaches the solve
as one call for each period: ``per_period`` writes a Flow-valued equation as
one scalar equation for each period, over the Movements of its Flows.
"""

import importlib.util
import itertools
from datetime import date
from itertools import accumulate

import pytest

import rangekeeper as rk
import rangekeeper.expressions as rx
from rangekeeper.execution import solve
from rangekeeper.execution.piecewise import KINDS, Pieces
from rangekeeper.model.expression.catalogue import functions
from rangekeeper.model.expression.lowering import per_period
from rangekeeper.model.expression.text import read
from rangekeeper.quantity import isclose
from rangekeeper.schema.records import Expression

pytestmark = pytest.mark.skipif(
    not all(importlib.util.find_spec(name) for name in ("pyomo", "highspy")),
    reason="requires the optional execution extra",
)

YEARS = rk.duration.Periods(
    start=date(2027, 1, 1), frequency=rk.duration.Frequency.YEAR, count=4
)
NET = (-55e6, -40e6, 5e6, 140e6)
EQUITY = 50e6
# The equity-first cascade of lesson 03 cell 12, without interest (D2).
CASCADE = (
    "need = -net.cumulative()",
    "principal = rx.max(0 AUD, need - equity)",
    "draws = principal.diff()",
)


def aud(magnitude: float) -> rk.Quantity:
    return rk.Quantity(magnitude=magnitude, units="AUD")


def strip(data: object) -> object:
    if isinstance(data, dict):
        return {k: strip(v) for k, v in data.items() if k != "id"}
    if isinstance(data, list):
        return [strip(item) for item in data]
    return data


class Names:
    """The names of equation text on one entity handle."""

    units = rk.quantity.default_units

    def __init__(self, project) -> None:
        self.project = project

    def value(self, path: tuple[str, ...]):
        return self.project.ref(key=".".join(path))


def declared():
    """Return a draft of the declared Model, its project and the Movements of its Flows.

    The Movements come from the committed declarations, so that each Flow
    equation can be written over them.
    """
    draft = rk.Model(name="Cascade").edit()
    project = draft.add_entity(code="project", classification="project")
    project.value(key="equity", units="AUD")
    for key in ("net", "need", "principal", "draws"):
        project.flow(key=key, units="AUD", periods=YEARS)
    model = draft.commit()
    shapes = {
        model.value(key=key).id: [m.id for m in model.value(key=key).flow.movements]
        for key in ("net", "need", "principal", "draws")
    }
    draft = model.edit()
    return draft, draft.entity(code="project"), shapes


def in_python(project) -> tuple[Expression, ...]:
    need, net = project.ref(key="need"), project.ref(key="net")
    principal, draws = project.ref(key="principal"), project.ref(key="draws")
    equity = project.ref(key="equity")
    terms = (
        need == -net.cumulative(),
        principal == rx.max("0 AUD", need - equity),
        draws == principal.diff(),
    )
    return tuple(term.to_expression() for term in terms)


def test_max_and_min_have_the_codes_that_the_solve_recognises():
    assert functions.function(name="max").code in KINDS
    assert functions.function(name="min").code in KINDS


def test_a_flow_max_is_one_call_for_each_period():
    _, project, shapes = declared()
    (equation,) = in_python(project)[1:2]
    lowered = per_period(expression=equation, flows=shapes)
    assert len(lowered) == len(YEARS)
    code = functions.function(name="max").id
    for row in lowered:
        (call,) = [
            node
            for node in _walk(row.to_data())
            if node.get("kind") == "call" and node["call"]["function"] == str(code)
        ]
        assert len(call["call"]["arguments"]) == 2
        assert "named_arguments" not in call["call"]


def test_text_and_rx_give_the_same_rows():
    _, project, shapes = declared()
    names = Names(project)
    for source, term in zip(CASCADE, in_python(project), strict=True):
        text_rows = per_period(
            expression=read(text=source, names=names).to_expression(), flows=shapes
        )
        rx_rows = per_period(expression=term, flows=shapes)
        assert [strip(r.to_data()) for r in text_rows] == [
            strip(r.to_data()) for r in rx_rows
        ]


def test_the_cascade_written_with_rx_solves_period_by_period():
    draft, project, shapes = declared()
    rows = [
        row
        for term in in_python(project)
        for row in per_period(expression=term, flows=shapes)
    ]
    project.equations(*rows)
    model = draft.commit()
    assert len(Pieces.of(model).kinds) == 1
    movements = shapes[project.ref(key="net").id]
    specification = model.specify(name="Cascade").fix(
        equity=aud(EQUITY),
        net={
            movement: aud(amount)
            for movement, amount in zip(movements, NET, strict=True)
        },
    )
    outcome = solve(specification=specification)
    outcome.raise_for_status()
    need = [-total for total in accumulate(NET)]
    principal = [max(0.0, amount - EQUITY) for amount in need]
    draws = [principal[0]] + [b - a for a, b in itertools.pairwise(principal)]
    for key, expected in (("need", need), ("principal", principal), ("draws", draws)):
        flow = outcome[key]
        for movement, amount in zip(flow.movements, expected, strict=True):
            assert isclose(
                actual=aud(movement.number), expected=aud(amount), tolerance="1e-3 AUD"
            ), key


def test_a_scalar_max_written_with_rx_solves():
    draft = rk.Model(name="Scalar").edit()
    project = draft.add_entity(code="project", classification="project")
    need = project.value(key="need", units="AUD")
    equity = project.value(key="equity", units="AUD")
    principal = project.value(key="principal", units="AUD")
    project.equations(principal == rx.max("0 AUD", need - equity))
    model = draft.commit()
    for amount, expected in ((80e6, 30e6), (20e6, 0.0)):
        outcome = solve(
            specification=model.specify(name="Scalar").fix(
                need=aud(amount), equity=aud(EQUITY)
            )
        )
        outcome.raise_for_status()
        assert isclose(
            actual=outcome["principal"], expected=aud(expected), tolerance="1e-3 AUD"
        )


def _walk(data: object):
    if isinstance(data, dict):
        yield data
        for child in data.values():
            yield from _walk(child)
    elif isinstance(data, list):
        for child in data:
            yield from _walk(child)
