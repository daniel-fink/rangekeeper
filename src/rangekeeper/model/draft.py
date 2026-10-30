"""The draft of a Model revision: definitions, entities, values and equations.

``model.edit()`` returns a ``ModelDraft``. The draft collects changes and checks
each call when it is made. ``commit()`` validates the complete candidate once and
returns a new immutable revision. Entity handles declare values, Flows and
equations on one entity.
"""

import keyword
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from difflib import get_close_matches
from typing import TYPE_CHECKING, TypeVar
from uuid import UUID, uuid4

from rangekeeper.duration import Period
from rangekeeper.flow import Flow, Movement
from rangekeeper.model._mathematics import Mathematics
from rangekeeper.model._undeclared import Undeclared, Unknown, known_values
from rangekeeper.model.expression import terms
from rangekeeper.model.expression import text as equation_text
from rangekeeper.model.expression.catalogue import functions
from rangekeeper.model.expression.terms import Symbolic, Term
from rangekeeper.model.expression.text import RESERVED
from rangekeeper.model.formulation.authoring import identify
from rangekeeper.model.formulation.handle import FormulationHandle
from rangekeeper.model.update import Update
from rangekeeper.quantity import UnitSystem
from rangekeeper.schema.enums import ExpressionKind, Operator, ValueKind
from rangekeeper.schema.records import (
    Assembly,
    Characteristics,
    Classification,
    Definitions,
    Entity,
    Expression,
    Function,
    Measure,
    Relationship,
    System,
    Taxonomy,
    Value,
)
from rangekeeper.schema.runtime import UNSET, Unset
from rangekeeper.shared.arguments import optional_text, require_code, require_text
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    AmbiguousReferenceError,
    ContractError,
    EquationError,
    MissingReferenceError,
    RevisionConflictError,
)

if TYPE_CHECKING:
    from rangekeeper.model.model import Model

# The Taxonomy that holds a classification given by code for an Entity or a
# Relationship, when no Taxonomy has that code yet.
ENTITY_TAXONOMY = "entity"
RELATIONSHIP_TAXONOMY = "relationship"
# Operators whose result is Boolean, so that an expression with one at its root
# can be an equation.
_RELATIONS = frozenset(
    {
        Operator.EQUAL,
        Operator.NOT_EQUAL,
        Operator.LESS_THAN,
        Operator.LESS_THAN_OR_EQUAL,
        Operator.GREATER_THAN,
        Operator.GREATER_THAN_OR_EQUAL,
        Operator.LOGICAL_NOT,
        Operator.LOGICAL_AND,
        Operator.LOGICAL_OR,
    }
)


@dataclass(frozen=True, slots=True)
class _Names:
    """The names that equation text on one entity of a draft can use."""

    draft: "ModelDraft"
    owner: UUID
    # The keys that the entity does not declare, with the UUIDs reserved for
    # them; an equation of the call must define each one (D44).
    new: dict[str, UUID] = field(default_factory=dict)

    @property
    def units(self) -> UnitSystem:
        """The unit system of the draft's Model."""
        return self.draft._base.unit_system

    def value(self, path: tuple[str, ...]) -> "ValueHandle | Unknown":
        """Return the handle of the Value of a key, or of an entity code and a key.

        A key that the entity does not declare names a value that an equation
        defines: one of an earlier call, or a new one, kept in ``new``.
        """
        draft = self.draft
        if len(path) == 1:
            return draft._named(self.owner, path[0], new=self.new)
        code, key = path
        owner = draft._owner(self.owner)
        if code in owner.keys:
            raise MissingReferenceError(
                ".".join(path), kind="Value", by="path", where=owner.where
            )
        entity = draft.entity(code=code).id
        found = draft._undeclared.get(entity, key)
        return draft._ref(entity, key) if found is None else Unknown(id=found, key=key)


# The records that ``_find`` selects by UUID, code or name.
_Found = TypeVar("_Found", Entity, Classification)
# The record kinds of the owners of values: Entity and Assembly.
_Owned = TypeVar("_Owned", bound=Entity)

# The word for each kind of Value in the display of a handle.
_VALUE_WORDS = {
    ValueKind.MEASUREMENT: "value",
    ValueKind.FLOW: "flow",
    ValueKind.DATE: "date",
    ValueKind.PROPERTY: "property",
}


@dataclass(frozen=True, slots=True, init=False, eq=False)
class ValueHandle(Symbolic):
    """A Value that a draft declared or found: its UUID, key, kind, owner and units.

    A draft makes handles: ``value``, ``flow``, ``date`` and ``ref`` on an
    entity handle return them. ``owner`` is the UUID of the entity, and
    ``units`` are the declared units, or None for a Value with no Measure;
    ``periods`` are the declared Periods of a Flow, or None when its
    equations give them.
    The display names the kind, key, units and entity, for example
    ``<value land_cost [AUD] on project>``.

    A handle is a value in the Python form of equations (D32): operators and
    the ``rx`` functions build equations from it, such as
    ``noi == coverage * debt_service``, and ``equations(...)`` takes them.
    ``==`` makes an equation, so compare handles by ``id``.
    """

    id: UUID
    key: str
    kind: ValueKind
    owner: UUID
    units: str | None
    periods: tuple[Period, ...] | None
    # The name or code of the owner, for the display only.
    _entity: str = field(repr=False, compare=False)

    def __init__(self) -> None:
        raise TypeError("a draft makes ValueHandles; call value() on an entity handle")

    @classmethod
    def _of(cls, value: Value, *, owner: "_Owner", units: str | None) -> "ValueHandle":
        """Return the handle of a Value of ``owner`` in a draft."""
        handle = object.__new__(cls)
        fields = {
            "id": value.id,
            "key": value.key,
            "kind": value.kind,
            "owner": owner.record.id,
            "units": units,
            "periods": _periods(value),
            "_entity": owner.label,
        }
        for name, item in fields.items():
            object.__setattr__(handle, name, item)
        return handle

    def __repr__(self) -> str:
        units = "" if self.units is None else f" [{self.units}]"
        word = _VALUE_WORDS.get(self.kind, "value")
        return f"<{word} {self.key}{units} on {self._entity}>"

    def _as_term(self) -> Term:
        return terms.reference(self, name=self.key)


@dataclass(slots=True, eq=False)
class _Owner:
    """The working state of one Entity or Assembly in a draft."""

    record: Entity
    values: list[Value]
    changed: bool = False
    keys: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.keys = {value.key: index for index, value in enumerate(self.values)}

    @property
    def path(self) -> str:
        """The code of the record, or its UUID when it has no code."""
        return self.record.code or str(self.record.id)

    @property
    def label(self) -> str:
        """The name of the record for a display, or its code or UUID."""
        return self.record.name or self.path

    @property
    def where(self) -> str:
        """Name the record in an error: its kind, and its code or UUID."""
        return f"{type(self.record).__name__} {self.path}"


class EntityHandle:
    """An Entity or Assembly in a draft, which declares its values and equations.

    A draft makes handles: ``draft.add_entity(...)`` and ``draft.entity(...)``
    return them. Declarations are checked when they are made; ``commit()`` on
    the draft validates them again with the whole revision. The display names
    the kind, code and name, for example ``<entity project "Project">``.
    """

    __slots__ = ("_draft", "_id")
    _draft: "ModelDraft"
    _id: UUID

    def __init__(self) -> None:
        raise TypeError("a draft makes EntityHandles; call add_entity() or entity()")

    @classmethod
    def _of(cls, draft: "ModelDraft", id: UUID) -> "EntityHandle":
        """Return the handle of the Entity or Assembly ``id`` of ``draft``."""
        handle = cls.__new__(cls)
        handle._draft = draft
        handle._id = id
        return handle

    @property
    def id(self) -> UUID:
        """The UUID of the Entity or Assembly."""
        return self._id

    @property
    def code(self) -> str | None:
        """The code of the Entity or Assembly."""
        return self._draft._owner(self._id).record.code

    def __repr__(self) -> str:
        record = self._draft._owner(self._id).record
        word = "assembly" if isinstance(record, Assembly) else "entity"
        name = "" if record.name is None else f" {record.name!r}"
        return f"<{word} {record.code or self._id}{name}>"

    def value(
        self,
        *,
        key: str,
        units: str,
        description: str | None = None,
    ) -> ValueHandle:
        """Declare a measurement Value with its key and units, and return its handle.

        The Value has no recorded quantity: a Specification fixes it or a solve
        finds it. The key must be a Python identifier that is not a keyword or a
        reserved word (``rx``, ``rk``, ``NEVER``). A key that the entity already
        has raises ContractError; unknown units raise UnitError.
        """
        return self._draft._add_value(
            self._id,
            key=key,
            units=units,
            kind=ValueKind.MEASUREMENT,
            description=description,
        )

    def flow(
        self,
        *,
        key: str,
        units: str,
        periods: Iterable[Period] | None = None,
        description: str | None = None,
    ) -> ValueHandle:
        """Declare a Flow Value with its key and units, and return its handle.

        A Flow made from amounts, by a profile or an event, is declared with
        its ``periods``: it then has one unresolved Movement in each Period.
        Without ``periods``, the Flow takes its Periods from the equations that
        define it. The key and units follow the rules of ``value``.
        """
        return self._draft._add_value(
            self._id,
            key=key,
            units=units,
            kind=ValueKind.FLOW,
            description=description,
            periods=periods,
        )

    def date(
        self,
        *,
        key: str,
        description: str | None = None,
    ) -> ValueHandle:
        """Declare a date Value with its key, and return its handle.

        A date has no units. Its content is a calendar date or
        ``rk.duration.NEVER``; the Value has none recorded, so a Specification
        fixes it or a solve finds it. The key follows the rules of ``value``.
        """
        return self._draft._add_value(
            self._id,
            key=key,
            units=None,
            kind=ValueKind.DATE,
            description=description,
        )

    def ref(self, *, key: str) -> ValueHandle:
        """Return the handle of a Value of this entity, declared now or before.

        A missing key raises MissingReferenceError with the nearest keys.
        """
        return self._draft._ref(self._id, require_text(key, "key"))

    def equations(self, *equations: str | Term | Expression) -> None:
        """Add one equation or several to the entity's default Formulation.

        An equation is equation text, such as ``"noi = coverage * debt_service"``,
        a Boolean Term of the Python form, such as
        ``noi == coverage * debt_service``, or a Boolean Expression record. It
        is an equality or a bound. Text names the keys of this entity, and
        ``code.key`` names a key of another entity; each name must be declared
        in the draft or in its Model. Text that does not make an equation
        raises EquationError with the position of the part that fails, and no
        equation of the call is added. The default Formulation is the root
        Formulation whose code is the entity's code; the draft makes it when it
        is absent. The draft adds the Function record of each equation
        function that an equation calls to the Model's definitions.
        """
        draft = self._draft
        records = draft._equations_of(self._id, equations)
        formulation = draft._mathematics.default(draft._owner(self._id).path)
        draft._mathematics.add(formulation=formulation, expressions=records)

    def add_formulation(
        self,
        *,
        name: str,
        description: str | None = None,
    ) -> FormulationHandle:
        """Declare a named Formulation of the entity, and return its handle.

        A Formulation groups equations, such as the "Funding" equations, for
        displays and traces. It changes nothing in a solve, and the values stay
        on the entity. ``equations(...)`` on the handle adds to it, as on the
        entity. The named Formulation is a child of the entity's default
        Formulation. A name that the entity's Formulations have raises
        ContractError with the code UNIQUE; ``formulation(name=)`` finds it.
        """
        draft = self._draft
        draft._require_open()
        optional_text(description, "description")
        owner = draft._owner(self._id)
        identity = draft._mathematics.add_named(
            path=owner.path,
            name=require_text(name, "name"),
            description=description,
            where=owner.where,
        )
        return FormulationHandle._of(
            draft, id=identity, name=name, owner=owner.record.id, entity=owner.label
        )

    def formulation(self, *, name: str) -> FormulationHandle:
        """Return the handle of a named Formulation of the entity, made now or before.

        A missing name raises MissingReferenceError with the nearest names.
        """
        owner = self._draft._owner(self._id)
        identity = self._draft._mathematics.named(
            path=owner.path, name=require_text(name, "name"), where=owner.where
        )
        return FormulationHandle._of(
            self._draft,
            id=identity,
            name=name,
            owner=owner.record.id,
            entity=owner.label,
        )


class ModelDraft:
    """The changes for the next revision of one Model; ``commit()`` returns it.

    ``model.edit()`` makes a draft. A draft adds definitions, entities,
    assemblies, relationships, values and equations, and refers to entities by
    handle, code or UUID. It checks each call when it is made and validates the
    complete revision once, in ``commit()``. A committed draft takes no further
    changes; edit the new revision instead.
    """

    __slots__ = (
        "_base",
        "_name",
        "_description",
        "_taxonomies",
        "_measures",
        "_functions",
        "_owners",
        "_relationships",
        "_mathematics",
        "_undeclared",
        "_changed",
        "_known",
        "_handles",
        "_committed",
    )
    _base: "Model"
    _name: str | None
    _description: str | None
    _taxonomies: list[Taxonomy]
    _measures: list[Measure]
    _functions: list[Function]
    _owners: dict[UUID, _Owner]
    _relationships: list[Relationship]
    # The Formulations, and the Formulations and equations that the draft adds.
    _mathematics: Mathematics
    # The values that equations define and no call declares (D44).
    _undeclared: Undeclared
    # The parts of the revision that the draft changed.
    _changed: set[str]
    # The UUIDs of the Values and Movements that equations can reference.
    _known: set[UUID]
    _handles: dict[UUID, EntityHandle]
    _committed: bool

    def __init__(self) -> None:
        raise TypeError("call model.edit() to make a ModelDraft")

    @classmethod
    def _start(
        cls,
        model: "Model",
        *,
        name: str | None,
        description: str | None,
    ) -> "ModelDraft":
        optional_text(name, "name", empty=False)
        optional_text(description, "description")
        draft = cls.__new__(cls)
        definitions = model.definitions or Definitions()
        system = model.system or System()
        draft._base = model
        draft._name = name
        draft._description = description
        draft._taxonomies = list(definitions.taxonomies or ())
        draft._measures = list(definitions.measures or ())
        draft._functions = list(definitions.functions or ())
        draft._owners = {
            record.id: _Owner(record, list(_values(record)))
            for record in (*(system.entities or ()), *(system.assemblies or ()))
        }
        draft._relationships = list(system.relationships or ())
        draft._mathematics = Mathematics(
            roots=system.formulations or (), identify=draft._identify
        )
        draft._undeclared = Undeclared()
        draft._changed = set()
        draft._known = {
            identity
            for identity, record in model._index.records.items()
            if isinstance(record, (Value, Movement))
        }
        draft._handles = {}
        draft._committed = False
        return draft

    def __repr__(self) -> str:
        return (
            f"ModelDraft(model={self._base.id!r}, entities={len(self._owners)}, "
            f"committed={self._committed})"
        )

    @property
    def model(self) -> "Model":
        """The revision that this draft changes; it does not change."""
        return self._base

    # Definitions.

    def add_measure(
        self,
        *,
        code: str,
        name: str,
        units: str,
        definition: str | None = None,
    ) -> Measure:
        """Declare a Measure with its code, name and canonical units, and return it.

        ``value`` and ``flow`` find or declare a Measure for their units, so a
        Measure is declared only to give it a code, a name or a definition. A
        code that is in use raises ContractError.
        """
        self._require_open()
        require_code(code, "code")
        require_text(name, "name")
        optional_text(definition, "definition")
        self._base.unit_system.validate_units(require_text(units, "units"))
        if any(item.code == code for item in self._measures):
            raise _duplicate("Measure", "code", code)
        measure = Measure(
            id=self._identify("measure", code),
            code=code,
            name=name,
            units=units,
            definition=UNSET if definition is None else definition,
        )
        self._measures.append(measure)
        self._changed.add("measures")
        return measure

    def add_classification(
        self,
        *,
        code: str,
        name: str | None = None,
        parent: str | UUID | None = None,
        taxonomy: str = ENTITY_TAXONOMY,
    ) -> Classification:
        """Declare a Classification in a Taxonomy, and return it.

        ``parent`` is the code or UUID of a Classification in the same Taxonomy;
        by default, the Taxonomy's root. A missing Taxonomy is made, with a root
        Classification of the same code. ``name`` defaults to the code. A code
        that the Taxonomy has raises ContractError.
        """
        self._require_open()
        require_code(code, "code")
        optional_text(name, "name", empty=False)
        index = self._taxonomy(require_code(taxonomy, "taxonomy"))
        records = self._taxonomies[index].classifications
        if any(item.code == code for item in records):
            raise _duplicate("Classification", "code", code)
        if parent is None:
            above = next(item.id for item in records if item.parent is None)
        else:
            above = _find(
                records,
                parent,
                kind="Classification",
                where=f"Taxonomy {taxonomy}",
            ).id
        return self._classify(index, code, name=name, parent=above)

    # Entities, assemblies and relationships.

    def add_entity(
        self,
        *,
        code: str,
        classification: str | UUID | None = None,
        name: str | None = None,
    ) -> EntityHandle:
        """Declare an Entity with its code, and return its handle.

        ``classification`` is a Classification code or UUID. A code that no
        Taxonomy has is declared in the ``entity`` Taxonomy; a code that several
        Taxonomies have raises AmbiguousReferenceError. An Entity or Assembly
        code that is in use raises ContractError.
        """
        self._require_open()
        return self._add_owner(
            self._new_owner(Entity, code=code, classification=classification, name=name)
        )

    def add_assembly(
        self,
        *,
        code: str,
        classification: str | UUID | None = None,
        name: str | None = None,
        entities: Sequence["str | UUID | EntityHandle"] = (),
    ) -> EntityHandle:
        """Declare an Assembly of entities, and return its handle.

        ``entities`` gives the members by code, UUID or handle. The other
        arguments are those of ``add_entity``. An Assembly declares values and
        equations like an Entity.
        """
        self._require_open()
        members = tuple(dict.fromkeys(self._entity_id(item) for item in entities))
        record = self._new_owner(
            Assembly, code=code, classification=classification, name=name
        )
        return self._add_owner(record.replace(entities=members) if members else record)

    def add_relationship(
        self,
        *,
        source: "str | UUID | EntityHandle",
        target: "str | UUID | EntityHandle",
        classification: str | UUID,
    ) -> Relationship:
        """Declare a directed Relationship between two entities, and return it.

        ``source`` and ``target`` are entities or assemblies by code, UUID or
        handle. ``classification`` names the Relationship, such as
        ``"contains"``; a code that no Taxonomy has is declared in the
        ``relationship`` Taxonomy.
        """
        self._require_open()
        start, end = self._entity_id(source), self._entity_id(target)
        kind = self._classification(classification, RELATIONSHIP_TAXONOMY)
        relationship = Relationship(
            id=self._identify(
                "relationship",
                self._owner(start).path,
                str(kind),
                self._owner(end).path,
            ),
            source=start,
            target=end,
            classification=kind,
        )
        self._relationships.append(relationship)
        self._changed.add("relationships")
        return relationship

    def entity(
        self,
        *,
        id: UUID | None = None,
        code: str | None = None,
        name: str | None = None,
    ) -> EntityHandle:
        """Return the handle of the one Entity or Assembly with this UUID, code or name.

        Give exactly one selector. The draft finds entities of its Model and
        entities that it declared. No match raises MissingReferenceError with the
        nearest codes or names; several matches raise AmbiguousReferenceError.
        """
        if sum(value is not None for value in (id, code, name)) != 1:
            raise TypeError("entity takes exactly one of id, code or name")
        if id is not None:
            return self._handle(self._owner(id).record.id)
        by, text = ("code", code) if code is not None else ("name", name)
        text = require_text(text, by)
        records = [owner.record for owner in self._owners.values()]
        return self._handle(
            _find(records, text, kind="Entity", where="ModelDraft", by=by).id
        )

    # Commit.

    def commit(self) -> "Model":
        """Validate the complete revision once and return it.

        The new revision has a new UUID, and ``previous`` is the UUID of the
        draft's Model. A failure raises ValidationError, or RevisionConflictError
        for a draft with no change, and leaves the draft open to correct it.

        A value that equations define and no call declares takes its kind and
        units from its equations (D44); one whose units cannot be worked out
        raises ValidationError with the code ``semantic.units``.
        """
        self._require_open()
        base = self._base
        measures = list(self._measures)
        inferred = self._inferred(measures)
        definitions: Definitions | Unset = UNSET
        added = len(measures) > len(self._measures)
        if self._changed & {"taxonomies", "measures", "functions"} or added:
            definitions = (base.definitions or Definitions()).replace(
                taxonomies=tuple(self._taxonomies) if self._taxonomies else UNSET,
                measures=tuple(measures) if measures else UNSET,
                functions=tuple(self._functions) if self._functions else UNSET,
            )
        system: System | Unset = UNSET
        if self._changed & {"owners", "relationships"} or self._mathematics.changed:
            owners = [
                _built(owner, inferred.get(owner.record.id, ()))
                for owner in self._owners.values()
            ]
            entities = tuple(r for r in owners if not isinstance(r, Assembly))
            assemblies = tuple(r for r in owners if isinstance(r, Assembly))
            formulations = self._mathematics.formulations()
            system = (base.system or System()).replace(
                entities=entities or UNSET,
                assemblies=assemblies or UNSET,
                relationships=tuple(self._relationships) or UNSET,
                formulations=formulations or UNSET,
            )
        metadata = base.metadata.replace(
            id=uuid4(),
            previous=base.id,
            name=UNSET if self._name is None else self._name,
            description=UNSET if self._description is None else self._description,
        )
        revision = base.revise(
            Update(
                definitions=definitions,
                system=system,
                metadata=metadata,
            )
        )
        self._committed = True
        return revision

    # Private helpers for handles.

    def _require_open(self) -> None:
        if self._committed:
            raise RevisionConflictError(
                "this draft is committed; call edit() on the new revision"
            )

    def _identify(self, *parts: str) -> UUID:
        namespace = self._base._namespace
        return uuid4() if namespace is None else identify(namespace, *parts)

    def _owner(self, id: UUID) -> _Owner:
        owner = self._owners.get(id)
        if owner is None:
            raise MissingReferenceError(id, kind="Entity", where="ModelDraft")
        return owner

    def _handle(self, id: UUID) -> EntityHandle:
        handle = self._handles.get(id)
        if handle is None:
            handle = self._handles[id] = EntityHandle._of(self, id)
        return handle

    def _entity_id(self, item: "str | UUID | EntityHandle") -> UUID:
        if isinstance(item, EntityHandle):
            if item._draft is not self:
                raise ContractError(
                    f"the handle of {item.code or item.id} belongs to another draft",
                    targets=(item.id,),
                )
            return item.id
        if isinstance(item, UUID):
            return self._owner(item).record.id
        return self.entity(code=require_text(item, "entity")).id

    def _new_owner(
        self,
        kind: type[_Owned],
        *,
        code: str,
        classification: str | UUID | None,
        name: str | None,
    ) -> _Owned:
        """Check the fields of a new Entity or Assembly, and return its record."""
        require_code(code, "code")
        optional_text(name, "name", empty=False)
        if any(owner.record.code == code for owner in self._owners.values()):
            raise _duplicate("Entity", "code", code)
        return kind(
            id=self._identify("entity", code),
            code=code,
            name=UNSET if name is None else name,
            classification=UNSET
            if classification is None
            else self._classification(classification, ENTITY_TAXONOMY),
        )

    def _add_owner(self, record: Entity) -> EntityHandle:
        self._owners[record.id] = _Owner(record, [], changed=True)
        self._changed.add("owners")
        return self._handle(record.id)

    def _add_value(
        self,
        owner_id: UUID,
        *,
        key: str,
        units: str | None,
        kind: ValueKind,
        description: str | None,
        periods: Iterable[Period] | None = None,
    ) -> ValueHandle:
        self._require_open()
        owner = self._owner(owner_id)
        _require_key(key)
        if units is not None:
            self._base.unit_system.validate_units(require_text(units, "units"))
        optional_text(description, "description")
        if key in owner.keys:
            raise _duplicate("Value", "key", key, where=owner.where)
        flow: Flow | Unset = UNSET
        if periods is not None:
            items = tuple(periods)
            if not all(isinstance(item, Period) for item in items):
                raise TypeError("periods must be Periods")
            assert units is not None
            flow = Flow(
                units=units,
                movements=[
                    Movement(
                        id=self._identify(
                            "movement", owner.path, key, item.start.isoformat()
                        ),
                        period=item,
                    )
                    for item in items
                ],
            )
        value = Value(
            id=self._undeclared.declare(owner_id, key)
            or self._identify("value", owner.path, key),
            key=key,
            kind=kind,
            measure=UNSET if units is None else self._measure(units).id,
            description=UNSET if description is None else description,
            flow=flow,
        )
        owner.keys[key] = len(owner.values)
        owner.values.append(value)
        owner.changed = True
        self._changed.add("owners")
        self._known.add(value.id)
        if isinstance(flow, Flow):
            self._known.update(movement.id for movement in flow.movements)
        return ValueHandle._of(value, owner=owner, units=units)

    def _ref(self, owner_id: UUID, key: str) -> ValueHandle:
        owner = self._owner(owner_id)
        index = owner.keys.get(key)
        if index is None:
            raise MissingReferenceError(
                key,
                kind="Value",
                by="key",
                where=owner.where,
                candidates=get_close_matches(key, sorted(owner.keys), n=3),
            )
        value = owner.values[index]
        units = None
        if value.measure is not None:
            units = next(
                item.units for item in self._measures if item.id == value.measure
            )
        return ValueHandle._of(value, owner=owner, units=units)

    def _add_to(
        self,
        formulation: UUID,
        *,
        owner: UUID,
        equations: Sequence[str | Term | Expression],
    ) -> None:
        """Add the equations of an entity to one of its Formulations."""
        records = self._equations_of(owner, equations)
        self._mathematics.add(formulation=formulation, expressions=records)

    def _equations_of(
        self,
        owner_id: UUID,
        equations: Sequence[str | Term | Expression],
    ) -> list[Expression]:
        """Return the checked records of the equations of one entity.

        The draft adds the Function record of each equation function that they
        call; it adds no equation.
        """
        self._require_open()
        owner = self._owner(owner_id)
        if not equations:
            raise TypeError("equations takes at least one equation")
        names = _Names(self, owner_id)
        records = [_equation(item, names=names) for item in equations]
        known = self._known | set(names.new.values())
        for equation in records:
            for target in _targets(equation.to_data()):
                if target not in known:
                    raise MissingReferenceError(target, kind="Value", where=owner.where)
        self._undeclared.add(
            owner=owner_id,
            where=owner.where,
            new=names.new,
            equations=records,
            texts=[item for item in equations if isinstance(item, str)],
            candidates=[*owner.keys, *self._undeclared.keys(owner_id)],
        )
        self._known.update(names.new.values())
        for equation in records:
            self._add_functions(equation.to_data())
        return records

    def _named(
        self,
        owner_id: UUID,
        key: str,
        *,
        new: dict[str, UUID],
    ) -> "ValueHandle | Unknown":
        """Return what a key of equation text names on one entity.

        A declared key names the handle of its Value, and an undeclared key the
        value that an equation defines; another key gets a new UUID in ``new``.
        """
        owner = self._owner(owner_id)
        if key in owner.keys:
            return self._ref(owner_id, key)
        found = self._undeclared.get(owner_id, key) or new.get(key)
        if found is None:
            found = new[key] = self._identify("value", owner.path, key)
        return Unknown(id=found, key=key)

    def _inferred(self, measures: list[Measure]) -> dict[UUID, list[Value]]:
        """Return the Values that equations define without a declaration, by owner.

        The Measures of their units are added to ``measures``, a copy of the
        draft's, so that a failed commit changes nothing.
        """
        if not self._undeclared:
            return {}
        return self._undeclared.values(
            equations=self._mathematics.expressions(),
            units=self._base.unit_system,
            lookup=known_values(
                (value for owner in self._owners.values() for value in owner.values),
                measures=measures,
            ),
            measure=lambda units: _measure_in(measures, units, self._identify),
            known=[item.units for item in measures],
        )

    def _add_functions(self, data: object) -> None:
        """Add the Function record of each equation function that ``data`` calls."""
        known = {record.id for record in self._functions}
        for identity in _called(data):
            function = functions.get(identity)
            if identity in known or function is None:
                continue
            self._functions.append(function.record())
            known.add(identity)
            self._changed.add("functions")

    def _measure(self, units: str) -> Measure:
        count = len(self._measures)
        measure = _measure_in(self._measures, units, self._identify)
        if len(self._measures) != count:
            self._changed.add("measures")
        return measure

    def _taxonomy(self, code: str) -> int:
        for index, item in enumerate(self._taxonomies):
            if item.code == code:
                return index
        root = Classification(
            id=self._identify("classification", code, code),
            code=code,
            name=code.capitalize(),
        )
        self._taxonomies.append(
            Taxonomy(
                id=self._identify("taxonomy", code),
                code=code,
                name=code.capitalize(),
                classifications=(root,),
            )
        )
        self._changed.add("taxonomies")
        return len(self._taxonomies) - 1

    def _classify(
        self,
        index: int,
        code: str,
        *,
        name: str | None,
        parent: UUID,
    ) -> Classification:
        taxonomy = self._taxonomies[index]
        record = Classification(
            id=self._identify("classification", taxonomy.code, code),
            code=code,
            name=name or code,
            parent=parent,
        )
        self._taxonomies[index] = taxonomy.replace(
            classifications=(*taxonomy.classifications, record)
        )
        self._changed.add("taxonomies")
        return record

    def _classification(self, value: str | UUID, default: str) -> UUID:
        records = [
            item for taxonomy in self._taxonomies for item in taxonomy.classifications
        ]
        if isinstance(value, UUID):
            return _find(records, value, kind="Classification", where="ModelDraft").id
        code = require_code(value, "classification")
        matches = [item for item in records if item.code == code]
        if len(matches) == 1:
            return matches[0].id
        if matches:
            raise AmbiguousReferenceError(
                code,
                kind="Classification",
                by="code",
                where="ModelDraft",
                candidates=[str(item.id) for item in matches],
            )
        index = self._taxonomy(default)
        root = next(
            item.id
            for item in self._taxonomies[index].classifications
            if item.parent is None
        )
        return self._classify(index, code, name=None, parent=root).id


def _periods(value: Value) -> tuple[Period, ...] | None:
    """Return the declared Periods of a Flow Value, or None."""
    movements = () if value.flow is None else value.flow.movements
    periods = tuple(m.period for m in movements if m.period is not None)
    return periods if periods and len(periods) == len(movements) else None


def _values(record: Entity) -> tuple[Value, ...]:
    characteristics = record.characteristics
    return () if characteristics is None else characteristics.values or ()


def _built(owner: _Owner, inferred: Sequence[Value]) -> Entity:
    """Return the record of an owner, with the values that the draft added."""
    values = (*owner.values, *inferred)
    if not (owner.changed or inferred) or not values:
        return owner.record
    characteristics = owner.record.characteristics or Characteristics()
    return owner.record.replace(characteristics=characteristics.replace(values=values))


def _measure_in(
    measures: list[Measure],
    units: str,
    identify: Callable[..., UUID],
) -> Measure:
    """Return the Measure with these units, and add one when ``measures`` has none.

    A new Measure's code is the units, with a number when that code is in use.
    """
    for item in measures:
        if item.units == units:
            return item
    codes = {item.code for item in measures}
    code, number = units, 1
    while code in codes:
        number += 1
        code = f"{units} {number}"
    measure = Measure(id=identify("measure", code), code=code, name=units, units=units)
    measures.append(measure)
    return measure


def _require_key(key: object) -> None:
    text = require_text(key, "key")
    if not text.isidentifier() or keyword.iskeyword(text) or text in RESERVED:
        raise ContractError(
            f"key {text!r} must be a Python identifier that is not a keyword "
            "or a reserved word (rx, rk, NEVER)",
            values={"key": text},
        )


def _duplicate(
    kind: str,
    by: str,
    text: str,
    *,
    where: str = "ModelDraft",
) -> ContractError:
    return ContractError(
        f"{kind} {by} {text!r} is already declared in {where}",
        code=Code.UNIQUE,
        values={"kind": kind, by: text, "where": where},
    )


def _find(
    records: Sequence[_Found],
    selector: str | UUID,
    *,
    kind: str,
    where: str,
    by: str = "code",
) -> _Found:
    """Return the one record with this UUID, or with this code or name."""
    if isinstance(selector, UUID):
        for record in records:
            if record.id == selector:
                return record
        raise MissingReferenceError(selector, kind=kind, where=where)
    matches = [record for record in records if getattr(record, by) == selector]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise AmbiguousReferenceError(
            selector,
            kind=kind,
            by=by,
            where=where,
            candidates=[getattr(r, "code", None) or str(r.id) for r in matches],
        )
    names = sorted({getattr(record, by) for record in records} - {None})
    raise MissingReferenceError(
        selector,
        kind=kind,
        by=by,
        where=where,
        candidates=get_close_matches(selector, names, n=3),
    )


def _equation(item: str | Term | Expression, *, names: _Names) -> Expression:
    """Return the record of one equation: its text parsed, or the record given."""
    if isinstance(item, Term):
        item = item.to_expression()
    elif isinstance(item, Symbolic):
        raise TypeError("an equation must be Boolean, such as a == b; not a handle")
    if isinstance(item, str):
        record = equation_text.parse(text=item, names=names)
        if not _relation(record):
            raise EquationError(
                "an equation must be Boolean, such as an equality or a bound",
                code=Code.PREDICATE,
                text=item,
                start=0,
                end=len(item),
            )
        return record
    if not isinstance(item, Expression):
        raise TypeError(
            "each equation must be equation text, a Term or an Expression record"
        )
    if not _relation(item):
        raise ContractError(
            "an equation must be Boolean, such as an equality or a bound",
            code=Code.PREDICATE,
            targets=(item.id,),
        )
    return item


def _relation(expression: Expression) -> bool:
    """Return whether the root of an expression can be Boolean."""
    if expression.kind in (ExpressionKind.BINARY, ExpressionKind.UNARY):
        return expression.operator in _RELATIONS
    return expression.kind in (ExpressionKind.BOOLEAN, ExpressionKind.CALL)


def _called(data: object) -> Iterable[UUID]:
    """Yield the Function UUID of each call in exported Expression data."""
    if isinstance(data, dict):
        if data.get("kind") == "call" and isinstance(data.get("call"), dict):
            yield UUID(data["call"]["function"])
        for child in data.values():
            yield from _called(child)
    elif isinstance(data, list):
        for child in data:
            yield from _called(child)


def _targets(data: object) -> Iterable[UUID]:
    """Yield the UUID of each Reference in exported Expression data."""
    if isinstance(data, dict):
        if data.get("kind") == "reference" and isinstance(data.get("target"), dict):
            yield UUID(data["target"]["target"])
        for child in data.values():
            yield from _targets(child)
    elif isinstance(data, list):
        for child in data:
            yield from _targets(child)


__all__ = ["ModelDraft", "EntityHandle", "ValueHandle"]
