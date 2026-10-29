"""Lesson 02's Model, with the equations of cell 5 as equation text.

The solve does not yet evaluate a product of fixed values before the affine
stage (G09), so the reference income of cell 6b is a fixed total here.
"""

from uuid import UUID

import rangekeeper as rk

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


def lesson_02_model(
    *,
    name: str = "Mixed-use feasibility",
    namespace: UUID | None = None,
    operating_cost: bool = True,
) -> rk.Model:
    """Return the Model of lesson 02, cells 4 to 5.

    Models with one ``namespace`` give their Values the same UUIDs. Without
    ``operating_cost``, the Model has no operating cost: ``effective_income = noi``.
    """
    model = rk.Model(name=name, namespace=namespace)
    draft = model.edit()
    project = draft.add_entity(code="project", classification="project")
    for key, units in UNITS.items():
        if operating_cost or key != "operating_cost":
            project.value(key=key, units=units)
    project.equations(
        "total_cost = land_cost + works_cost",
        "mortgage = leverage * total_cost",
        "debt_service = mortgage_constant * mortgage",
        "noi = coverage * debt_service",
        "effective_income = noi + operating_cost"
        if operating_cost
        else "effective_income = noi",
        "effective_income = rent_factor * reference_income",
    )
    return draft.commit()
