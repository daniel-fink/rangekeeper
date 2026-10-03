"""Explicit recorded-Value reductions, coverage, and immutable results.

These operations neither solve equations nor write quantities into Models.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from uuid import UUID
from ..model import Entity, Value, Quantity
from ..units import UnitSystem, default_units
from .errors import AggregationError, SelectionError
from .hierarchy import Hierarchy
from .selection import ValueSelector
from .reducers import sum_quantities


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
    def status(self) -> str:
        return (
            "empty"
            if not self.selected
            else "complete" if self.complete else "incomplete"
        )


@dataclass(frozen=True)
class Aggregation:
    """One result per selected Entity, pinned through its immutable hierarchy.

    value_ids records actual owner-to-Value choices, including unresolved Values.
    Missing keys have no Value ID. Outputs are schema Quantities, never live Pint
    objects; no mutable solver or Model state is retained.
    """

    hierarchy: Hierarchy
    _values: Mapping[UUID, Quantity | None]
    _coverage: Mapping[UUID, Coverage]
    _available: Mapping[UUID, Quantity | None]
    value_ids: Mapping[UUID, UUID]
    _is_sum: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.hierarchy, Hierarchy):
            raise TypeError("hierarchy must be a Hierarchy")
        ids = set(self.hierarchy.preorder())
        for name in ("_values", "_coverage", "_available"):
            items = dict(getattr(self, name))
            if set(items) != ids:
                raise AggregationError(
                    "aggregation entries must exactly match the hierarchy"
                )
            if name == "_coverage":
                if any(not isinstance(item, Coverage) for item in items.values()):
                    raise TypeError("coverage entries must be Coverage objects")
            elif any(
                item is not None and not isinstance(item, Quantity)
                for item in items.values()
            ):
                raise TypeError("result entries must be schema Quantities or None")
            object.__setattr__(self, name, MappingProxyType(items))
        for owner, value_id in self.value_ids.items():
            self.hierarchy.view.entity(owner)
            self.hierarchy.view.model.value(value_id)
            if self.hierarchy.view.model.owner_of(value_id) != owner:
                raise AggregationError(
                    "value_ids must record selected owners' local Values"
                )
        object.__setattr__(self, "value_ids", MappingProxyType(dict(self.value_ids)))

    @property
    def root_value(self) -> Quantity | None:
        """The result at the sole root, subject to the reduction's coverage policy."""
        return self.value(self.hierarchy.root)

    def value(self, id: UUID) -> Quantity | None:
        """Resolve a result by selected Entity UUID; no code/name fallback."""
        self.hierarchy.view.entity(id)
        return self._values[id]

    def __getitem__(self, id: UUID) -> Quantity | None:
        return self.value(id)

    def coverage(self, id: UUID) -> Coverage:
        """Report actual selected contributors below and including this Entity."""
        self.hierarchy.view.entity(id)
        return self._coverage[id]

    def available_value(self, id: UUID) -> Quantity | None:
        """Reduce measured contributors even when complete coverage is required."""
        self.hierarchy.view.entity(id)
        return self._available[id]

    def known_subtotal(self, id: UUID) -> Quantity | None:
        """Return available sum; this interpretation applies only to sum_quantities."""
        if not self._is_sum:
            raise AggregationError("known_subtotal requires sum_quantities")
        return self.available_value(id)


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
        self.unit_system.compatible(self.units, self.units)

    def execute(self, hierarchy: Hierarchy) -> Aggregation:
        """Return a detached derived result; never revise, persist, or execute a Model.

        Selectors must return a Value actually owned by the supplied Entity in this
        revision. That rejects stale, cross-owner and Formulation-local shortcuts.
        Raw contributors are combined at each subtree so means remain correctly
        weighted. Missing keys and unresolved quantities count as missing, not zero.
        """
        if not isinstance(hierarchy, Hierarchy):
            raise TypeError("hierarchy must be a Hierarchy")
        model = hierarchy.view.model
        raw: dict[UUID, tuple[Quantity, ...]] = {}
        coverage: dict[UUID, Coverage] = {}
        available: dict[UUID, Quantity | None] = {}
        results: dict[UUID, Quantity | None] = {}
        value_ids: dict[UUID, UUID] = {}
        for id in hierarchy.postorder():
            entity = hierarchy.view.entity(id)
            eligible = True if self.contributors is None else self.contributors(entity)
            if not isinstance(eligible, bool):
                raise TypeError("contributors must return bool")
            selected = self.select(model, entity) if eligible else None
            own = None
            if selected is not None:
                if not isinstance(selected, Value):
                    raise TypeError("select must return a schema Value or None")
                canonical = model.value(selected.id)
                if (
                    model.owner_of(selected.id) != id
                    or canonical.to_data() != selected.to_data()
                ):
                    raise SelectionError(
                        f"selector returned a stale or nonlocal Value {selected.id} for {id}"
                    )
                value_ids[id] = selected.id
                if selected.kind != "measurement":
                    raise AggregationError(
                        "only scalar Measurement Values are supported"
                    )
                if selected.quantity is not None:
                    own = self.unit_system.convert(selected.quantity, to=self.units)
            selected_ids = [id] if eligible else []
            measured_ids = [id] if own is not None else []
            missing_ids = [id] if eligible and own is None else []
            values = [] if own is None else [own]
            for child in hierarchy.children(id):
                values.extend(raw[child])
                selected_ids.extend(coverage[child].selected)
                measured_ids.extend(coverage[child].measured)
                missing_ids.extend(coverage[child].missing)
            raw[id] = tuple(values)
            coverage[id] = Coverage(
                tuple(selected_ids), tuple(measured_ids), tuple(missing_ids)
            )
            reduced = self.reducer(raw[id]) if values else None
            if reduced is not None:
                if not isinstance(reduced, Quantity):
                    raise TypeError("reducer must return a schema Quantity")
                reduced = self.unit_system.convert(reduced, to=self.units)
            elif values:
                raise TypeError("reducer must return a schema Quantity")
            available[id] = reduced
            results[id] = (
                None if self.require_complete and not coverage[id].complete else reduced
            )
        return Aggregation(
            hierarchy,
            results,
            coverage,
            available,
            value_ids,
            self.reducer is sum_quantities,
        )


__all__ = ["Aggregation", "Coverage", "Reduction"]
