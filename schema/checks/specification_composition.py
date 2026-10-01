"""Bounded additive composition checks; no persistence, scheduling, or solving.

Structurally validate every supplied document first. The caller supplies a typed
catalogue of Specification revisions; UUID shape does not establish document kind.
Derived views are internal check results, not revisions to serialize or publish.
"""

from copy import deepcopy
from dataclasses import dataclass

from expression_contract import require
from formulation_contract import check_ownership
from model_contract import acyclic


REQUIREMENTS = (
    "assignments",
    "unknowns",
    "estimates",
    "formulations",
    "objectives",
    "settings",
)
FIELDS = {"metadata", "model", "includes", "cases", *REQUIREMENTS}


@dataclass
class Composition:
    """An effective check view and its exact contributors and requirement sources."""

    effective: dict
    contributors: tuple
    sources: dict


def specification_catalogue(root, specifications, schema_version):
    """Resolve reachable includes/cases and check their shared revision graph."""
    catalogue = dict(specifications or {})
    root_id = root["metadata"]["id"]
    require(
        root_id not in catalogue or catalogue[root_id] == root,
        "different content for one Specification revision",
    )
    catalogue[root_id] = root
    reachable, active = {}, set()

    def visit(ref):
        require(ref not in active, "Specification composition/case cycle")
        if ref in reachable:
            return
        require(ref in catalogue, f"unresolved Specification reference: {ref}")
        doc = catalogue[ref]
        require(set(doc) <= FIELDS, "reference must resolve to a Specification")
        metadata = doc["metadata"]
        require(metadata["id"] == ref, "Specification catalogue identity mismatch")
        require(
            metadata["schema_version"] == schema_version,
            "unsupported Specification schema version",
        )
        require(metadata.get("previous") != ref, "self predecessor")
        for field in ("includes", "cases"):
            refs = doc.get(field) or []
            require(len(refs) == len(set(refs)), f"duplicate {field} reference")
        if doc.get("cases"):
            require(
                not doc.get("includes") and not any(doc.get(f) for f in REQUIREMENTS),
                "batch cannot supply or include investigation requirements",
            )
        active.add(ref)
        for target in (doc.get("includes") or []) + (doc.get("cases") or []):
            visit(target)
        for target in doc.get("includes") or []:
            require(not catalogue[target].get("cases"), "cannot include a batch")
        active.remove(ref)
        reachable[ref] = doc

    visit(root_id)
    acyclic(
        {
            key: [d["metadata"]["previous"]] if d["metadata"].get("previous") else []
            for key, d in reachable.items()
        },
        "Specification revision history",
    )
    return reachable


def compose_specification(specification, specifications, schema_version):
    """Accumulate one investigation without overrides; permit incomplete views.

    Completeness and Model-dependent reference/role validation happen separately.
    A diamond includes each revision once. Independent repeated requirements are
    errors even when identical. Empty containers are neutral, including objectives.
    """
    catalogue = specification_catalogue(specification, specifications, schema_version)
    require(not specification.get("cases"), "batch is not one concrete investigation")
    contributors = tuple(catalogue[key] for key in sorted(catalogue))
    check_ownership(list(contributors))
    effective = {"metadata": deepcopy(specification["metadata"])}
    sources, model_ids, assigned, unknowns = {}, set(), set(), set()

    def claim(key, source):
        require(
            key not in sources,
            f"multiple contributors for {'.'.join(key)}: {sources.get(key)} and {source}",
        )
        sources[key] = source

    for doc in contributors:
        source = doc["metadata"]["id"]
        if doc.get("model") is not None:
            model_ids.add(doc["model"])
        for field in ("assignments", "unknowns", "estimates"):
            local = set()
            for entry in doc.get(field) or []:
                target = entry if field == "unknowns" else entry["value"]
                require(
                    target not in local,
                    "duplicate unknown"
                    if field == "unknowns"
                    else f"duplicate {field} target",
                )
                local.add(target)
                claim((field, target), source)
                effective.setdefault(field, []).append(deepcopy(entry))
            if field == "assignments":
                assigned.update(local)
            elif field == "unknowns":
                unknowns.update(local)
        for name, value in (doc.get("settings") or {}).items():
            if value is not None:
                claim(("settings", name), source)
                effective.setdefault("settings", {})[name] = deepcopy(value)
        if doc.get("objectives"):
            claim(("objectives",), source)
            effective["objectives"] = deepcopy(doc["objectives"])
        for formulation in doc.get("formulations") or []:
            claim(("formulations", formulation["id"]), source)
            effective.setdefault("formulations", []).append(deepcopy(formulation))

    require(len(model_ids) <= 1, "conflicting input Model revisions")
    if model_ids:
        effective["model"] = next(iter(model_ids))
    require(not assigned & unknowns, "assigned and unknown roles overlap")
    return Composition(effective, contributors, sources)


def batch_cases(specification, specifications, schema_version):
    """Yield case paths, concrete leaf records, and enclosing Model assertions.

    This is a validation walk, not a scheduling algorithm. A leaf reached through
    different case paths occurs separately. No batch content is passed to a leaf.
    """
    catalogue = specification_catalogue(specification, specifications, schema_version)
    require(bool(specification.get("cases")), "Specification is not a batch")

    def walk(doc, path, models):
        if doc.get("cases"):
            if doc.get("model") is not None:
                models = models + (doc["model"],)
            for ref in sorted(doc["cases"]):
                yield from walk(catalogue[ref], path + (ref,), models)
        else:
            yield path, doc, models

    yield from walk(specification, (specification["metadata"]["id"],), ())
