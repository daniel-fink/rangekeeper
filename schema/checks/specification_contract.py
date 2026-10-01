"""Bounded Specification conformance checks; no evaluation, graph executor, or solver.

Run generated structural validation on both documents first. Assignment checks
accept exact canonical unit spellings, or an explicit unit-compatibility adapter.
Other spellings are reported as unsupported without such an adapter. This is not
expression unit inference or a shared unit registry. Query dependencies in imposed
mathematics require a graph adapter and are reported explicitly as unsupported.
"""

import math

from expression_contract import require
from formulation_contract import check_ownership, validate_formulations
from model_contract import acyclic, model_documents, validate_model
from specification_composition import (
    batch_cases,
    compose_specification,
    specification_catalogue,
)


def records(node):
    if isinstance(node, dict):
        yield node
        for child in node.values():
            yield from records(child)
    elif isinstance(node, (list, tuple)):
        for child in node:
            yield from records(child)


def validate_specification(
    specification,
    model,
    schema_version,
    model_schema_version,
    *,
    history=(),
    units_compatible=None,
    specifications=None,
):
    """Validate one concrete composition and roles without changing its inputs.

    The caller supplies structurally validated Model/Specification documents and
    an optional UUID-keyed Specification catalogue. Historical Metadata, if
    supplied, must come from Specification revisions. External resolution is absent.
    """
    composition = compose_specification(specification, specifications, schema_version)
    effective = composition.effective
    require("model" in effective, "concrete Specification requires an input Model")
    _, identities = model_documents(model)
    check_ownership(dict(model=identities, specifications=list(composition.contributors)))
    # Contributor lineage is distinct from include edges. A predecessor may be
    # explicitly included, but cannot masquerade as a Model/domain declaration.
    domain_ids = {r["id"] for r in records(identities) if "id" in r}
    domain_ids.update(
        r["id"]
        for d in composition.contributors
        for r in records(d.get("formulations") or [])
        if "id" in r
    )
    for contributor in composition.contributors:
        require(
            contributor["metadata"].get("previous") not in domain_ids,
            "Specification predecessor targets current scope",
        )
    return _validate_concrete(
        effective,
        model,
        schema_version,
        model_schema_version,
        history=history,
        units_compatible=units_compatible,
    )


def validate_batch(
    specification,
    models,
    schema_version,
    model_schema_version,
    *,
    specifications=None,
    units_compatible=None,
):
    """Validate every leaf independently; return case paths, not runs or results."""
    catalogue = specification_catalogue(specification, specifications, schema_version)
    paths = []
    for path, leaf, assertions in batch_cases(specification, catalogue, schema_version):
        effective = compose_specification(leaf, catalogue, schema_version).effective
        require("model" in effective, "concrete Specification requires an input Model")
        model_id = effective["model"]
        require(
            all(ref == model_id for ref in assertions),
            "batch input Model assertion mismatch",
        )
        require(model_id in models, "unresolved input Model revision")
        _, identities = model_documents(models[model_id])
        # Batch revision identities also must not alias a Model/declaration UUID.
        # Sibling mathematical scopes stay separate; do not combine their Values.
        check_ownership(dict(
            metadata=[d["metadata"] for d in catalogue.values()],
            model=identities,
            formulations=effective.get("formulations") or [],
        ))
        validate_specification(
            leaf,
            models[model_id],
            schema_version,
            model_schema_version,
            specifications=catalogue,
            units_compatible=units_compatible,
        )
        paths.append(path)
    return paths


def _validate_concrete(
    specification,
    model,
    schema_version,
    model_schema_version,
    *,
    history=(),
    units_compatible=None,
):
    require("model" not in model, "input document must be a Model, not a Specification")
    validate_model(model, model_schema_version)
    metadata = specification["metadata"]
    require(
        metadata["schema_version"] == schema_version,
        "unsupported Specification schema version",
    )
    require(
        specification["model"] == model["metadata"]["id"],
        "input Model revision mismatch",
    )
    document, identities = model_documents(model)
    combined = dict(model=identities, specification=specification)
    check_ownership(combined)
    internal_ids = {r["id"] for r in records(combined) if "id" in r}
    previous = metadata.get("previous")
    require(previous != metadata["id"], "self predecessor")
    require(
        previous not in internal_ids, "Specification predecessor targets current scope"
    )
    revisions = {metadata["id"]: metadata}
    for record in history:
        require(record["id"] not in internal_ids, "history identity in current scope")
        require(record["id"] not in revisions, "duplicate history identity")
        revisions[record["id"]] = record
    acyclic(
        {
            key: [r["previous"]] if r.get("previous") else []
            for key, r in revisions.items()
        },
        "Specification revision history",
    )

    additions = specification.get("formulations") or []
    scope = validate_formulations(document, additional_formulations=additions)

    def eligible(target):
        require(target in scope.values, "unknown or non-Value role target")
        require(
            scope.values[target]["kind"] == "measurement", "unsupported role Value kind"
        )

    def supplied(collection):
        targets = set()
        for assignment in specification.get(collection) or []:
            target = assignment["value"]
            require(target not in targets, f"duplicate {collection} target")
            targets.add(target)
            eligible(target)
            quantity = assignment["quantity"]
            require(
                math.isfinite(quantity["magnitude"]), "non-finite supplied magnitude"
            )
            expected = scope.measures[scope.values[target]["measure"]]["units"]
            actual = quantity["units"]
            if actual != expected:
                require(
                    units_compatible is not None,
                    "unit compatibility requires a unit-aware adapter",
                )
            if units_compatible is not None:
                require(
                    units_compatible(actual, expected), "incompatible supplied units"
                )
        return targets

    assigned = supplied("assignments")
    unknowns = specification.get("unknowns") or []
    require(len(unknowns) == len(set(unknowns)), "duplicate unknown")
    unknowns = set(unknowns)
    for target in unknowns:
        eligible(target)
    require(not assigned & unknowns, "assigned and unknown roles overlap")
    estimates = supplied("estimates")
    require(estimates <= unknowns, "estimate target is not an unknown")

    # Imposed predicates and every objective need role completeness. Unused
    # expressions (including reporting queries) need not be prepared for a solve.
    roots, constraints = [], []

    def collect(formulations):
        for formulation in formulations:
            roots.extend(formulation.get("expressions") or [])
            constraints.extend(formulation.get("constraints") or [])
            collect(formulation.get("formulations") or [])

    collect(document["formulations"])
    collect(additions)
    by_id = {r["id"]: r for root in roots for r in records(root) if "id" in r}
    imposed = [by_id[c["predicate"]] for c in constraints]
    # Validate all criteria without ranking, selecting, or reordering candidates.
    for objective in specification.get("objectives") or []:
        ref = objective["expression"]
        require(ref in by_id, "unknown or non-Expression objective")
        require(
            scope.expression(by_id[ref])["kind"]
            in ("number", "quantity", "measurement"),
            "objective must be scalar numerical",
        )
        imposed.append(by_id[ref])
    required = set()
    for expression in imposed:
        for node in records(expression):
            require(
                node.get("kind") != "query",
                "query dependency resolution requires a graph adapter",
            )
            if node.get("kind") == "reference":
                required.add(node["target"])
    require(required <= assigned | unknowns, "missing solve role for required Value")

    settings = specification.get("settings") or {}
    for name in ("relative_tolerance", "time_limit", "iteration_limit"):
        if name in settings and settings[name] is not None:
            value = settings[name]
            require(
                math.isfinite(value) and value > 0,
                "settings must be positive and finite",
            )
    if settings.get("relative_tolerance") is not None:
        require(
            settings["relative_tolerance"] < 1,
            "relative_tolerance must be less than one",
        )
    return scope
