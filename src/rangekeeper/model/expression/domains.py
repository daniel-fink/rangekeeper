"""Local expression domain rules; no traversal, graph execution or evaluation."""

from ..scope import Scope
from ..._validation import require
from enum import Enum
from uuid import UUID
from typing import cast


class DomainCompatibility(Enum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNPROVEN = "unproven"


def get_numerical_units(domain, *, scope: Scope) -> str | None:
    """Return the declared units of a coarse numerical domain, if known."""
    if domain["kind"] == "number":
        return "dimensionless"
    if domain["kind"] == "quantity":
        return domain.get("units")
    if domain["kind"] == "measurement":
        return (
            scope.measures.get(UUID(domain["measure"]), {}).get("units")
            if domain.get("measure")
            else None
        )
    return None


def compare_domains(actual, expected, *, scope: Scope) -> DomainCompatibility:
    """Compare directional requirements and retain incomplete static knowledge."""
    compatible = DomainCompatibility.COMPATIBLE
    incompatible = DomainCompatibility.INCOMPATIBLE
    unproven = DomainCompatibility.UNPROVEN
    if actual.get("kind") == "unknown":
        return unproven
    if expected["kind"] in ("number", "quantity"):
        if actual["kind"] not in ("number", "quantity", "measurement"):
            return incompatible
        required = (
            "dimensionless" if expected["kind"] == "number" else expected.get("units")
        )
        if required is None:
            return compatible
        units = get_numerical_units(actual, scope=scope)
        return (
            unproven
            if units is None
            else compatible if units == required else incompatible
        )
    if actual["kind"] != expected["kind"]:
        return incompatible
    if "measure" in expected:
        if "measure" not in actual:
            return unproven
        if actual["measure"] != expected["measure"]:
            return incompatible
    if expected["kind"] == "collection":
        if (
            "collection_kind" in expected
            and actual.get("collection_kind") != expected["collection_kind"]
        ):
            return incompatible
        return compare_domains(
            actual["item_domain"], expected["item_domain"], scope=scope
        )
    return compatible


def infer_operator_domain(operator, domains, *, unary, scope):
    """Infer a local operator result from already analyzed operand domains."""
    if operator in ("logical_not", "logical_and", "logical_or"):
        require(
            all(t["kind"] == "boolean" for t in domains),
            "Boolean operands required",
        )
        return dict(kind="boolean")
    if operator in ("equal", "not_equal") and all(
        t["kind"] == "boolean" for t in domains
    ):
        return dict(kind="boolean")
    require(
        all(t["kind"] in ("number", "quantity", "measurement") for t in domains),
        "numerical operands required",
    )
    if operator in (
        "equal",
        "not_equal",
        "less_than",
        "less_than_or_equal",
        "greater_than",
        "greater_than_or_equal",
    ):
        return dict(kind="boolean")
    if all(get_numerical_units(t, scope=scope) == "dimensionless" for t in domains):
        return dict(kind="number")
    if unary and get_numerical_units(domains[0], scope=scope) is not None:
        return dict(kind="quantity", units=get_numerical_units(domains[0], scope=scope))
    # Full unit inference is deferred. Arithmetic alone does not supply
    # a Measurement's domain meaning or a Measure identity.
    return dict(kind="quantity")


def infer_selection_domain(base, *, scope, member=None, index=None, literal=None):
    """Check a member or index against already analyzed child domains."""
    if member is not None:
        members = {
            "span": {"start_date": dict(kind="date"), "end_date": dict(kind="date")},
            "account": {"transactions": dict(kind="flow")},
        }
        result = members.get(base["kind"], {}).get(member)
        require(result is not None, "unknown or unsupported member")
        return cast(dict, result)
    require(
        base["kind"] == "collection" and base.get("collection_kind") == "sequence",
        "this index fixture requires an ordered sequence",
    )
    require(
        compare_domains(index, dict(kind="number"), scope=scope)
        is DomainCompatibility.COMPATIBLE,
        "numerical index required",
    )
    if literal is not None:
        require(
            literal >= 0 and int(literal) == literal,
            "nonnegative integer sequence index required",
        )
    return base["item_domain"]
