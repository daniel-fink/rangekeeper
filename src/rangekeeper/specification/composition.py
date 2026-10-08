"""Bounded additive composition checks; no persistence, scheduling, or solving.

Structurally validate every supplied document first. The caller supplies a typed
catalogue of Specification revisions; UUID shape does not establish document kind.
Derived views are internal check results, not revisions to serialize or publish.
"""

from copy import deepcopy
from types import MappingProxyType
from uuid import UUID
import math
from typing import TYPE_CHECKING
from collections.abc import Mapping
from rangekeeper.shared.references import SpecificationResolver
from rangekeeper.shared.units import UnitSystem, default_units
from rangekeeper.shared.diagnostics import ValidationReport
from rangekeeper.schema.records import Specification as SpecificationRecord
from rangekeeper.schema.validation import document_version
from rangekeeper.shared.errors import (
    IdentityConflictError,
    ReferenceTypeError,
    ValidationError,
    ContractError,
)
from rangekeeper.shared.validation import bounded
from rangekeeper.model.scope import reference_key
from dataclasses import dataclass
from rangekeeper.shared.validation import require, require_ownership, require_acyclic


if TYPE_CHECKING:
    from rangekeeper.specification.specification import Specification


REQUIREMENTS = (
    "assignments",
    "unknowns",
    "estimates",
    "formulations",
    "objectives",
    "settings",
    "policy",
)
FIELDS = {"metadata", "model", "includes", "cases", *REQUIREMENTS}


def validate_local_header(doc, schema_version):
    """Check one contribution's header without resolving external revisions."""
    require(set(doc) <= FIELDS, "reference must resolve to a Specification")
    metadata = doc["metadata"]
    ref = metadata["id"]
    require(
        metadata["schema_version"] == schema_version,
        "unsupported Specification schema version",
    )
    require(metadata.get("previous") != ref, "self predecessor")
    for field in ("includes", "cases"):
        refs = doc.get(field) or []
        require(len(refs) == len(set(refs)), f"duplicate {field} reference")
        require(ref not in refs, "Specification composition/case cycle")
    if doc.get("cases"):
        require(
            not doc.get("includes") and not any(doc.get(f) for f in REQUIREMENTS),
            "batch cannot supply or include investigation requirements",
        )


@dataclass(frozen=True, slots=True)
class Source:
    document_id: UUID
    path: str


@dataclass(frozen=True, init=False)
class Composition:
    """One immutable derived view with exact contributors and original locations."""

    __slots__ = ("requirements", "contributors", "sources")
    requirements: SpecificationRecord
    contributors: tuple["Specification", ...]
    sources: Mapping[tuple[str, ...], Source]

    def __init__(self):
        raise TypeError("construct a Composition with Specification.compose")

    @property
    def root_id(self) -> UUID:
        return self.requirements.metadata.id

    @property
    def model_id(self) -> UUID | None:
        return self.requirements.model

    @property
    def contributor_ids(self) -> tuple[UUID, ...]:
        return tuple(document.id for document in self.contributors)

    @property
    def effective(self):
        return self.requirements.to_data()

    def validate(
        self,
        *,
        resolver: SpecificationResolver,
        units: UnitSystem = default_units,
    ) -> ValidationReport:
        from rangekeeper.shared.units import default_units
        from rangekeeper.specification.validation import prepare

        return prepare(self, resolver=resolver, units=units or default_units).report


def validate_settings(settings):
    for value in settings.values():
        require(
            value is None or math.isfinite(value) and value > 0,
            "settings must be positive and finite",
        )
    if settings.get("relative_tolerance") is not None:
        require(
            settings["relative_tolerance"] < 1,
            "relative_tolerance must be less than one",
        )


def validate_roles(document):
    """Return local role sets after checking duplicates and disjoint ownership."""
    groups = {}
    for field in ("assignments", "unknowns", "estimates"):
        values = [
            reference_key(entry if field == "unknowns" else entry["target"])
            for entry in document.get(field) or ()
        ]
        require(
            len(values) == len(set(values)),
            "duplicate unknown" if field == "unknowns" else f"duplicate {field} target",
        )
        groups[field] = set(values)
    require(
        not groups["assignments"] & groups["unknowns"],
        "assigned and unknown roles overlap",
    )
    controls = [
        reference_key(ref) for ref in (document.get("policy") or {}).get("targets", ())
    ]
    groups["policy"] = set(controls)
    require(len(controls) == len(groups["policy"]), "duplicate policy-controlled role")
    require(
        not groups["policy"] & (groups["assignments"] | groups["unknowns"]),
        "policy-controlled roles overlap",
    )
    return groups


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
        validate_local_header(doc, schema_version)
        metadata = doc["metadata"]
        require(metadata["id"] == ref, "Specification catalogue identity mismatch")
        active.add(ref)
        for target in (doc.get("includes") or []) + (doc.get("cases") or []):
            visit(target)
        for target in doc.get("includes") or []:
            require(not catalogue[target].get("cases"), "cannot include a batch")
        active.remove(ref)
        reachable[ref] = doc

    visit(root_id)
    require_acyclic(
        {
            key: [d["metadata"]["previous"]] if d["metadata"].get("previous") else []
            for key, d in reachable.items()
        },
        "Specification revision history",
    )
    return reachable


def compose_specification(
    specification,
    specifications,
    schema_version,
    *,
    documents=None,
    catalogue=None,
):
    """Accumulate one investigation without overrides; permit incomplete views.

    Completeness and Model-dependent reference/role validation happen separately.
    A diamond includes each revision once. Independent repeated requirements are
    errors even when identical. Empty containers are neutral, including objectives.
    """
    if catalogue is None:
        catalogue = specification_catalogue(
            specification, specifications, schema_version
        )
    require(not specification.get("cases"), "batch is not one concrete investigation")
    included = set()

    def include(identity):
        if identity in included:
            return
        included.add(identity)
        for child in catalogue[identity].get("includes") or ():
            include(child)

    include(specification["metadata"]["id"])
    contributors = tuple(catalogue[key] for key in sorted(included))
    require_ownership(list(contributors))
    effective = {"metadata": deepcopy(specification["metadata"])}
    sources, model_ids = {}, set()

    def claim(key, source, path):
        require(
            key not in sources,
            f"multiple contributors for {'.'.join(key)}: {sources.get(key)} and {source}",
        )
        sources[key] = Source(UUID(source), path)

    for doc in contributors:
        validate_roles(doc)
        source = doc["metadata"]["id"]
        if doc.get("model") is not None:
            model_ids.add(doc["model"])
        for field in ("assignments", "unknowns", "estimates"):
            for position, entry in enumerate(doc.get(field) or []):
                target = reference_key(
                    entry if field == "unknowns" else entry["target"]
                )
                claim((field, str(target)), source, f"/{field}/{position}")
                effective.setdefault(field, []).append(deepcopy(entry))
        for name, value in (doc.get("settings") or {}).items():
            if value is not None:
                claim(("settings", name), source, f"/settings/{name}")
                effective.setdefault("settings", {})[name] = deepcopy(value)
        if doc.get("policy"):
            claim(("policy",), source, "/policy")
            effective["policy"] = deepcopy(doc["policy"])
        if doc.get("objectives"):
            claim(("objectives",), source, "/objectives")
            effective["objectives"] = deepcopy(doc["objectives"])
        for position, formulation in enumerate(doc.get("formulations") or []):
            claim(
                ("formulations", formulation["id"]), source, f"/formulations/{position}"
            )
            effective.setdefault("formulations", []).append(deepcopy(formulation))

    require(len(model_ids) <= 1, "conflicting input Model revisions")
    if model_ids:
        effective["model"] = next(iter(model_ids))
    validate_roles(effective)
    from rangekeeper.specification.specification import Specification

    snapshots = []
    for document in contributors:
        if documents is not None:
            snapshots.append(documents[UUID(document["metadata"]["id"])])
            continue
        try:
            snapshots.append(Specification.from_data(document))
        except ValidationError as error:
            issue = error.report.issues[0]
            raise ContractError(
                issue.message,
                code=issue.code,
                path=issue.path,
                document_id=issue.document_id,
            ) from error
        except (ValueError, TypeError) as error:
            raise ContractError(str(error)) from error
    result = object.__new__(Composition)
    object.__setattr__(result, "requirements", SpecificationRecord.from_data(effective))
    object.__setattr__(result, "contributors", tuple(snapshots))
    object.__setattr__(result, "sources", MappingProxyType(sources))
    return result


def batch_cases(specification, specifications, schema_version, *, catalogue=None):
    """Yield case paths, concrete leaf records, and enclosing Model assertions.

    This is a validation walk, not a scheduling algorithm. A leaf reached through
    different case paths occurs separately. No batch content is passed to a leaf.
    """
    if catalogue is None:
        catalogue = specification_catalogue(
            specification, specifications, schema_version
        )
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


def collect_specifications(
    root: "Specification",
    *,
    resolver: SpecificationResolver,
):
    """Resolve and export each reachable revision once, then check its graph."""
    from rangekeeper.specification.specification import Specification

    if not isinstance(root, Specification):
        raise TypeError("root must be a Specification")
    documents = {root.id: root}
    pending = [root]
    while pending:
        current = pending.pop()
        for identity in (
            *(current.record.includes or ()),
            *(current.record.cases or ()),
        ):
            if identity in documents:
                continue
            found = resolver.load_specification(identity)
            if not isinstance(found, Specification):
                raise ReferenceTypeError(
                    f"{identity} did not resolve to a Specification"
                )
            if found.id != identity:
                raise IdentityConflictError(
                    f"resolver returned {found.id} for {identity}"
                )
            documents[identity] = found
            pending.append(found)
    catalogue = {str(key): value.to_data() for key, value in documents.items()}
    bounded(
        [],
        lambda: specification_catalogue(
            catalogue[str(root.id)], catalogue, document_version("Specification")
        ),
        document=catalogue[str(root.id)],
    ).raise_if_invalid()
    return documents, catalogue


def compose(
    root: "Specification",
    *,
    resolver: SpecificationResolver,
    documents=None,
    catalogue=None,
) -> Composition:
    """Compose exact resolved snapshots without rebuilding a supplied catalogue."""
    if documents is None and catalogue is None:
        documents, catalogue = collect_specifications(root, resolver=resolver)
    elif documents is None or catalogue is None:
        raise TypeError("documents and catalogue must be supplied together")
    data = catalogue[str(root.id)]
    result = None

    def check():
        nonlocal result
        result = compose_specification(
            data,
            catalogue,
            document_version("Specification"),
            documents=documents,
            catalogue=catalogue,
        )

    bounded([], check, document=data).raise_if_invalid()
    assert result is not None
    return result
