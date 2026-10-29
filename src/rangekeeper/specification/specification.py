"""A saved investigation contribution, distinct from its derived composition."""

from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rangekeeper.model import Model
    from rangekeeper.shared.table import Table
from dataclasses import dataclass
from typing import Self
from uuid import UUID, uuid4

from rangekeeper.model.formulation.validation import check_formulation_names
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.schema.index import RecordIndex
from rangekeeper.schema.records import Metadata, Reference
from rangekeeper.schema.records import Specification as SpecificationRecord
from rangekeeper.schema.revision import check_revision
from rangekeeper.schema.runtime import UNSET
from rangekeeper.schema.validation import (
    check_known_reference_types,
    document_version,
    supports_version,
)
from rangekeeper.shared.arguments import optional_text
from rangekeeper.shared.diagnostics import ValidationReport
from rangekeeper.shared.errors import UnitError, UnsupportedVersionError
from rangekeeper.shared.references import SpecificationResolver
from rangekeeper.shared.validation import bounded, require
from rangekeeper.specification.composition import (
    Composition,
    check_local_header,
    check_roles,
    check_settings,
)
from rangekeeper.specification.roles import equation_targets, in_model_order, role_table


def _validate_local(record: SpecificationRecord) -> ValidationReport:
    """Report local ownership and role problems; unresolved external inputs are allowed.

    An unsupported schema version raises UnsupportedVersionError.
    """
    data = record.to_data()
    index = RecordIndex.build(record)
    version = document_version("Specification")
    if not supports_version(record.metadata.schema_version, version):
        raise UnsupportedVersionError(record.metadata.schema_version)

    def check():
        check_local_header(data, version)
        check_known_reference_types(record, index=index)
        require(
            record.metadata.previous not in index.records,
            "Specification predecessor targets current scope",
        )
        check_roles(data)
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
        check_settings(data.get("settings") or {})

        check_formulation_names(data.get("formulations") or [])

    return bounded([], check, document=data)


@dataclass(frozen=True, init=False, eq=False)
class Specification:
    """Immutable locally valid contribution, including partial contributions/batches.

    External resolution and complete solve roles belong to composition validation.
    The ``record`` property exposes all generated fields with their original types;
    this facade does not redeclare the authoritative field schema.

    ``model.specify()`` makes a Specification of a Model revision. Each chained
    call, such as ``fix`` and ``free``, returns a new Specification with new
    Metadata; the Specification that it was called on does not change.

    A value that is not fixed is free: the solve finds it. ``specify`` and each
    chained call record as unknowns the values that the equations use and that
    no fix or rule controls.
    """

    __slots__ = ("_record", "_model", "_resolver")
    _record: SpecificationRecord
    _model: "Model | None"
    _resolver: SpecificationResolver | None

    def __init__(
        self,
        record: SpecificationRecord,
        *,
        model: "Model | None" = None,
        resolver: SpecificationResolver | None = None,
    ) -> None:
        """Validate a record locally and return its facade.

        ``model`` is the Model revision that the record pins. The facade keeps
        it, and ``resolver`` for its includes, so that chained calls can find
        values by key. Neither is part of the saved document.
        """
        from rangekeeper.model import Model

        if not isinstance(record, SpecificationRecord):
            raise TypeError("record must be a generated Specification record")
        if model is not None:
            if not isinstance(model, Model):
                raise TypeError("model must be a Model")
            if record.model is not None and record.model != model.id:
                raise ValueError(
                    "model must be the Model revision that the record pins"
                )
        _validate_local(record).raise_if_invalid()
        object.__setattr__(self, "_record", record)
        object.__setattr__(self, "_model", model)
        object.__setattr__(self, "_resolver", resolver)

    @classmethod
    def _start(
        cls,
        model: "Model",
        *,
        name: str | None,
        description: str | None,
    ) -> "Specification":
        """Return an empty Specification that pins a Model revision."""
        optional_text(name, "name", empty=False)
        optional_text(description, "description")
        metadata = Metadata(
            id=uuid4(),
            schema_version=document_version("Specification"),
            name=UNSET if name is None else name,
            description=UNSET if description is None else description,
        )
        record = SpecificationRecord(metadata=metadata, model=model.id)
        unknowns = tuple(
            Reference(target=identity) for identity in equation_targets(model, record)
        )
        if unknowns:
            record = record.replace(unknowns=unknowns)
        return cls(record, model=model)

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
    def model_id(self) -> UUID | None:
        """UUID of the Model revision that this Specification pins, or None."""
        return self._record.model

    @property
    def roles(self) -> "Table":
        """Return the role of each value: fixed with its Quantity, free or decided.

        The Table has the columns ``key``, ``movement`` (a Movement UUID, or None
        for a scalar Value), ``role`` (a ``Role``) and ``quantity`` (the fixed
        Quantity, or None), in Model order. Each Row's ``id`` is its target's UUID.
        A Specification with includes needs its resolver; a batch has no roles.
        """
        model = self._require_model()
        if self.record.cases:
            raise ValueError("a batch has no roles; read the roles of one case")
        record = self.record
        if record.includes:
            if self._resolver is None:
                raise ValueError("included Specifications require a resolver")
            record = self.compose(resolver=self._resolver).requirements
        return role_table(model, record)

    @property
    def record(self) -> SpecificationRecord:
        """Read-only typed access to assignments, roles, include/case edges and settings."""
        return self._record

    def to_data(self) -> dict[str, object]:
        """Export detached saved content, retaining include/case boundaries and presence."""
        return self._record.to_data()

    def __repr__(self) -> str:
        return f"Specification(id={self.id!r}, includes={len(self.record.includes or ())}, cases={len(self.record.cases or ())})"

    def validate(
        self,
        *,
        resolver: SpecificationResolver | None = None,
        units: UnitSystem | None = None,
    ) -> ValidationReport:
        """Report the problems of this contribution; content problems raise nothing.

        Without ``resolver``, the check repeats the local rules of construction.
        With ``resolver``, it resolves the includes and cases, composes each
        concrete case and checks it against its input Model, as execution does.
        A partial contribution then reports what it lacks, for example its
        input Model. ``units`` replaces the unit system of each input Model.
        """
        from rangekeeper.specification.validation import validate_document

        return validate_document(self, resolver=resolver, units=units)

    def check(
        self,
        *,
        resolver: SpecificationResolver | None = None,
        units: UnitSystem | None = None,
    ) -> Self:
        """Return this contribution if ``validate`` finds no problem.

        Otherwise raise ValidationError; its ``report`` holds the problems.
        """
        self.validate(resolver=resolver, units=units).raise_if_invalid()
        return self

    def compose(self, *, resolver: SpecificationResolver) -> Composition:
        """Resolve this contribution to one immutable additive investigation."""
        from rangekeeper.specification.composition import compose

        return compose(self, resolver=resolver)

    def revise(self, replacement: SpecificationRecord) -> "Specification":
        """Accept a complete locally valid replacement with explicit new identity/lineage.

        No include is resolved and no missing requirement is inherited implicitly.
        Metadata-only identity changes and schema-version migrations are rejected.
        The new Specification keeps the Model and resolver of this one.
        """
        if not isinstance(replacement, SpecificationRecord):
            raise TypeError("replacement must be a generated Specification record")
        check_revision(self._record, replacement)
        return type(self)(replacement, model=self._model, resolver=self._resolver)

    def _derive(
        self,
        *,
        model: "Model | None" = None,
        **changes: object,
    ) -> "Specification":
        """Return the next revision with these record changes and new Metadata.

        Each chained call makes its revision here: a new UUID, and ``previous``
        is this revision. ``model`` pins another Model revision and keeps it.
        """
        if model is None:
            model = self._model
        else:
            changes["model"] = model.id
        replacement = self._record.replace(
            metadata=self.metadata.replace(id=uuid4(), previous=self.id),
            **changes,  # type: ignore[arg-type]
        )
        check_revision(self._record, replacement)
        return type(self)(replacement, model=model, resolver=self._resolver)

    def fix(
        self,
        targets: "Mapping[str | UUID | Reference, Quantity | str | float | Decimal | Mapping[UUID, Quantity | str | float | Decimal]] | None" = None,
        /,
        **values: "Quantity | str | float | Decimal | Mapping[UUID, Quantity | str | float | Decimal]",
    ) -> "Specification":
        """Return a new Specification that fixes values, by key.

        Name each value by its key, ``fix(land_cost="20e6 AUD")``. The mapping
        form also takes a dotted path (``"building_a.income"``), a Value or
        Movement UUID, or a Reference. A bare key must name one Value of the
        Model. A value is a Quantity, Quantity text such as ``"65 %"``, or a
        bare number for a ratio (``coverage=1.25``). Its units must be
        compatible with the units of the value. One value fixes a scalar
        value, or each Movement of a Flow; a mapping from Movement UUIDs to
        values fixes those Movements only. A fix replaces an earlier fix or
        free of the same target. When no role changes, ``fix`` returns this
        Specification.
        """
        from rangekeeper.model.targets import target_units
        from rangekeeper.schema.records import Assignment

        items = dict(targets or {})
        for key, quantity in values.items():
            if key in items:
                raise TypeError(f"{key} is given twice")
            items[key] = quantity
        if not items:
            raise TypeError("fix takes at least one value")
        model = self._require_model()
        refs: list[Reference] = []
        assignments = []
        for target, quantity in items.items():
            ids = tuple(quantity) if isinstance(quantity, Mapping) else None
            selected = self._targets(model, target, ids=ids)
            for ref in selected:
                q = _quantity(
                    quantity[ref.target] if isinstance(quantity, Mapping) else quantity,
                    target=target,
                    units=target_units(model, ref),
                    unit_system=model.unit_system,
                )
                assignments.append(Assignment(target=ref, quantity=q))
            refs.extend(selected)
        return self._edit_roles(refs, tuple(assignments))

    def free(self, *targets: "str | UUID | Reference") -> "Specification":
        """Return a new Specification that frees values: the solve finds them.

        A value that is not fixed is already free; ``free`` releases a value
        that was fixed before. Each target is a key, a dotted path, a Value or
        Movement UUID, or a Reference, as in ``fix``. A Flow frees each of its
        Movements. A free removes an earlier fix of the same target. When no
        role changes, ``free`` returns this Specification.
        """
        if not targets:
            raise TypeError("free takes at least one value")
        model = self._require_model()
        refs = [ref for target in targets for ref in self._targets(model, target)]
        return self._edit_roles(refs, None)

    def on(self, *, model: "Model") -> "Specification":
        """Return a new Specification of another Model revision, with the same roles.

        Each fix, estimate and rule target must be a Value or Movement that
        ``model`` declares, with units that its Quantity converts to. A fixed
        value that ``model`` does not declare raises ContractError with the code
        ``REFERENCE_MISSING`` and its keys: free it first, then call ``on``. The
        free values are those that the equations of ``model`` use and that
        nothing controls; an estimate of another value is dropped.

        A Specification with includes, or a batch, raises ValueError. When
        ``model`` is the pinned revision, ``on`` returns this Specification.
        """
        from rangekeeper.model import Model
        from rangekeeper.model.targets import target_units
        from rangekeeper.shared.codes import Code
        from rangekeeper.shared.errors import ContractError

        if not isinstance(model, Model):
            raise TypeError("model must be a Model")
        if self.record.cases:
            raise ValueError("move each case of a batch, not the batch")
        if self.record.includes:
            raise ValueError(
                "a Specification with includes cannot move to another Model; "
                "move each included Specification"
            )
        if model.id == self.record.model:
            if self._model is not None:
                return self
            return type(self)(self.record, model=model, resolver=self._resolver)
        record = self.record
        declared = model._index.records
        controlled = [a.target for a in record.assignments or ()]
        if record.rules is not None:
            controlled.extend(record.rules.targets)
        missing = [ref.target for ref in controlled if ref.target not in declared]
        if missing:
            keys = tuple(self._key(identity) for identity in missing)
            raise ContractError(
                f"Model {model.id} does not declare these fixed or decided "
                f"values: {', '.join(keys)}; free them first, then call on",
                code=Code.REFERENCE_MISSING,
                document_id=self.id,
                targets=missing,
                values={"keys": keys},
            )
        for assignment in record.assignments or ():
            model.unit_system.convert(
                assignment.quantity, to=target_units(model, assignment.target)
            )
        for estimate in record.estimates or ():
            if estimate.target.target in declared:
                model.unit_system.convert(
                    estimate.quantity, to=target_units(model, estimate.target)
                )
        taken = {ref.target for ref in controlled}
        unknowns = tuple(
            Reference(target=identity)
            for identity in equation_targets(model, record)
            if identity not in taken
        )
        free = {ref.target for ref in unknowns}
        return self._derive(
            model=model,
            unknowns=unknowns,
            estimates=tuple(
                e for e in record.estimates or () if e.target.target in free
            ),
        )

    def _key(self, identity: UUID) -> str:
        """Name a target by its key in the pinned Model, or by its UUID."""
        if self._model is None or identity not in self._model._index.records:
            return str(identity)
        from rangekeeper.specification.roles import target_key

        return target_key(self._model, identity)

    def _require_model(self) -> "Model":
        if self._model is None:
            raise ValueError(
                "this Specification has no Model; make it with model.specify() "
                "or pass model= to Specification(...)"
            )
        return self._model

    @staticmethod
    def _targets(model, target, *, ids=None) -> "tuple[Reference, ...]":
        from rangekeeper.specification.targets import expand_targets

        if isinstance(target, str):
            target = model._value_at(target).id
        return expand_targets(model, target, ids=ids)

    def _edit_roles(self, refs, assignments):
        model = self._model
        resolver = self._resolver
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
        if len(targets) != len(refs):
            raise ValueError("a target is selected more than once")
        for contribution in composition.contributors:
            record = contribution.record
            if record.rules and targets & {ref.target for ref in record.rules.targets}:
                raise ValueError(
                    "rule-controlled targets must be revised through their rules"
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
        local_assignments += assignments or ()
        local_unknowns = tuple(
            r for r in self.record.unknowns or () if r.target not in targets
        )
        if assignments is None:
            local_unknowns += tuple(refs)
        estimates = tuple(
            e for e in self.record.estimates or () if e.target.target not in targets
        )
        # A value that the equations use and that nothing controls is free.
        controlled = {a.target.target for a in local_assignments}
        controlled.update(r.target for r in local_unknowns)
        for contribution in composition.contributors:
            record = contribution.record
            if record.rules:
                controlled.update(ref.target for ref in record.rules.targets)
            if contribution.id != self.id:
                controlled.update(ref.target for ref in record.unknowns or ())
                controlled.update(
                    item.target.target
                    for field in ("assignments", "estimates")
                    for item in getattr(record, field) or ()
                )
        local_unknowns += tuple(
            Reference(target=identity)
            for identity in equation_targets(model, self.record)
            if identity not in controlled
        )
        unknowns = in_model_order(model, local_unknowns)
        if (
            local_assignments == (self.record.assignments or ())
            and unknowns == (self.record.unknowns or ())
            and estimates == (self.record.estimates or ())
        ):
            # The roles do not change: a free of a free value, or the same fix.
            return self
        revised = self._derive(
            assignments=local_assignments,
            unknowns=unknowns,
            estimates=estimates,
        )
        revised.compose(resolver=resolver)
        return revised


def _quantity(
    value: object,
    *,
    target: object,
    units: str,
    unit_system: UnitSystem,
) -> Quantity:
    """Return the Quantity that fixes a target, after a check of its units.

    Text is read as a Quantity. A bare number is a ratio, so its target must have
    dimensionless units.
    """
    if isinstance(value, Quantity):
        quantity = value
    elif isinstance(value, str):
        quantity = Quantity(text=value)
    elif isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        quantity = Quantity(magnitude=value, units="ratio")
        if not unit_system.compatible("ratio", units):
            raise UnitError(
                f"a bare number fixes a ratio, but {target} has units {units!r}; "
                f"give a Quantity or text with units, such as '{value} {units}'"
            )
    else:
        raise TypeError(
            f"the value of {target} must be a Quantity, Quantity text, a number "
            "or a mapping from Movement UUIDs to these"
        )
    unit_system.convert(quantity, to=units)
    return quantity


from rangekeeper.model import model as _model_module  # noqa: E402

# Model.specify makes a Specification through this registration (ADR-010).
_model_module._SPECIFICATION = Specification
