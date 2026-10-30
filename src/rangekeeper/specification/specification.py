"""A saved investigation contribution, distinct from its derived composition."""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rangekeeper.model import Model
    from rangekeeper.shared.table import Table
from dataclasses import dataclass
from types import MappingProxyType
from typing import Self
from uuid import UUID, uuid4

from rangekeeper.duration.dates import NEVER, Never
from rangekeeper.model.formulation.validation import check_formulation_names
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.schema.index import RecordIndex
from rangekeeper.schema.records import Assignment, Metadata, Reference
from rangekeeper.schema.records import Specification as SpecificationRecord
from rangekeeper.schema.revision import check_revision
from rangekeeper.schema.runtime import UNSET
from rangekeeper.schema.validation import (
    check_known_reference_types,
    document_version,
    supports_version,
)
from rangekeeper.shared.arguments import optional_text
from rangekeeper.shared.codes import Code
from rangekeeper.shared.diagnostics import ValidationReport
from rangekeeper.shared.errors import (
    ContractError,
    IdentityConflictError,
    MissingReferenceError,
    UnitError,
    UnsupportedVersionError,
)
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

    __slots__ = ("_record", "_model", "_resolver", "_cases")
    _record: SpecificationRecord
    _model: "Model | None"
    _resolver: SpecificationResolver | None
    # The case Specifications that ``cases`` made, by UUID; not saved.
    _cases: "Mapping[UUID, Specification]"

    def __init__(
        self,
        *,
        record: SpecificationRecord,
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
                raise ContractError(
                    f"model {model.id} is not the Model revision that the record "
                    f"pins, {record.model}",
                    code=Code.IDENTITY,
                    document_id=record.metadata.id,
                    targets=(record.model, model.id),
                    values={"pinned": record.model, "model": model.id},
                )
        _validate_local(record).raise_if_invalid()
        object.__setattr__(self, "_record", record)
        object.__setattr__(self, "_model", model)
        object.__setattr__(self, "_resolver", resolver)
        object.__setattr__(self, "_cases", MappingProxyType({}))

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
        return cls(record=record, model=model)

    @classmethod
    def from_data(cls, data: Mapping[str, object]) -> "Specification":
        """Copy and validate local structure/ownership; perform no external lookup."""
        return cls(record=SpecificationRecord.from_data(data))

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
    def model(self) -> "Model | None":
        """The pinned Model revision that this facade keeps, or None.

        ``model.specify()`` and each chained call keep it. It is not saved with
        the document: a Specification read from data has none.
        """
        return self._model

    @property
    def resolver(self) -> SpecificationResolver | None:
        """The resolver that this facade keeps for its includes, or None; not saved."""
        return self._resolver

    @property
    def roles(self) -> "Table":
        """Return the role of each value: fixed with its Quantity, free or decided.

        The Table has the columns ``key``, ``movement`` (a Movement UUID, or None
        for a scalar Value), ``role`` (a ``Role``) and ``quantity`` (the fixed
        Quantity, or None), in Model order. Each Row's ``id`` is its target's UUID.
        A Specification with includes needs its resolver; a batch has no roles.
        """
        model = self._require_model()
        self._require_concrete("roles", "read the roles of one case")
        record = self.record
        if record.includes:
            record = self.compose(resolver=self._require_resolver("roles")).requirements
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
        return type(self)(
            record=replacement, model=self._model, resolver=self._resolver
        )

    def _derive(
        self,
        *,
        model: "Model | None" = None,
        **changes: object,
    ) -> "Specification":
        """Return the next revision with these record changes and new Metadata.

        Each chained call makes its revision here: a new UUID, and ``previous``
        is this revision. ``model`` pins another Model revision and keeps it.
        ``name`` is the Metadata name of the new revision; None keeps the name.
        ``cases`` maps the UUID of each case to its Specification: the new
        revision is a batch that pins the same Model, lists those cases and
        keeps them.
        """
        if model is None:
            model = self._model
        else:
            changes["model"] = model.id
        metadata = self.metadata.replace(id=uuid4(), previous=self.id)
        name = changes.pop("name", None)
        if name is not None:
            metadata = metadata.replace(name=str(name))
        documents = changes.pop("cases", None)
        if isinstance(documents, Mapping):
            # A batch holds only its metadata, its Model and its cases.
            replacement = SpecificationRecord(
                metadata=metadata,
                model=UNSET if self._record.model is None else self._record.model,
                cases=tuple(documents),
            )
        else:
            replacement = self._record.replace(
                metadata=metadata,
                **changes,  # type: ignore[arg-type]
            )
        check_revision(self._record, replacement)
        revised = type(self)(record=replacement, model=model, resolver=self._resolver)
        if isinstance(documents, Mapping):
            object.__setattr__(revised, "_cases", MappingProxyType(dict(documents)))
        return revised

    def fix(
        self,
        targets: "Mapping[str | UUID | Reference, Quantity | str | float | Decimal | date | Never | Mapping[UUID, Quantity | str | float | Decimal]] | None" = None,
        /,
        **values: "Quantity | str | float | Decimal | date | Never | Mapping[UUID, Quantity | str | float | Decimal]",
    ) -> "Specification":
        """Return a new Specification that fixes values, by key.

        Name each value by its key, ``fix(land_cost="20e6 AUD")``. The mapping
        form also takes a dotted key (``"building_a.income"``), the text of a
        Value UUID, a Value or Movement UUID, or a Reference: each key that
        ``Model.value(key=)`` takes. A bare key must name one Value of the
        Model. A value is a Quantity, Quantity text such as ``"65 %"``, or a
        bare number for a ratio (``coverage=1.25``). Its units must be
        compatible with the units of the value. One value fixes a scalar
        value, or each Movement of a Flow; a mapping from Movement UUIDs to
        values fixes those Movements only. A fix replaces an earlier fix or
        free of the same target. When no role changes, ``fix`` returns this
        Specification.
        """
        items = dict(targets or {})
        for key, quantity in values.items():
            if key in items:
                raise TypeError(f"{key} is given twice")
            items[key] = quantity
        if not items:
            raise TypeError("fix takes at least one value")
        return self._fix(items)

    def _fix(self, items: Mapping, *, name: str | None = None) -> "Specification":
        """Fix each target of ``items`` to its value; ``name`` renames the revision."""
        model = self._require_model()
        refs: list[Reference] = []
        assignments = []
        for target, quantity in items.items():
            ids = tuple(quantity) if isinstance(quantity, Mapping) else None
            selected = self._targets(model, target, ids=ids)
            for ref in selected:
                given = (
                    quantity[ref.target] if isinstance(quantity, Mapping) else quantity
                )
                assignments.append(_assignment(model, ref, given, target=target))
            refs.extend(selected)
        return self._edit_roles(refs, tuple(assignments), name=name)

    def free(self, *targets: "str | UUID | Reference") -> "Specification":
        """Return a new Specification that frees values: the solve finds them.

        A value that is not fixed is already free; ``free`` releases a value
        that was fixed before. Each target is a key, a dotted key, a Value or
        Movement UUID, or a Reference, as in ``fix``. A Flow frees each of its
        Movements. A free removes an earlier fix of the same target. When no
        role changes, ``free`` returns this Specification.
        """
        if not targets:
            raise TypeError("free takes at least one value")
        model = self._require_model()
        refs = [ref for target in targets for ref in self._targets(model, target)]
        return self._edit_roles(refs, None)

    def cases(
        self,
        *,
        cases: "Mapping[str, Mapping[str | UUID | Reference, object]]",
    ) -> "Specification":
        """Return a batch Specification with one named case for each key.

        Each case is a new revision of this Specification: its Metadata name is
        the case key, and it fixes the values that its mapping gives, by key,
        as ``fix`` does. A value that a case gives replaces the fix of this
        Specification; an empty mapping keeps this Specification's values. The
        batch keeps this Specification's name, pins its Model and lists the
        cases in mapping order. It keeps the case Specifications, so ``solve``
        resolves them; ``execute`` puts them in its store.
        """
        self._require_concrete("cases", "make the cases from one case")
        if not isinstance(cases, Mapping) or not cases:
            raise TypeError("cases takes a mapping from case keys to values")
        made: dict[UUID, Specification] = {}
        for key, values in cases.items():
            if not isinstance(key, str):
                raise TypeError("each case key must be text")
            if not key.strip():
                raise ContractError(
                    "each case key must be non-empty text",
                    document_id=self.id,
                    values={"key": key},
                )
            if not isinstance(values, Mapping):
                raise TypeError(f"the values of case {key} must be a mapping")
            case = self._fix(values, name=key) if values else self._derive(name=key)
            made[case.id] = case
        return self._derive(cases=made)

    def case(self, *, key: str) -> "Specification":
        """Return the case of this batch with the key ``key``: its Metadata name.

        A batch that ``cases`` made keeps its cases; a batch read from data
        loads them with its resolver. No case with the key raises
        MissingReferenceError with the keys that exist.
        """
        if not self.record.cases:
            raise ContractError(
                "case takes a batch; this Specification has no cases",
                code=Code.BATCH_REQUIRED,
                document_id=self.id,
            )
        found = []
        for identity in self.record.cases:
            document = self._cases.get(identity)
            if document is None:
                document = self._require_resolver("case").load_specification(identity)
            found.append(document)
            if document.metadata.name == key:
                return document
        raise MissingReferenceError(
            key,
            kind="Specification",
            by="key",
            where=self._where,
            document_id=self.id,
            candidates=[str(d.metadata.name) for d in found if d.metadata.name],
        )

    def on(self, *, model: "Model") -> "Specification":
        """Return a new Specification of another Model revision, with the same roles.

        Each fix and rule target must be a Value or Movement that ``model``
        declares, with units that its Quantity converts to. A fixed value that
        ``model`` does not declare raises ContractError with the code
        ``REFERENCE_MISSING`` and its keys: free it first, then call ``on``. The
        free values are those that the equations of ``model`` use and that
        nothing controls. An estimate stays only when its target is free in
        ``model``, and its Quantity must convert to the units of the target;
        ``on`` drops the estimate of any other value.

        A Specification with includes, or a batch, raises ValueError. When
        ``model`` is the pinned revision, ``on`` returns this Specification.
        """
        from rangekeeper.model import Model

        if not isinstance(model, Model):
            raise TypeError("model must be a Model")
        self._require_concrete("on", "move each case")
        if self.record.includes:
            raise ContractError(
                "a Specification with includes cannot move to another Model; "
                "move each included Specification",
                code=Code.CONTRACT,
                document_id=self.id,
                targets=self.record.includes,
            )
        if model.id == self.record.model:
            if self._model is not None:
                return self
            return type(self)(record=self.record, model=model, resolver=self._resolver)
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
            _require_content(model, assignment)
        taken = {ref.target for ref in controlled}
        unknowns = tuple(
            Reference(target=identity)
            for identity in equation_targets(model, record)
            if identity not in taken
        )
        free = {ref.target for ref in unknowns}
        estimates = tuple(e for e in record.estimates or () if e.target.target in free)
        for estimate in estimates:
            _require_content(model, estimate)
        return self._derive(model=model, unknowns=unknowns, estimates=estimates)

    def _key(self, identity: UUID) -> str:
        """Name a target by its key in the pinned Model, or by its UUID."""
        if self._model is None:
            return str(identity)
        try:
            return self._model.key_of(identity)
        except LookupError:
            return str(identity)

    @property
    def _where(self) -> str:
        """Name this Specification in an error: its Metadata name, or its UUID."""
        return f"Specification {self.metadata.name or self.id}"

    def _require_model(self) -> "Model":
        if self._model is None:
            raise ContractError(
                "this Specification has no Model; make it with model.specify() "
                "or pass model= to Specification(...)",
                code=Code.MODEL_MISSING,
                document_id=self.id,
            )
        return self._model

    def _require_resolver(self, call: str) -> SpecificationResolver:
        """Return the resolver; ``call`` must load included or case Specifications."""
        if self._resolver is None:
            raise ContractError(
                f"{call} must load other Specifications; give this Specification "
                "a resolver",
                code=Code.RESOLVER_MISSING,
                document_id=self.id,
                targets=(*(self.record.includes or ()), *(self.record.cases or ())),
            )
        return self._resolver

    def _require_concrete(self, call: str, instead: str) -> None:
        """Raise ContractError when this Specification is a batch."""
        if self.record.cases:
            raise ContractError(
                f"{call} takes a concrete Specification, not a batch; {instead}",
                code=Code.BATCH_UNSUPPORTED,
                document_id=self.id,
            )

    @staticmethod
    def _targets(model, target, *, ids=None) -> "tuple[Reference, ...]":
        from rangekeeper.specification.targets import expand_targets

        if isinstance(target, str):
            target = model.value(key=target).id
        return expand_targets(model, target, ids=ids)

    def _edit_roles(
        self,
        refs: "list[Reference]",
        assignments: "tuple[Assignment, ...] | None",
        *,
        name: str | None = None,
    ) -> "Specification":
        """Return the revision that fixes ``refs`` to ``assignments``, or frees them.

        ``assignments`` is None for a free. A fix replaces the estimate of its
        target; a free keeps it. When no role changes, return this Specification.
        """
        model = self._require_model()
        composition = self._check_edit(model, refs)
        targets = {ref.target for ref in refs}
        record = self.record
        local_assignments = tuple(
            a for a in record.assignments or () if a.target.target not in targets
        ) + (assignments or ())
        local_unknowns = tuple(
            r for r in record.unknowns or () if r.target not in targets
        )
        if assignments is None:
            local_unknowns += tuple(refs)
        estimates = tuple(
            e
            for e in record.estimates or ()
            if assignments is None or e.target.target not in targets
        )
        # A value that the equations use and that nothing controls is free.
        controlled = {a.target.target for a in local_assignments}
        controlled.update(r.target for r in local_unknowns)
        controlled.update(_controlled(composition, local=self.id))
        local_unknowns += tuple(
            Reference(target=identity)
            for identity in equation_targets(model, record)
            if identity not in controlled
        )
        unknowns = in_model_order(model, local_unknowns)
        if name is None and (local_assignments, unknowns, estimates) == (
            record.assignments or (),
            record.unknowns or (),
            record.estimates or (),
        ):
            # The roles do not change: a free of a free value, or the same fix.
            return self
        revised = self._derive(
            assignments=local_assignments,
            unknowns=unknowns,
            estimates=estimates,
            name=name,
        )
        # A Specification without includes composes without a resolver.
        revised.compose(resolver=self._resolver)  # type: ignore[arg-type]
        return revised

    def _check_edit(self, model: "Model", refs: "list[Reference]") -> Composition:
        """Check that ``fix`` or ``free`` can change the roles of ``refs`` here.

        Return the Composition of this Specification. A batch, includes without
        a resolver, another Model revision, a target given twice, a target that
        a rule controls and a role that an included Specification gives raise
        Rangekeeper errors.
        """
        self._require_concrete("fix and free", "edit one case")
        resolver = self._resolver
        if self.record.includes:
            resolver = self._require_resolver("fix and free")
        composition = self.compose(resolver=resolver)  # type: ignore[arg-type]
        if composition.model_id != model.id:
            raise ContractError(
                f"the Composition uses Model {composition.model_id}, not the "
                f"pinned Model {model.id}",
                code=Code.IDENTITY,
                document_id=self.id,
                values={"pinned": model.id, "model": composition.model_id},
            )
        if resolver is not None and resolver.load_model(model.id)._record != (
            model._record
        ):
            raise IdentityConflictError(
                f"the resolver gives other content for Model {model.id}",
                document_id=self.id,
                targets=(model.id,),
            )
        targets = [ref.target for ref in refs]
        repeated = tuple(dict.fromkeys(t for t in targets if targets.count(t) > 1))
        if repeated:
            raise ContractError(
                "a target is selected more than once",
                code=Code.UNIQUE,
                document_id=self.id,
                targets=repeated,
            )
        for contribution in composition.contributors:
            _check_owned(contribution, set(targets), local=self.id)
        return composition


def _controlled(composition: Composition, *, local: UUID) -> set[UUID]:
    """Return the targets that rules and included Specifications control."""
    controlled: set[UUID] = set()
    for contribution in composition.contributors:
        record = contribution.record
        if record.rules:
            controlled.update(ref.target for ref in record.rules.targets)
        if contribution.id != local:
            controlled.update(_roles(record))
    return controlled


def _roles(record: SpecificationRecord) -> set[UUID]:
    """Return the targets that a Specification fixes, frees or estimates."""
    found = {ref.target for ref in record.unknowns or ()}
    found.update(a.target.target for a in record.assignments or ())
    found.update(e.target.target for e in record.estimates or ())
    return found


def _check_owned(
    contribution: "Specification", targets: set[UUID], *, local: UUID
) -> None:
    """Raise ContractError when a rule or an included Specification owns a target."""
    record = contribution.record
    ruled = targets & {
        ref.target for ref in (record.rules.targets if record.rules else ())
    }
    if ruled:
        raise ContractError(
            "a target that a rule controls changes only through its rule",
            document_id=local,
            targets=ruled,
            values={"rules": contribution.id},
        )
    inherited = targets & _roles(record) if contribution.id != local else set()
    if inherited:
        raise ContractError(
            f"change an inherited role in the included Specification {contribution.id}",
            document_id=local,
            targets=inherited,
            values={"included": contribution.id},
        )


def _require_content(model: "Model", assignment: Assignment) -> None:
    """Check that an Assignment's content fits its target in ``model``.

    A date Value takes a date or NEVER; another target takes a Quantity whose
    units convert to the target's units.
    """
    from rangekeeper.model.targets import date_target, target_units

    if date_target(model, assignment.target):
        require(
            assignment.quantity is None,
            "a date Value takes a date or NEVER",
            code=Code.CONTRACT,
        )
        return
    require(
        assignment.quantity is not None,
        "a date or NEVER fixes a date Value only",
        code=Code.CONTRACT,
    )
    assert assignment.quantity is not None
    model.unit_system.convert(
        quantity=assignment.quantity, to=target_units(model, assignment.target)
    )


def _assignment(
    model: "Model", ref: Reference, value: object, *, target: object
) -> Assignment:
    """Return the Assignment that fixes one target to a value.

    A date Value takes a ``datetime.date`` or ``rk.duration.NEVER``; another
    target takes a Quantity, Quantity text or a number for a ratio. A value of
    the other kind raises ContractError.
    """
    from rangekeeper.model.targets import date_target, target_units

    dated = value is NEVER or (
        isinstance(value, date) and not isinstance(value, datetime)
    )
    if date_target(model, ref):
        if not dated:
            raise ContractError(
                f"{target} is a date Value: fix it to a date or NEVER",
                targets=(ref.target,),
                values={"key": str(target)},
            )
        if value is NEVER:
            return Assignment(target=ref, never=NEVER)
        assert isinstance(value, date)
        return Assignment(target=ref, date=value)
    if dated:
        raise ContractError(
            f"a date fixes a date Value, and {target} is not one",
            targets=(ref.target,),
            values={"key": str(target)},
        )
    quantity = _quantity(
        value,
        target=target,
        units=target_units(model, ref),
        unit_system=model.unit_system,
    )
    return Assignment(target=ref, quantity=quantity)


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
                f"give a Quantity or text with units, such as '{value} {units}'",
                code=Code.INCOMPATIBLE_UNITS,
            )
    else:
        raise TypeError(
            f"the value of {target} must be a Quantity, Quantity text, a number "
            "or a mapping from Movement UUIDs to these"
        )
    if not unit_system.compatible(quantity.units, units):
        raise UnitError(
            f"incompatible units: {target} has units {units!r}, and the quantity "
            f"that fixes it {quantity.units!r}",
            code=Code.INCOMPATIBLE_UNITS,
        )
    unit_system.convert(quantity=quantity, to=units)
    return quantity


from rangekeeper.model import model as _model_module  # noqa: E402

# Model.specify makes a Specification through this registration (ADR-010).
_model_module._SPECIFICATION = Specification
