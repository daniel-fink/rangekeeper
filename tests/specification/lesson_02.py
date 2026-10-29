"""Lesson 02's Model, with its equations as Expression records.

Equation text is not supported yet (#145), so the equations of cell 5 are
written with ``rangekeeper.model.expression.authoring``. The solve does not yet
evaluate a product of fixed values before the affine stage (G09), so the
reference income of cell 6b is a fixed total here.
"""

import rangekeeper as rk
from rangekeeper.model.expression.authoring import (
    add,
    equal,
    multiply,
    reference,
)
from rangekeeper.schema.records import Reference

UNITS = {
    "land_cost": "AUD",
    "works_cost": "AUD",
    "total_cost": "AUD",
    "leverage": "ratio",
    "mortgage": "AUD",
    "mortgage_constant": "% pa",
    "debt_service": "AUD pa",
    "coverage": "ratio",
    "noi": "AUD pa",
    "operating_cost": "AUD pa",
    "effective_income": "AUD pa",
    "rent_factor": "ratio",
    "reference_income": "AUD pa",
}

# The data package's totals, with one reference income.
DATA = {
    "works_cost": rk.Quantity(text="30e6 AUD"),
    "operating_cost": rk.Quantity(text="1e6 AUD pa"),
    "reference_income": rk.Quantity(text="9e6 AUD pa"),
}


def lesson_02_model() -> rk.Model:
    """Return the Model of lesson 02, cells 4 to 5."""
    model = rk.Model(name="Mixed-use feasibility")
    draft = model.edit()
    project = draft.add_entity(code="project", classification="project")
    handles = {key: project.value(key=key, units=units) for key, units in UNITS.items()}

    def ref(key):
        return reference(Reference(target=handles[key].id))

    project.equations(
        equal(ref("total_cost"), add(ref("land_cost"), ref("works_cost"))),
        equal(ref("mortgage"), multiply(ref("leverage"), ref("total_cost"))),
        equal(ref("debt_service"), multiply(ref("mortgage_constant"), ref("mortgage"))),
        equal(ref("noi"), multiply(ref("coverage"), ref("debt_service"))),
        equal(ref("effective_income"), add(ref("noi"), ref("operating_cost"))),
        equal(
            ref("effective_income"),
            multiply(ref("rent_factor"), ref("reference_income")),
        ),
    )
    return draft.commit()
