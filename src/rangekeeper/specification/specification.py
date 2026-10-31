"""A saved investigation contribution, distinct from its derived composition."""

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rangekeeper.market.paths import Paths
    from rangekeeper.model import Model
    from rangekeeper.shared.table import Table
from dataclasses import dataclass
from types import MappingProxyType
from typing import Self
from uuid import UUID, uuid4

from rangekeeper.duration.dates import NEVER, Never
from rangekeeper.flow import Flow
from rangekeeper.model.formulation.validation import check_formulation_names
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.schema.index import RecordIndex
from rangekeeper.schema.records import (
    Assignment,
    Metadata,
    Reference,
    RuleDeclaration,
)
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
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.shared.errors import (
    ContractError,
    IdentityConflictError,
    MissingReferenceError,
    UnsupportedVersionError,
)
from rangekeeper.shared.references import SpecificationResolver
from rangekeeper.shared.validation import bounded, require
from rangekeeper.specification import _paths
from rangekeeper.specification.composition import (
    Composition,
    check_local_header,
    check_path,
    check_settings,
)
from rangekeeper.specification.roles import (
    decided_targets,
    equation_targets,
    in_model_order,
    role_table,
)
from rangekeeper.specification.rule._declaration import (
    Rule,
    Rules,
    check_declared,
    declare,
    path_movements,
    rule_of,
)
from rangekeeper.specification.rule._query import read_targets, references
from rangekeeper.specification.targets import checked_quantity


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
        check_path(data)
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
    no fix or rule controls. A rule fixes a value during the solve: that value is
    decided, and ``rules`` gives its rule.
    """

    __slots__ = ("_record", "_model", "_resolver", "_cases", "_paths")
    _record: SpecificationRecord
    _model: "Model | None"
    _resolver: SpecificationResolver | None
    # The case Specifications that ``cases`` made, by UUID; not saved.
    _cases: "Mapping[UUID, Specification]"
    # The Paths document of a case that ``across`` made; not saved.
    _paths: "Paths | None"

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
        object.__setattr__(self, "_paths", None)

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
        elif record.path is not None:
            # The path's assignments come from its Paths document.
            record = self.compose(resolver=self._resolver).requirements  # type: ignore[arg-type]
        return role_table(model, record)

    @property
    def rules(self) -> Rules:
        """Return the rules of this Specification by key, in the order that they run.

        ``rules[key]`` is a Rule with the fixed values that it reads, its
        ``triggers``, so another Specification can reuse it:
        ``fixed.fix(start_date=timing["start_date"])``. A key without a rule raises
        MissingReferenceError. A Specification with includes needs its resolver; a
        batch has no rules of its own.
        """
        model = self._require_model()
        self._require_concrete("rules", "read the rules of one case")
        record = self.record
        if record.includes:
            record = self.compose(resolver=self._require_resolver("rules")).requirements
        assignments = record.assignments or ()
        return Rules(
            rules={
                model.key_of(item.target.target): rule_of(
                    item, model=model, assignments=assignments
                )
                for item in record.declared_rules or ()
            },
            where=self._where,
        )

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
        is this revision. ``model`` pins another Model revision and keeps it,
        without the resolver: that resolver holds the documents of the earlier
        revision.
        ``name`` is the Metadata name of the new revision; None keeps the name.
        ``cases`` maps the UUID of each case to its Specification: the new
        revision is a batch that pins the same Model, lists those cases and
        keeps them.
        """
        resolver = self._resolver
        if model is None:
            model = self._model
        else:
            changes["model"] = model.id
            resolver = None
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
        revised = type(self)(record=replacement, model=model, resolver=resolver)
        if isinstance(documents, Mapping):
            object.__setattr__(revised, "_cases", MappingProxyType(dict(documents)))
        return revised

    def across(
        self,
        *,
        paths: "Paths",
        series: "Mapping[str, str | Mapping[str, str]] | None" = None,
    ) -> "Specification":
        """Return a batch Specification with one case for each path of ``paths``.

        Each case fixes each Model value from the path series with the same
        key; ``series`` maps a Model key to a series whose name differs, such
        as ``series={"rent_index": "market_index"}``. Each case is a new
        revision of this Specification: its Metadata name is the path key, and
        it refers to its path by the UUID of ``paths`` and the key, without
        copying the amounts. Its composition expands the path into
        assignments. The batch keeps the cases and ``paths``, so ``solve``
        resolves them; ``execute`` puts ``paths`` in its store.

        A series that fixes no value, a key of ``series`` that the paths lack,
        a value with two series, and a value that this Specification fixes or
        a rule decides raise ContractError, whose ``values`` list the path
        series and the Model keys. A value must be a Flow over the Periods of
        the paths (``ALIGNMENT_DIFFER``) in units that the series converts to
        (UnitError). A rule that reads a Flow that the paths leave free raises
        ValidationError with the code ``rule_reads_unknown``.
        """
        from rangekeeper.market.paths import Paths

        if not isinstance(paths, Paths):
            raise TypeError("paths must be rk.market.Paths")
        self._require_concrete("across", "call across on each case")
        self._require_no_path("across")
        model = self._require_model()
        matches = _paths.match(model=model, paths=paths, series=series)
        bindings = _paths.bindings(model=model, paths=paths, matches=matches)
        fixed = {ref.target for binding in bindings for ref in binding.movements}
        requirements = self._check_edit(model, []).requirements
        given = {a.target.target for a in requirements.assignments or ()}
        taken = given | {ref.target for ref in decided_targets(requirements)}
        clash = [
            item.key
            for item, binding in zip(matches, bindings, strict=True)
            if {ref.target for ref in binding.movements} & taken
        ]
        if clash:
            raise ContractError(
                f"this Specification fixes or decides {', '.join(clash)}, which "
                "the paths fix too; free it first, then call across",
                document_id=self.id,
                values={
                    "keys": clash,
                    "series": list(paths.names),
                },
            )
        check_declared(
            requirements.declared_rules or (),
            model=model,
            fixed=given | fixed,
            document_id=self.id,
        )
        unknowns = tuple(
            ref for ref in self.record.unknowns or () if ref.target not in fixed
        )
        estimates = tuple(
            e for e in self.record.estimates or () if e.target.target not in fixed
        )
        made: dict[UUID, Specification] = {}
        for key in paths.keys:
            case = self._derive(
                name=key,
                path=_paths.path_case(paths=paths, key=key, series=bindings),
                unknowns=unknowns,
                estimates=estimates,
            )
            object.__setattr__(case, "_paths", paths)
            made[case.id] = case
        batch = self._derive(cases=made)
        object.__setattr__(batch, "_paths", paths)
        return batch

    def _require_no_path(self, call: str) -> None:
        """Raise ContractError when this Specification is a case that ``across`` made."""
        if self.record.path is not None:
            raise ContractError(
                f"{call} takes a Specification without a path; this case takes its "
                "values from a path: change the Specification that across was "
                "called on, then call across again",
                document_id=self.id,
            )

    def fix(
        self,
        targets: "Mapping[str | UUID | Reference, Quantity | str | float | Decimal | date | Never | Flow | Rule | Mapping[UUID, Quantity | str | float | Decimal]] | None" = None,
        /,
        **values: "Quantity | str | float | Decimal | date | Never | Flow | Rule | Mapping[UUID, Quantity | str | float | Decimal]",
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
        values fixes those Movements only. A Flow fixes a Flow value: each
        Movement takes the amount over the same Period, or on the same date,
        such as ``fix(rent_index=paths.mean(name="rent_index"))``; a Flow
        with other Periods raises ContractError. A fix replaces an earlier fix or
        free of the same target. When no role changes, ``fix`` returns this
        Specification.

        A Rule makes the value decided: the solve finds it. Rules run in the order
        that they are fixed, and a later ``fix`` of the same key replaces the rule
        or the value, a rule in the same position. A Rule that ``rules`` gave brings
        each fixed value that it reads and that this Specification does not fix.
        A condition that reads the future raises AvailabilityError. ValidationError
        reports a condition that reads a later rule (``rule_order``), one that
        reads a free input (``rule_reads_unknown``) and a rule of another kind than
        its value (``rule_capability``). A Flow counts as known here, because a
        later ``across`` can fix it; ``across`` and the solve check it again.
        """
        items = dict(targets or {})
        for key, quantity in values.items():
            if key in items:
                raise TypeError(f"{key} is given twice")
            items[key] = quantity
        if not items:
            raise TypeError("fix takes at least one value")
        self._require_no_path("fix")
        return self._fix(items)

    def _fix(self, items: Mapping, *, name: str | None = None) -> "Specification":
        """Fix each target of ``items`` to its value; ``name`` renames the revision."""
        model = self._require_model()
        refs: list[Reference] = []
        assignments = []
        rules = {key: rule for key, rule in items.items() if isinstance(rule, Rule)}
        items = {key: item for key, item in items.items() if key not in rules}
        for target, value in items.items():
            quantity = (
                self._by_movement(model, target, value)
                if isinstance(value, Flow)
                else value
            )
            ids = tuple(quantity) if isinstance(quantity, Mapping) else None
            selected = self._targets(model, target, ids=ids)
            for ref in selected:
                given = (
                    quantity[ref.target] if isinstance(quantity, Mapping) else quantity
                )
                assignments.append(_assignment(model, ref, given, target=target))
            refs.extend(selected)
        if not rules:
            return self._edit_roles(refs, tuple(assignments), name=name)
        return self._fix_rules(rules, refs=refs, assignments=assignments, name=name)

    def _fix_rules(
        self,
        rules: Mapping,
        *,
        refs: "list[Reference]",
        assignments: "list[Assignment]",
        name: str | None,
    ) -> "Specification":
        """Return the revision with ``rules`` and the fixes that come with them."""
        model = self._require_model()
        declared = _declared(self, rules, model=model)
        requirements = self._check_edit(model, []).requirements
        present = {a.target.target for a in assignments}
        present.update(ref.target for ref in decided_targets(requirements))
        present.update(a.target.target for a in requirements.assignments or ())
        present.update(rule.target.target for rule in declared.values())
        for rule in rules.values():
            for key, value in rule.triggers.items():
                ref = Reference(target=model.value(key=key).id)
                if ref.target not in present:
                    present.add(ref.target)
                    refs.append(ref)
                    assignments.append(_assignment(model, ref, value, target=key))
        refs.extend(rule.target for rule in declared.values())
        return self._edit_roles(
            refs,
            tuple(assignments),
            rules=_placed(self.record.declared_rules or (), declared),
            name=name,
        )

    def free(self, *targets: "str | UUID | Reference") -> "Specification":
        """Return a new Specification that frees values: the solve finds them.

        A value that is not fixed is already free; ``free`` releases a value
        that was fixed before. Each target is a key, a dotted key, a Value or
        Movement UUID, or a Reference, as in ``fix``. A Flow frees each of its
        Movements. A free removes an earlier fix or rule of the same target. When
        no role changes, ``free`` returns this Specification. A rule that then
        reads the free value raises ValidationError with ``rule_reads_unknown``.
        """
        if not targets:
            raise TypeError("free takes at least one value")
        self._require_no_path("free")
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
        self._require_no_path("cases")
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

        The new Specification keeps ``model`` and no resolver: it has no
        includes or cases to load, and a resolver of the earlier revision, such
        as the documents of a file, does not hold ``model``.

        A Specification with includes, or a batch, raises ValueError. When
        ``model`` is the pinned revision, ``on`` returns this Specification.
        """
        from rangekeeper.model import Model

        if not isinstance(model, Model):
            raise TypeError("model must be a Model")
        self._require_concrete("on", "move each case")
        self._require_no_path("on")
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
        controlled.extend(decided_targets(record))
        read = [
            Reference(target=token)
            for rule in record.declared_rules or ()
            for token in _rule_reads(rule)
        ]
        missing = [
            ref.target for ref in (*controlled, *read) if ref.target not in declared
        ]
        if missing:
            keys = tuple(self._key(identity) for identity in missing)
            raise ContractError(
                f"Model {model.id} does not declare these fixed, decided or read "
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
    def _by_movement(
        model: "Model", target: "str | UUID | Reference", flow: Flow
    ) -> "dict[UUID, Quantity]":
        """Return the amount of ``flow`` for each Movement of the Flow ``target``."""
        from rangekeeper.specification.targets import flow_amounts

        if isinstance(target, str):
            identity = model.value(key=target).id
        elif isinstance(target, Reference):
            identity = target.target
        else:
            identity = target
        return flow_amounts(model, identity, flow=flow)

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
        rules: "tuple[RuleDeclaration, ...] | None" = None,
        name: str | None = None,
    ) -> "Specification":
        """Return the revision that fixes ``refs`` to ``assignments``, or frees them.

        ``assignments`` is None for a free. A fix replaces the estimate of its
        target; a free keeps it. ``rules`` are the new rules; without them, the
        rule of each target of ``refs`` goes. When no role changes, return this
        Specification.
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
        declared = rules
        if declared is None:
            declared = tuple(
                rule
                for rule in record.declared_rules or ()
                if rule.target.target not in targets
            )
        controlled.update(rule.target.target for rule in declared)
        local_unknowns += tuple(
            Reference(target=identity)
            for identity in equation_targets(model, record)
            if identity not in controlled
        )
        unknowns = in_model_order(model, local_unknowns)
        if name is None and (local_assignments, unknowns, estimates, declared) == (
            record.assignments or (),
            record.unknowns or (),
            record.estimates or (),
            record.declared_rules or (),
        ):
            # The roles do not change: a free of a free value, or the same fix.
            return self
        # A Specification that never had a rule stores no empty list of rules.
        changes: dict[str, Any] = {
            "assignments": local_assignments,
            "unknowns": unknowns,
            "estimates": estimates,
        }
        if declared or record.declared_rules:
            changes["declared_rules"] = declared
        revised = self._derive(name=name, **changes)
        # A Specification without includes composes without a resolver.
        composed = revised.compose(resolver=self._resolver)  # type: ignore[arg-type]
        # A fix without a rule only adds what a rule can read.
        if rules is not None or assignments is None:
            requirements = composed.requirements
            given = {a.target.target for a in requirements.assignments or ()}
            check_declared(
                requirements.declared_rules or (),
                model=model,
                fixed=given | path_movements(model),
                document_id=revised.id,
            )
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


def _declared(
    specification: "Specification", rules: Mapping, *, model: "Model"
) -> "dict[UUID, RuleDeclaration]":
    """Return the stored record of each Rule, by the UUID of the value it decides.

    A record that does not fit its value raises ValidationError.
    """
    found = {}
    for target, rule in rules.items():
        value = model.value(key=target) if isinstance(target, str) else None
        if value is None:
            identity = target.target if isinstance(target, Reference) else target
            value = model.value(id=identity)
        try:
            found[value.id] = declare(rule, target=value, model=model)
        except ContractError as error:
            issue = Issue.from_error(error, document_id=specification.id)
            ValidationReport((issue,)).raise_if_invalid()
    return found


def _placed(
    current: "Sequence[RuleDeclaration]", new: "dict[UUID, RuleDeclaration]"
) -> "tuple[RuleDeclaration, ...]":
    """Return the rules with each new one in the position of the one it replaces."""
    kept = [new.get(rule.target.target, rule) for rule in current]
    held = {rule.target.target for rule in current}
    kept.extend(rule for token, rule in new.items() if token not in held)
    return tuple(kept)


def _rule_reads(rule: RuleDeclaration) -> "tuple[UUID, ...]":
    """Return each Value that a rule's condition and bounds read."""
    found = dict.fromkeys(read_targets(rule.condition))
    for bound in (rule.earliest, rule.latest):
        if bound is not None:
            found.update(dict.fromkeys(references(bound)))
    return tuple(found)


def _controlled(composition: Composition, *, local: UUID) -> set[UUID]:
    """Return the targets that rules and included Specifications control."""
    controlled: set[UUID] = set()
    for contribution in composition.contributors:
        record = contribution.record
        controlled.update(ref.target for ref in decided_targets(record))
        if contribution.id != local:
            controlled.update(_roles(record))
    return controlled


def _roles(record: SpecificationRecord) -> set[UUID]:
    """Return the targets that a Specification fixes, frees, estimates or decides."""
    found = {ref.target for ref in record.unknowns or ()}
    found.update(rule.target.target for rule in record.declared_rules or ())
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
    quantity = checked_quantity(
        value,
        target=target,
        units=target_units(model, ref),
        unit_system=model.unit_system,
    )
    return Assignment(target=ref, quantity=quantity)


from rangekeeper.model import model as _model_module  # noqa: E402

# Model.specify makes a Specification through this registration (ADR-010).
_model_module._SPECIFICATION = Specification
