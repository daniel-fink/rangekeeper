"""Ordered Formulation locations; input iterables are consumed once."""


def walk_formulations(formulations, path):
    """Yield root and nested Formulations in document order."""
    for index, formulation in enumerate(formulations):
        current = f"{path}/{index}"
        yield formulation, current
        yield from walk_formulations(
            formulation.get("formulations") or [], current + "/formulations"
        )
