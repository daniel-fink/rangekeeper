"""Explicit recorded-Value reductions, coverage, and immutable results.

These operations neither solve equations nor write quantities into Models.
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum, unique
from types import MappingProxyType
from uuid import UUID
from rangekeeper.model import Entity, Value, Quantity, ValueKind
from rangekeeper.shared.units import UnitSystem, default_units
from rangekeeper.model.system.errors import AggregationError, SelectionError
from rangekeeper.model.system.hierarchy import Hierarchy
from rangekeeper.model.system.selection import ValueSelector, _recorded_quantity


@unique
class CoverageStatus(Enum):
    EMPTY = "empty"
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True)
class Coverage:
    """Selected, measured and missing owner UUIDs; not population certification."""

    selected: tuple[UUID, ...]
    measured: tuple[UUID, ...]
    missing: tuple[UUID, ...]

    def __post_init__(self) -> None:
        for name in ("selected", "measured", "missing"):
            items = tuple(getattr(self, name))
            if any(not isinstance(id, UUID) for id in items) or len(set(items)) != len(
                items
            ):
                raise AggregationError("coverage must contain unique UUIDs")
            object.__setattr__(self, name, items)
        if set(self.measured) & set(self.missing) or set(self.selected) != set(
            self.measured
        ) | set(self.missing):
            raise AggregationError(
                "measured and missing must partition selected contributors"
            )

    @property
    def complete(self) -> bool:
        """Whether a nonempty selected population is fully measured."""
        return bool(self.selected) and not self.missing

    @property
    def status(self) -> CoverageStatus:
        return (
            CoverageStatus.EMPTY
            if not self.selected
            else CoverageStatus.COMPLETE if self.complete else CoverageStatus.INCOMPLETE
        )


@dataclass(frozen=True)
class AggregateEntry:
    """Available reduction and its contributor coverage."""

    available: Quantity | None
    coverage: Coverage

    def __post_init__(self) -> None:
        if not isinstance(self.coverage, Coverage):
            raise TypeError("coverage must be Coverage")
        if self.available is not None and not isinstance(self.available, Quantity):
            raise TypeError("available must be a schema Quantity or None")
        if bool(self.coverage.measured) != (self.available is not None):
            raise AggregationError("measured coverage and available result must agree")


@dataclass(frozen=True)
class Aggregation:
    """Immutable entries and selected Value identities, pinned to a Hierarchy."""

    hierarchy: Hierarchy
    entries: Mapping[UUID, AggregateEntry]
    value_ids: Mapping[UUID, UUID]
    require_complete: bool

    def __post_init__(self) -> None:
        if not isinstance(self.hierarchy, Hierarchy):
            raise TypeError("hierarchy must be a Hierarchy")
        if type(self.require_complete) is not bool:
            raise TypeError("require_complete must be bool")
        order = self.hierarchy.preorder()
        entries, value_ids = dict(self.entries), dict(self.value_ids)
        if set(entries) != set(order):
            raise AggregationError(
                "aggregation entries must exactly match the hierarchy"
            )
        # Each subtree is a contiguous preorder interval; no repeated subtree walks.
        positions = {uid: position for position, uid in enumerate(order)}
        ends: dict[UUID, int] = {}
        for uid in self.hierarchy.postorder():
            children = self.hierarchy.children(uid)
            ends[uid] = ends[children[-1]] if children else positions[uid] + 1
        for uid, entry in entries.items():
            if not isinstance(entry, AggregateEntry):
                raise TypeError("entries must contain AggregateEntry objects")
            if any(
                owner not in positions
                or not positions[uid] <= positions[owner] < ends[uid]
                for owner in entry.coverage.selected
            ):
                raise AggregationError(
                    "coverage must belong to its corresponding subtree"
                )
            if any(owner not in value_ids for owner in entry.coverage.measured):
                raise AggregationError(
                    "measured contributors require selected Value identities"
                )
        selected = set(entries[self.hierarchy.root].coverage.selected)
        for owner, value_id in value_ids.items():
            self.hierarchy.view.entity(owner)
            self.hierarchy.view.model.value(value_id)
            if (
                owner not in selected
                or self.hierarchy.view.model.owner_of(value_id) != owner
            ):
                raise AggregationError(
                    "value_ids must record selected owners' local Values"
                )
        object.__setattr__(self, "entries", MappingProxyType(entries))
        object.__setattr__(self, "value_ids", MappingProxyType(value_ids))

    @property
    def root_value(self) -> Quantity | None:
        return self.value(self.hierarchy.root)

    def value(self, id: UUID) -> Quantity | None:
        self.hierarchy.view.entity(id)
        entry = self.entries[id]
        return (
            None
            if self.require_complete and not entry.coverage.complete
            else entry.available
        )

    def __getitem__(self, id: UUID) -> Quantity | None:
        return self.value(id)

    def coverage(self, id: UUID) -> Coverage:
        self.hierarchy.view.entity(id)
        return self.entries[id].coverage

    def available_value(self, id: UUID) -> Quantity | None:
        self.hierarchy.view.entity(id)
        return self.entries[id].available


def _reduce_quantities(values, reducer, units, unit_system):
    if not values:
        return None
    result = reducer(values)
    if not isinstance(result, Quantity):
        raise TypeError("reducer must return a schema Quantity")
    return unit_system.convert(result, to=units)


@dataclass(frozen=True)
class _Population:
    """Raw quantities, contributor coverage and selected identities for one scope."""

    quantities: tuple[Quantity, ...]
    coverage: Coverage
    value_ids: Mapping[UUID, UUID]


def _collect_quantities(
    selections: Iterable[tuple[Entity, Value | None]],
    units: str,
    unit_system: UnitSystem,
) -> _Population:
    """Collect canonical selections; callers retain eligibility and reduction policy."""
    selected, measured, missing, quantities, value_ids = [], [], [], [], {}
    for entity, value in selections:
        selected.append(entity.id)
        if value is not None:
            value_ids[entity.id] = value.id
        quantity = _recorded_quantity(value, units, unit_system)
        if quantity is None:
            missing.append(entity.id)
        else:
            measured.append(entity.id)
            quantities.append(quantity)
    return _Population(
        tuple(quantities),
        Coverage(tuple(selected), tuple(measured), tuple(missing)),
        MappingProxyType(value_ids),
    )


def _combine_coverage(parts: tuple[Coverage, ...]) -> Coverage:
    return Coverage(
        tuple(uid for part in parts for uid in part.selected),
        tuple(uid for part in parts for uid in part.measured),
        tuple(uid for part in parts for uid in part.missing),
    )


@dataclass(frozen=True, kw_only=True)
class Reduction:
    """Choose one Value per eligible Entity, normalize units, then combine explicitly.

    The default includes every selected Entity with complete coverage required.
    Supply contributors to select leaves or a classification when parent values
    represent totals. Nothing infers physical population or additive semantics.
    Callbacks must be pure; all records supplied to them are immutable.
    """

    select: ValueSelector
    reducer: Callable[[tuple[Quantity, ...]], Quantity]
    units: str
    contributors: Callable[[Entity], bool] | None = None
    require_complete: bool = True
    unit_system: UnitSystem = default_units

    def __post_init__(self) -> None:
        if not callable(self.select) or not callable(self.reducer):
            raise TypeError("select and reducer must be callable")
        if self.contributors is not None and not callable(self.contributors):
            raise TypeError("contributors must be callable")
        if not isinstance(self.require_complete, bool):
            raise TypeError("require_complete must be a bool")
        if not isinstance(self.unit_system, UnitSystem):
            raise TypeError("unit_system must be a UnitSystem")
        self.unit_system.validate_units(self.units)

    def execute(self, hierarchy: Hierarchy) -> Aggregation:
        """Return a detached derived result; never revise, persist, or execute a Model.

        Selectors must return a Value actually owned by the supplied Entity in this
        revision. That rejects stale, cross-owner and Formulation-local shortcuts.
        Raw contributors are combined at each subtree so means remain correctly
        weighted. Missing keys and unresolved quantities count as missing, not zero.
        """
        if not isinstance(hierarchy, Hierarchy):
            raise TypeError("hierarchy must be a Hierarchy")
        raw: dict[UUID, tuple[Quantity, ...]] = {}
        entries: dict[UUID, AggregateEntry] = {}
        value_ids: dict[UUID, UUID] = {}
        for id in hierarchy.postorder():
            own = self._contribution(hierarchy.view.model, hierarchy.view.entity(id))
            value_ids.update(own.value_ids)
            children = hierarchy.children(id)
            raw[id] = (*own.quantities, *(q for child in children for q in raw[child]))
            coverage = _combine_coverage(
                (own.coverage, *(entries[child].coverage for child in children))
            )
            entries[id] = AggregateEntry(
                _reduce_quantities(raw[id], self.reducer, self.units, self.unit_system),
                coverage,
            )
        return Aggregation(hierarchy, entries, value_ids, self.require_complete)

    def _contribution(self, model, entity) -> _Population:
        eligible = True if self.contributors is None else self.contributors(entity)
        if not isinstance(eligible, bool):
            raise TypeError("contributors must return bool")
        if not eligible:
            return _collect_quantities((), self.units, self.unit_system)
        selected = self.select(model, entity)
        if selected is not None:
            if not isinstance(selected, Value):
                raise TypeError("select must return a schema Value or None")
            canonical = model.value(selected.id)
            if model.owner_of(selected.id) != entity.id or canonical != selected:
                raise SelectionError(
                    f"selector returned a stale or nonlocal Value {selected.id} for {entity.id}"
                )
            if selected.kind is not ValueKind.MEASUREMENT:
                raise AggregationError("only scalar Measurement Values are supported")
        return _collect_quantities(((entity, selected),), self.units, self.unit_system)


__all__ = ["Aggregation", "AggregateEntry", "Coverage", "CoverageStatus", "Reduction"]
