"""Explicit recorded-Value reductions, coverage, and immutable results.

These operations neither solve equations nor write quantities into Models.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rangekeeper.model.duration import Period
    from rangekeeper.model.flux import MissingValueHandling
    from rangekeeper.calculations.series import (
        ResamplingMethod,
        AggregationMethod,
        MeanWeighting,
        AlignmentJoin,
    )
from dataclasses import dataclass
from enum import Enum, unique
from types import MappingProxyType
from uuid import UUID
from rangekeeper.model import Entity, Value, Quantity, ValueKind
from rangekeeper.schema.records import Flow
from rangekeeper.shared.units import UnitSystem, default_units
from rangekeeper.model.system.errors import AggregationError, SelectionError
from rangekeeper.model.system.hierarchy import Hierarchy
from rangekeeper.model.system.selection import ValueSelector, _recorded_quantity


@unique
class Contributor(Enum):
    LEAVES = "leaves"
    ALL = "all"


@dataclass(frozen=True)
class _FlowRule:
    periods: tuple | None
    resampling: object
    aggregation: object
    weighting: object
    missing: object
    join: object


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

    available: Quantity | Flow | None
    coverage: Coverage
    period_coverage: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.coverage, Coverage):
            raise TypeError("coverage must be Coverage")
        if self.available is not None and not isinstance(
            self.available, (Quantity, Flow)
        ):
            raise TypeError("available must be a schema Quantity, Flow or None")
        periods = tuple(self.period_coverage)
        if any(type(v) not in (int, float) or not 0 <= v <= 1 for v in periods):
            raise AggregationError(
                "period coverage must contain fractions from zero to one"
            )
        if periods and (
            not isinstance(self.available, Flow)
            or len(periods) != len(self.available.movements)
        ):
            raise AggregationError("period coverage must match the available Flow")
        object.__setattr__(self, "period_coverage", periods)
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
    def root_value(self) -> Quantity | Flow | None:
        return self.value(self.hierarchy.root)

    def value(self, id: UUID) -> Quantity | Flow | None:
        self.hierarchy.view.entity(id)
        entry = self.entries[id]
        return (
            None
            if self.require_complete and not entry.coverage.complete
            else entry.available
        )

    def __getitem__(self, id: UUID) -> Quantity | Flow | None:
        return self.value(id)

    def coverage(self, id: UUID) -> Coverage:
        self.hierarchy.view.entity(id)
        return self.entries[id].coverage

    def available_value(self, id: UUID) -> Quantity | Flow | None:
        self.hierarchy.view.entity(id)
        return self.entries[id].available

    def display(self, *, transpose: bool = False, precision: int = 2):
        """Display available Flow results; owner and period coverage remain inspectable."""
        from rangekeeper.model.flux import Stream

        flows = {}
        for index, identity in enumerate(self.hierarchy.preorder()):
            value = self.value(identity)
            if value is None:
                continue
            if not isinstance(value, Flow):
                raise TypeError("display requires Flow aggregation results")
            entity = self.hierarchy.view.entity(identity)
            label = entity.name or entity.code or f"Entity {index+1}"
            if label in flows:
                label = f"{label} ({index+1})"
            flows[label] = value
        return Stream(flows).display(transpose=transpose, precision=precision)


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
    reducer: Callable[[tuple[Quantity, ...]], Quantity] | None
    units: str | None
    contributors: Contributor | Callable[[Entity], bool] | None = None
    require_complete: bool = True
    unit_system: UnitSystem = default_units
    _flow: _FlowRule | None = None

    def __post_init__(self) -> None:
        if (
            not callable(self.select)
            or self._flow is None
            and not callable(self.reducer)
        ):
            raise TypeError("select and reducer must be callable")
        if (
            self.contributors is not None
            and not isinstance(self.contributors, Contributor)
            and not callable(self.contributors)
        ):
            raise TypeError("contributors must be callable")
        if not isinstance(self.require_complete, bool):
            raise TypeError("require_complete must be a bool")
        if not isinstance(self.unit_system, UnitSystem):
            raise TypeError("unit_system must be a UnitSystem")
        if self.units is not None:
            self.unit_system.validate_units(self.units)
        elif self._flow is None:
            raise TypeError("scalar reductions require units")

    def execute(self, hierarchy: Hierarchy) -> Aggregation:
        """Return a detached derived result; never revise, persist, or execute a Model.

        Selectors must return a Value actually owned by the supplied Entity in this
        revision. That rejects stale, cross-owner and Formulation-local shortcuts.
        Raw contributors are combined at each subtree so means remain correctly
        weighted. Missing keys and unresolved quantities count as missing, not zero.
        """
        if not isinstance(hierarchy, Hierarchy):
            raise TypeError("hierarchy must be a Hierarchy")
        if self._flow is not None:
            return self._execute_flows(hierarchy)
        raw: dict[UUID, tuple[Quantity, ...]] = {}
        entries: dict[UUID, AggregateEntry] = {}
        value_ids: dict[UUID, UUID] = {}
        for id in hierarchy.postorder():
            own = self._contribution(
                hierarchy.view.model,
                hierarchy.view.entity(id),
                leaf=not hierarchy.children(id),
            )
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

    def _contribution(self, model, entity, *, leaf=True) -> _Population:
        assert self.units is not None
        if not self._eligible(entity, leaf=leaf):
            return _collect_quantities((), self.units, self.unit_system)
        selected = self._selection(model, entity)
        return _collect_quantities(((entity, selected),), self.units, self.unit_system)

    @classmethod
    def flows(
        cls,
        *,
        key: str,
        periods: "Sequence[Period] | None" = None,
        resampling: "ResamplingMethod | None" = None,
        aggregation: "AggregationMethod | None" = None,
        weighting: "MeanWeighting | None" = None,
        contributors: "Contributor | Callable[[Entity], bool]" = Contributor.LEAVES,
        units: str | None = None,
        missing: "MissingValueHandling | None" = None,
        join: "AlignmentJoin | None" = None,
        require_complete: bool = True,
    ) -> "Reduction":
        """Select owner-local Flow Values and combine original contributors per subtree."""
        from rangekeeper.calculations.series import (
            AggregationMethod,
            AlignmentJoin,
            ResamplingMethod,
        )
        from rangekeeper.model.flux import MissingValueHandling
        from rangekeeper.model.system.selection import select_value

        if (periods is None) != (resampling is None):
            raise ValueError("supply both periods and resampling, or neither")
        if resampling is not None and not isinstance(resampling, ResamplingMethod):
            raise TypeError("resampling must be a ResamplingMethod")
        rule = _FlowRule(
            None if periods is None else tuple(periods),
            resampling,
            AggregationMethod.SUM if aggregation is None else aggregation,
            weighting,
            MissingValueHandling.ERROR if missing is None else missing,
            AlignmentJoin.EXACT if join is None else join,
        )
        if (
            not isinstance(rule.aggregation, AggregationMethod)
            or not isinstance(rule.missing, MissingValueHandling)
            or not isinstance(rule.join, AlignmentJoin)
        ):
            raise TypeError("aggregation, missing and join require their enum types")
        return cls(
            select=select_value(key),
            reducer=None,
            units=units,
            contributors=contributors,
            require_complete=require_complete,
            _flow=rule,
        )

    def _eligible(self, entity, *, leaf):
        eligible = (
            leaf
            if self.contributors is Contributor.LEAVES
            else (
                True
                if self.contributors in (None, Contributor.ALL)
                else self.contributors(entity)
            )
        )
        if type(eligible) is not bool:
            raise TypeError("contributors must return bool")
        return eligible

    def _selection(self, model, entity):
        selected = self.select(model, entity)
        if selected is not None:
            if not isinstance(selected, Value):
                raise TypeError("select must return a schema Value or None")
            if (
                model.owner_of(selected.id) != entity.id
                or model.value(selected.id) != selected
            ):
                raise SelectionError(
                    f"selector returned a stale or nonlocal Value {selected.id} for {entity.id}"
                )
            kind = ValueKind.FLOW if self._flow is not None else ValueKind.MEASUREMENT
            if selected.kind is not kind:
                raise AggregationError(f"expected {kind.value} Values")
        return selected

    def _flow_population(self, hierarchy):
        if not isinstance(hierarchy, Hierarchy):
            raise TypeError("hierarchy must be a Hierarchy")
        selected = {}
        populations = {}
        for identity in hierarchy.postorder():
            entity = hierarchy.view.entity(identity)
            children = hierarchy.children(identity)
            own = ()
            if self._eligible(entity, leaf=not children):
                selected[identity] = self._selection(hierarchy.view.model, entity)
                own = (identity,)
            populations[identity] = own + tuple(
                owner for child in children for owner in populations[child]
            )
        return selected, populations

    def _execute_flows(self, hierarchy):
        from rangekeeper.model.flux import Stream

        selected, populations = self._flow_population(hierarchy)
        available = {
            owner: value
            for owner, value in selected.items()
            if value is not None and value.flow is not None
        }
        value_ids = {
            owner: value.id for owner, value in selected.items() if value is not None
        }
        owners = tuple(available)
        positions = {owner: i for i, owner in enumerate(owners)}
        groups = {
            node: tuple(positions[owner] for owner in population if owner in positions)
            for node, population in populations.items()
        }
        results = {}
        if owners:
            stream = Stream(
                {str(i): available[owner].flow for i, owner in enumerate(owners)}
            )
            rule = self._flow
            if rule.periods is not None:
                stream = stream.resample(
                    rule.periods,
                    method=rule.resampling,
                    weighting=rule.weighting,
                    missing=rule.missing,
                )
            nodes = tuple(node for node, group in groups.items() if group)
            results = dict(
                zip(
                    nodes,
                    stream._prepared().aggregate_groups(
                        tuple(groups[node] for node in nodes),
                        method=rule.aggregation,
                        units=self.units,
                        missing=rule.missing,
                        join=rule.join,
                    ),
                )
            )
        entries = {}
        for node, population in populations.items():
            measured = tuple(owner for owner in population if owner in available)
            missing = tuple(owner for owner in population if owner not in available)
            result = results.get(node)
            entries[node] = AggregateEntry(
                None if result is None else result.flow,
                Coverage(population, measured, missing),
                () if result is None else result.coverage,
            )
        return Aggregation(hierarchy, entries, value_ids, self.require_complete)

    def formulate(
        self,
        hierarchy: Hierarchy,
        *,
        id: UUID,
        aggregates: Mapping[UUID, UUID],
    ):
        """Declare hierarchy sums over the same original structural contributors."""
        from rangekeeper.model.formulation.hierarchy import formulate
        from rangekeeper.calculations.series import AggregationMethod

        if self._flow is None or self._flow.aggregation is not AggregationMethod.SUM:
            raise ValueError("formulate requires a built-in Flow SUM rule")
        if callable(self.contributors):
            raise ValueError(
                "symbolic selection requires Contributor.LEAVES or ALL; select a structural View explicitly"
            )
        selected, populations = self._flow_population(hierarchy)
        return formulate(
            hierarchy,
            id=id,
            aggregates=aggregates,
            selected=selected,
            populations=populations,
            rule=self._flow,
        )


__all__ = [
    "Aggregation",
    "AggregateEntry",
    "Coverage",
    "CoverageStatus",
    "Contributor",
    "Reduction",
]
