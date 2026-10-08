"""Read-only indexes connecting authored interpretation to supported graph Facts."""

import json
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from rangekeeper.workflow.references import references


def decision_records(model, claim_ids, *, claims=None):
    """Read reviewed decisions through UUID support links, without source I/O."""
    if claims is None:
        claims = (
            {c.id: c for c in model.provenance.claims or ()} if model.provenance else {}
        )
    pending, seen = list(claim_ids), set()
    while pending:
        identity = pending.pop()
        if identity in seen:
            continue
        seen.add(identity)
        claim = claims[identity]
        if claim.method and claim.method.code == "reviewed-decision":
            content = claim.content
            if (
                isinstance(content, Mapping)
                and content.get("encoding") == "rk.source-value/v1"
            ):
                value = content["value"]
                if value[0] == "str":
                    try:
                        record = json.loads(value[1])
                    except (ValueError, TypeError):
                        record = None
                    if isinstance(record, Mapping) and isinstance(
                        record.get("id"), str
                    ):
                        yield record
        pending.extend(c for c in claim.sources or () if isinstance(c, UUID))


def object_index(result):
    """Resolve canonical assertion targets to their inspectable Model owners."""
    owners = {}
    model = result.model
    for owner in (*model.find_entities(), *(model.system.relationships or ())):
        label = (
            getattr(owner, "code", None)
            or getattr(owner, "name", None)
            or str(owner.id)
        )
        owners[owner.id] = {
            "owner": str(owner.id),
            "label": label,
            "characteristic": "Object",
        }
        if owner.characteristics:
            for kind in ("values", "labels"):
                for characteristic in getattr(owner.characteristics, kind) or ():
                    owners[characteristic.id] = {
                        "owner": str(owner.id),
                        "label": label,
                        "characteristic": f"{kind}: {characteristic.key}",
                    }
    return owners


def usage(result, *, owners=None):
    """Separate declared use from actual Fact support; never infer targets from prose."""
    targets = defaultdict(dict)
    claims = (
        {c.id: c for c in result.model.provenance.claims or ()}
        if result.model.provenance
        else {}
    )
    owners = object_index(result) if owners is None else owners
    for fact in (
        (result.model.provenance.facts or ()) if result.model.provenance else ()
    ):
        if fact.target not in owners:
            continue
        for decision in decision_records(result.model, fact.claims, claims=claims):
            targets[decision["id"]][str(fact.target)] = owners[fact.target]
    declared = defaultdict(list)

    def visit(value, path):
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key == "decisions" and isinstance(child, (tuple, list)):
                    for identifier in child:
                        if isinstance(identifier, str):
                            declared[identifier].append(path)
                else:
                    visit(child, f"{path}.{key}")
        elif isinstance(value, (tuple, list)):
            for index, child in enumerate(value):
                identity = (
                    child.get("id", index) if isinstance(child, Mapping) else index
                )
                visit(child, f"{path}[{identity}]")

    snapshot = result.metadata.get("review_specification", {})
    for section in ("steps", "model", "checks"):
        visit(snapshot.get(section, {}), section)
    return {key: tuple(value.values()) for key, value in targets.items()}, dict(
        declared
    )


@dataclass(frozen=True, slots=True)
class Report:
    owners: Mapping
    targets: Mapping
    declared: Mapping
    checks: tuple[dict, ...]
    cell_references: Mapping


def prepare(result):
    """Prepare shared report indexes once per render/export operation."""
    owners = object_index(result)
    targets, declared = usage(result, owners=owners)
    claims = {
        id(claim): claim
        for evidence in result.evidence.values()
        for claim in evidence.claims.values()
    }
    claim_references = {uid: references((claim,)) for uid, claim in claims.items()}
    return Report(
        owners,
        targets,
        declared,
        tuple(c.to_mapping() for c in result.checks),
        {
            (name, key): claim_references[id(claim)]
            for name, evidence in result.evidence.items()
            for key, claim in evidence.claims.items()
        },
    )
