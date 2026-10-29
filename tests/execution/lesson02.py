"""The Model and Specifications of walkthrough lesson 02, for execution tests.

The equations are Expression records until equation text lands. Each
Specification frees its derived values by name, as lesson 02 does by default.
"""

import rangekeeper as rk
from rangekeeper.io import MemoryStore
from rangekeeper.model.expression.authoring import (
    add,
    equal,
    literal,
    multiply,
    reference,
    subtract,
)
from rangekeeper.schema.records import Reference


def q(text: str) -> rk.Quantity:
    return rk.Quantity(text=text)


DATA = {
    "works_cost": q("60e6 AUD"),
    "operating_cost": q("1.5e6 AUD pa"),
    "hotel_area": q("8000 sqm"),
    "hotel_rent": q("450 AUD per sqm pa"),
    "hotel_vacancy": q("0.25 ratio"),
    "residential_area": q("12000 sqm"),
    "residential_rent": q("520 AUD per sqm pa"),
    "residential_vacancy": q("0.04 ratio"),
    "retail_area": q("3000 sqm"),
    "retail_rent": q("700 AUD per sqm pa"),
    "retail_vacancy": q("0.08 ratio"),
}
USES = ("hotel", "residential", "retail")
DERIVED = (
    "total_cost",
    "mortgage",
    "debt_service",
    "noi",
    "effective_income",
    "reference_income",
)
CONSTANT = q("8.6 % pa")


def build_model() -> rk.Model:
    """Return the lesson 02 Model: one project and its seven equations."""
    draft = rk.Model(name="Mixed-use feasibility").edit()
    project = draft.add_entity(code="project", classification="project")
    for key, units in (
        ("land_cost", "AUD"),
        ("works_cost", "AUD"),
        ("total_cost", "AUD"),
        ("leverage", "ratio"),
        ("mortgage", "AUD"),
        ("mortgage_constant", "% pa"),
        ("debt_service", "AUD pa"),
        ("coverage", "ratio"),
        ("noi", "AUD pa"),
        ("operating_cost", "AUD pa"),
        ("effective_income", "AUD pa"),
        ("rent_factor", "ratio"),
        ("reference_income", "AUD pa"),
    ):
        project.value(key=key, units=units)
    for use in USES:
        project.value(key=f"{use}_area", units="sqm")
        project.value(key=f"{use}_rent", units="AUD per sqm pa")
        project.value(key=f"{use}_vacancy", units="ratio")

    def r(key):
        return reference(Reference(target=project.ref(key=key).id))

    def income(use):
        return multiply(
            multiply(r(f"{use}_area"), r(f"{use}_rent")),
            subtract(literal(1, "dimensionless"), r(f"{use}_vacancy")),
        )

    project.equations(
        equal(r("total_cost"), add(r("land_cost"), r("works_cost"))),
        equal(r("mortgage"), multiply(r("leverage"), r("total_cost"))),
        equal(r("debt_service"), multiply(r("mortgage_constant"), r("mortgage"))),
        equal(r("noi"), multiply(r("coverage"), r("debt_service"))),
        equal(r("effective_income"), add(r("noi"), r("operating_cost"))),
        equal(r("effective_income"), multiply(r("rent_factor"), r("reference_income"))),
        equal(
            r("reference_income"),
            add(add(income("hotel"), income("residential")), income("retail")),
        ),
    )
    return draft.commit()


MODEL = build_model()


def front(model: rk.Model = MODEL) -> rk.Specification:
    """Return the front door: fix the land cost and find the rent factor."""
    return (
        model.specify(name="Front door")
        .fix(land_cost=q("20e6 AUD"), **DATA)
        .fix(leverage=q("65 %"), coverage=q("1.25 ratio"), mortgage_constant=CONSTANT)
        .free("rent_factor", *DERIVED)
    )


def back(model: rk.Model = MODEL) -> rk.Specification:
    """Return the back door: fix the rent factor and find the land cost."""
    return front(model).fix(rent_factor=q("1 ratio")).free("land_cost")


def store(*documents) -> MemoryStore:
    """Return a MemoryStore that holds the lesson Model and ``documents``."""
    found = MemoryStore()
    found.put(MODEL)
    for document in documents:
        found.put(document)
    return found
