"""A saved investigation contribution, distinct from its derived composition."""

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rangekeeper.model import Model
    from rangekeeper.schema.records import Reference, Quantity
from dataclasses import dataclass
import math
from uuid import UUID

from rangekeeper.schema.revision import check_revision
from rangekeeper.schema.records import Specification as SpecificationRecord, Metadata
from rangekeeper.schema.validation import document_version
from rangekeeper.shared.validation import (
    bounded,
    require,
    validate_known_reference_types,
)
from rangekeeper.shared.errors import UnsupportedVersionError
from rangekeeper.schema.index import RecordIndex
from rangekeeper.model.formulation.validation import validate_formulation_names
from rangekeeper.specification.composition import (
    Composition,
    validate_local_header,
    validate_settings,
    validate_roles,
)
from rangekeeper.shared.references import SpecificationResolver


def _validate_local(record: SpecificationRecord) -> None:
    """Check local ownership and roles while permitting unresolved external inputs."""
    data = record.to_data()
    index = RecordIndex.build(record)
    version = document_version("Specification")
    if record.metadata.schema_version != version:
        raise UnsupportedVersionError(record.metadata.schema_version)

    def check():
        validate_local_header(data, version)
        validate_known_reference_types(record, index=index)
        require(
            record.metadata.previous not in index.records,
            "Specification predecessor targets current scope",
        )
        validate_roles(data)
        for field in ("includes", "cases"):
            require(
                all(
                    identity not in index.records
                    for identity in (getattr(record, field) or ())
                ),
                f"{field} reference targets a local declaration",
            )
        if record.model is not None:
            require(
                record.model not in index.records,
                "Model pin targets a local declaration",
            )
        validate_settings(data.get("settings") or {})

        validate_formulation_names(data.get("formulations") or [])

    bounded([], check, document=data).raise_if_invalid()


@dataclass(frozen=True, init=False, eq=False)
class Specification:
    """Immutable locally valid contribution, including partial contributions/batches.

    External resolution and complete solve roles belong to composition validation.
    The ``record`` property exposes all generated fields with their original types;
    this facade does not redeclare the authoritative field schema.
    """

    __slots__ = ("_record",)
    _record: SpecificationRecord

    def __init__(self, record: SpecificationRecord) -> None:
        if not isinstance(record, SpecificationRecord):
            raise TypeError("record must be a generated Specification record")
        _validate_local(record)
        object.__setattr__(self, "_record", record)

    @classmethod
    def from_data(cls, data: Mapping[str, object]) -> "Specification":
        """Copy and validate local structure/ownership; perform no external lookup."""
        return cls(SpecificationRecord.from_data(data))

    @property
    def id(self) -> UUID:
        """Saved revision identity, forwarded from Metadata."""
        return self.metadata.id

    @property
    def metadata(self) -> Metadata:
        """Immutable revision identity, version, lineage and descriptive content."""
        return self._record.metadata

    @property
    def record(self) -> SpecificationRecord:
        """Read-only typed access to assignments, roles, include/case edges and settings."""
        return self._record

    def to_data(self) -> dict[str, object]:
        """Export detached saved content, retaining include/case boundaries and presence."""
        return self._record.to_data()

    def __repr__(self) -> str:
        return f"Specification(id={self.id!r}, includes={len(self.record.includes or ())}, cases={len(self.record.cases or ())})"

    def compose(self, *, resolver: SpecificationResolver) -> Composition:
        """Resolve this contribution to one immutable additive investigation."""
        from rangekeeper.specification.composition import compose

        return compose(self, resolver=resolver)

    def revise(self, replacement: SpecificationRecord) -> "Specification":
        """Accept a complete locally valid replacement with explicit new identity/lineage.

        No include is resolved and no missing requirement is inherited implicitly.
        Metadata-only identity changes and schema-version migrations are rejected.
        """
        if not isinstance(replacement, SpecificationRecord):
            raise TypeError("replacement must be a generated Specification record")
        check_revision(self._record, replacement)
        return type(self)(replacement)

    def lock(
        self,
        target: "UUID | Reference",
        quantity: "Quantity | Mapping[UUID, Quantity] | None" = None,
        *,
        id: UUID,
        model: "Model",
        ids: "Sequence[UUID] | None" = None,
        recorded: bool = False,
        resolver: SpecificationResolver | None = None,
    ) -> "Specification":
        """Return a revision with explicit assignments and matching local roles removed.

        A scalar Quantity applies to each selected Movement in its stated units.
        A mapping supplies one Quantity per selected Movement. recorded=True copies
        recorded amounts explicitly; it cannot be combined with quantity.
        Included roles and policy controls must be revised at their owner.
        """
        from rangekeeper.schema.records import Assignment, Quantity
        from rangekeeper.specification.targets import expand_targets
        from rangekeeper.model.scope import recorded_scalar, target_units
        from rangekeeper.shared.units import default_units

        if type(recorded) is not bool:
            raise TypeError("recorded must be bool")
        if recorded == (quantity is not None):
            raise ValueError("supply quantity or explicitly request recorded=True")
        refs = expand_targets(model, target, ids=ids)
        if isinstance(quantity, Mapping) and set(quantity) != {
            ref.target for ref in refs
        }:
            raise ValueError("quantity mapping must cover the selected targets exactly")
        assignments = []
        for ref in refs:
            q = (
                recorded_scalar(model, ref)
                if recorded
                else quantity[ref.target] if isinstance(quantity, Mapping) else quantity
            )
            if q is None:
                raise ValueError("cannot lock an unresolved recorded amount")
            if not isinstance(q, Quantity):
                raise TypeError(
                    "quantity must be a Quantity or target-to-Quantity mapping"
                )
            default_units.convert(q, to=target_units(model, ref))
            assignments.append(Assignment(target=ref, quantity=q))
        return self._edit_roles(
            id=id,
            model=model,
            refs=refs,
            assignments=tuple(assignments),
            resolver=resolver,
        )

    def unlock(
        self,
        target: "UUID | Reference",
        *,
        id: UUID,
        model: "Model",
        ids: "Sequence[UUID] | None" = None,
        resolver: SpecificationResolver | None = None,
    ) -> "Specification":
        """Return a revision that removes local assignments and declares selected unknowns."""
        from rangekeeper.specification.targets import expand_targets

        refs = expand_targets(model, target, ids=ids)
        return self._edit_roles(
            id=id, model=model, refs=refs, assignments=None, resolver=resolver
        )

    def _edit_roles(self, *, id, model, refs, assignments, resolver):
        if self.record.cases:
            raise ValueError("edit a concrete investigation, not a batch")
        if self.record.includes and resolver is None:
            raise ValueError(
                "included Specifications require a resolver for role editing"
            )
        composition = self.compose(resolver=resolver)
        if composition.model_id != model.id:
            raise ValueError("role editing requires the exact pinned Model revision")
        if resolver is not None:
            pinned = resolver.load_model(model.id)
            if pinned._record != model._record:
                raise ValueError("Model content differs from the resolved revision")
        targets = {ref.target for ref in refs}
        if not targets:
            raise ValueError("role selection is empty")
        for contribution in composition.contributors:
            record = contribution.record
            if record.policy and targets & {
                ref.target for ref in record.policy.targets
            }:
                raise ValueError(
                    "policy-controlled targets must be revised through their policy"
                )
            if contribution.id != self.id:
                inherited = {ref.target for ref in record.unknowns or ()}
                inherited.update(
                    item.target.target
                    for field in ("assignments", "estimates")
                    for item in getattr(record, field) or ()
                )
                if targets & inherited:
                    raise ValueError(
                        "inherited roles must be revised in the included Specification"
                    )
        local_assignments = tuple(
            a for a in self.record.assignments or () if a.target.target not in targets
        )
        local_unknowns = tuple(
            r for r in self.record.unknowns or () if r.target not in targets
        )
        estimates = tuple(
            e for e in self.record.estimates or () if e.target.target not in targets
        )
        replacement = self.record.replace(
            metadata=self.metadata.replace(id=id, previous=self.id),
            assignments=local_assignments + (assignments or ()),
            unknowns=local_unknowns + (refs if assignments is None else ()),
            estimates=estimates,
        )
        revised = self.revise(replacement)
        revised.compose(resolver=resolver)
        return revised
