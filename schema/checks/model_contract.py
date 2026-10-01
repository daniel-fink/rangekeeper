"""Bounded Model reference/ownership checks; not a runtime or full unit validator.

Run generated structural validation first. Generic Claim content remains opaque;
these checks validate evidence references, not arbitrary Fact/content agreement.
"""

from formulation_contract import check_ownership, unique_names, validate_formulations
from expression_contract import require


def acyclic(edges, label):
    visiting, complete = set(), set()

    def visit(node):
        require(node not in visiting, f"{label} cycle")
        if node in complete:
            return
        visiting.add(node)
        for target in edges.get(node, []):
            visit(target)
        visiting.remove(node)
        complete.add(node)

    for node in edges:
        visit(node)


def model_documents(model):
    """Adapt the canonical Model into bounded mathematical and identity scopes."""
    metadata = model["metadata"]
    definitions = model.get("definitions") or {}
    system = model.get("system") or {}
    provenance = model.get("provenance") or {}
    # Adapt into the existing bounded mathematical scope; no duplicate Function
    # catalogue is introduced into the serialized Model.
    scope_document = dict(
        definitions={k: v for k, v in definitions.items() if k != "functions"},
        functions=definitions.get("functions") or [],
        entities=system.get("entities") or [],
        relationships=system.get("relationships") or [],
        assemblies=system.get("assemblies") or [],
        formulations=system.get("formulations") or [],
    )
    # Content can legitimately contain keys named id; it is not a declaration.
    identity_document = dict(
        scope_document,
        metadata=metadata,
        provenance=dict(
            sources=provenance.get("sources") or [],
            claims=[
                {k: v for k, v in c.items() if k != "content"}
                for c in provenance.get("claims") or []
            ],
        ),
    )
    return scope_document, identity_document


def validate_model(model, schema_version, history=()):
    """Check a complete current Model; prior Metadata records are optional context.

    Missing historical records are permitted. Internal domain and mathematical
    references must resolve without importing content from a previous revision.
    """
    metadata = model["metadata"]
    require(metadata["schema_version"] == schema_version, "unsupported schema version")
    definitions = model.get("definitions") or {}
    system = model.get("system") or {}
    provenance = model.get("provenance") or {}
    scope_document, identity_document = model_documents(model)
    check_ownership(identity_document)
    scope = validate_formulations(scope_document)

    for collection in ("taxonomies", "measures", "functions"):
        unique_names(definitions.get(collection) or [], "code", f"{collection} code")
    for taxonomy in definitions.get("taxonomies") or []:
        records = taxonomy["classifications"]
        require(bool(records), "empty Taxonomy")
        unique_names(records, "code", "Classification code")
        local = {r["id"] for r in records}
        parents = {}
        roots = []
        for record in records:
            parent = record.get("parent")
            if parent is None:
                roots.append(record)
            else:
                require(parent in local, "Classification parent outside Taxonomy")
                parents[record["id"]] = [parent]
        acyclic(parents, "Classification parent")
        require(len(roots) == 1, "Taxonomy must have one root")

    entities = scope.entities
    relationships = {r["id"]: r for r in system.get("relationships") or []}
    assemblies = {r["id"]: r for r in system.get("assemblies") or []}
    unique_names(entities.values(), "code", "Entity/Assembly code")
    targets = dict(entities, **relationships, **scope.values)
    for obj in list(entities.values()) + list(relationships.values()):
        if obj.get("classification") is not None:
            require(
                obj["classification"] in scope.classifications, "unknown Classification"
            )
        for label in (obj.get("characteristics") or {}).get("labels") or []:
            targets[label["id"]] = label
            refs = label.get("classifications") or []
            require(len(refs) == len(set(refs)), "duplicate Label Classification")
            require(
                all(r in scope.classifications for r in refs),
                "unknown Label Classification",
            )
    for relationship in relationships.values():
        require(
            relationship["source"] in entities and relationship["target"] in entities,
            "unknown or non-Entity Relationship endpoint",
        )
    for assembly in assemblies.values():
        members = assembly.get("entities") or []
        links = assembly.get("relationships") or []
        require(
            len(members) == len(set(members)) and len(links) == len(set(links)),
            "duplicate Assembly membership",
        )
        require(all(m in entities for m in members), "unknown Assembly Entity")
        require(all(r in relationships for r in links), "unknown Assembly Relationship")
        endpoints = set(members) | {assembly["id"]}
        for link in links:
            relation = relationships[link]
            require(
                relation["source"] in endpoints and relation["target"] in endpoints,
                "Assembly Relationship endpoint outside membership",
            )
    acyclic(
        {
            a["id"]: [i for i in a.get("entities") or [] if i in assemblies]
            for a in assemblies.values()
        },
        "Assembly membership",
    )

    sources = {r["id"]: r for r in provenance.get("sources") or []}
    claims = {r["id"]: r for r in provenance.get("claims") or []}
    parents = {}
    for claim in claims.values():
        support = claim.get("sources") or []
        locations = [s for s in support if isinstance(s, dict)]
        upstream = [s for s in support if isinstance(s, str)]
        require(all(s["source"] in sources for s in locations), "unknown Source")
        require(all(c in claims for c in upstream), "unknown upstream Claim")
        if claim["kind"] == "sourced":
            require(bool(locations), "sourced Claim needs a Location")
        if claim["kind"] == "derived":
            require(bool(upstream), "derived Claim needs an upstream Claim")
        parents[claim["id"]] = upstream
    acyclic(parents, "Claim dependency")
    fact_targets = set()
    for fact in provenance.get("facts") or []:
        target = fact["target"]
        require(target in targets, "unknown or ineligible Fact target")
        require(target not in fact_targets, "duplicate Fact target")
        fact_targets.add(target)
        support = fact["claims"]
        require(bool(support), "Fact needs a Claim")
        require(len(support) == len(set(support)), "duplicate Fact Claim")
        require(all(c in claims for c in support), "unknown supporting Claim")
        reconciliation = fact.get("reconciliation")
        if reconciliation:
            require(
                reconciliation["selected"] in support, "selected Claim outside Fact"
            )

    # Previous is an external revision handle, never an internal domain reference.
    internal_ids = set()

    def ids(node):
        if isinstance(node, dict):
            if "id" in node:
                internal_ids.add(node["id"])
            for child in node.values():
                ids(child)
        elif isinstance(node, list):
            for child in node:
                ids(child)

    ids(identity_document)
    previous = metadata.get("previous")
    require(previous != metadata["id"], "self predecessor")
    require(previous not in internal_ids, "previous targets current snapshot content")
    revisions = {metadata["id"]: metadata}
    for record in history:
        require(record["id"] not in revisions, "duplicate history identity")
        revisions[record["id"]] = record
    acyclic(
        {
            key: [r["previous"]] if r.get("previous") else []
            for key, r in revisions.items()
        },
        "revision history",
    )
    return scope
