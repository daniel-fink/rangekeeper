"""Owner-local Formulation declaration rules."""

from ..._validation import require_unique


def validate_formulation_names(formulations, *, path="/formulations") -> None:
    """Check names within each owner without resolving mathematical references.

    Root and nested sibling codes, Binding names, Value keys and Constraint codes
    have separate owning collections. This same rule serves complete Models and
    partial Specifications; distinct owners may reuse the same names.
    """
    formulations = tuple(formulations)
    require_unique(formulations, "code", "sibling Formulation code", path=path)
    for index, formulation in enumerate(formulations):
        current = f"{path}/{index}"
        for collection, field, label in (
            ("bindings", "name", "Binding name"),
            ("values", "key", "local Value key"),
            ("constraints", "code", "Constraint code"),
        ):
            require_unique(
                formulation.get(collection) or [],
                field,
                label,
                path=f"{current}/{collection}",
            )
        validate_formulation_names(
            formulation.get("formulations") or [], path=f"{current}/formulations"
        )
