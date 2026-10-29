"""Rollups of recorded Values over a Hierarchy, with coverage and immutable results.

A ``QuantityRollup`` combines measurement Values and a ``FlowRollup`` combines Flow
Values. Both select their contributors in the same way, take one ``Reducer`` and
return a ``RollupResult``. These operations neither solve equations nor write
quantities into Models.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum, unique
from types import MappingProxyType
from typing import TYPE_CHECKING
from uuid import UUID

from rangekeeper.flow import Flow
from rangekeeper.model import Entity, Measure, Model, Value, ValueKind
from rangekeeper.model.system import _reducers
from rangekeeper.model.system.errors import RollupError
from rangekeeper.model.system.hierarchy import Hierarchy
from rangekeeper.model.system.matching import _prepare
from rangekeeper.model.system.selection import _local_value, _recorded_quantity
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.schema.records import Filter
from rangekeeper.shared.arguments import require_text, require_uuid

if TYPE_CHECKING:
    from rangekeeper.duration import Period
    from rangekeeper.flow import (
        AggregationMethod,
        AlignmentJoin,
        MissingValueHandling,
        ResampleMethod,
        StreamTable,
    )
    from rangekeeper.model.system.pivot import Pivot
    from rangekeeper.schema.records import Formulation


@unique
class Contributor(StrEnum):
    """Hierarchy nodes whose Values a rollup selects: leaves only, or all nodes."""

    LEAVES = "leaves"
    ALL = "all"


@unique
class Reducer(StrEnum):
    """How a rollup combines the Values of its contributors.

    ``SUM``, ``MIN`` and ``MAX`` apply to Quantities and Flows. ``MEAN`` and
    ``COUNT`` apply to Quantities. A mean uses the raw contributors of each
    subtree, never the means of its sub-trees. ``COUNT`` counts the contributors
    that have a value and returns a dimensionless whole number.
    """

    SUM = "sum"
    MEAN = "mean"
    MIN = "min"
    MAX = "max"
    COUNT = "count"


_QUANTITY_REDUCERS = {
    Reducer.SUM: _reducers.sum,
    Reducer.MEAN: _reducers.mean,
    Reducer.MIN: _reducers.min,
    Reducer.MAX: _reducers.max,
    Reducer.COUNT: _reducers.count,
}


@unique
class CoverageStatus(StrEnum):
    """Coverage state: no contributors, all measured, or some missing or undecided."""

    EMPTY = "empty"
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, kw_only=True)
class Coverage:
    """Selected, measured, missing and undecided owner UUIDs.

    ``measured`` and ``missing`` partition ``selected``. ``undecided`` holds the
    owners that a ``Filter`` could not decide, because a tested value is
    missing: they are not selected, and their contribution is unknown. Coverage
    does not certify a physical population.
    """

    selected: tuple[UUID, ...]
    measured: tuple[UUID, ...]
    missing: tuple[UUID, ...]
    undecided: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        for name in ("selected", "measured", "missing", "undecided"):
            items = tuple(getattr(self, name))
            if any(not isinstance(id, UUID) for id in items) or len(set(items)) != len(
                items
            ):
                raise RollupError("coverage must contain unique UUIDs")
            object.__setattr__(self, name, items)
        if set(self.measured) & set(self.missing) or set(self.selected) != set(
            self.measured
        ) | set(self.missing):
            raise RollupError(
                "measured and missing must partition selected contributors"
            )
        if set(self.undecided) & set(self.selected):
            raise RollupError("an undecided contributor cannot be selected")

    @property
    def complete(self) -> bool:
        """Whether a nonempty selected population is fully measured and decided."""
        return bool(self.selected) and not self.missing and not self.undecided

    @property
    def status(self) -> CoverageStatus:
        """Classify this coverage as empty, complete or incomplete."""
        return (
            CoverageStatus.EMPTY
            if not self.selected and not self.undecided
            else CoverageStatus.COMPLETE
            if self.complete
            else CoverageStatus.INCOMPLETE
        )


@dataclass(frozen=True, kw_only=True)
class RollupEntry:
    """The result over the measured contributors of one node, and its coverage."""

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
            raise RollupError("period coverage must contain fractions from zero to one")
        if periods and (
            not isinstance(self.available, Flow)
            or len(periods) != len(self.available.movements)
        ):
            raise RollupError("period coverage must match the available Flow")
        object.__setattr__(self, "period_coverage", periods)
        if bool(self.coverage.measured) != (self.available is not None):
            raise RollupError("measured coverage and available result must agree")


@dataclass(frozen=True, kw_only=True)
class RollupResult:
    """Immutable entries and selected Value identities, pinned to a Hierarchy.

    ``QuantityRollup`` and ``FlowRollup`` both return this type.
    """

    hierarchy: Hierarchy
    entries: Mapping[UUID, RollupEntry]
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
            raise RollupError("rollup entries must exactly match the hierarchy")
        # Each subtree is a contiguous preorder interval; no repeated subtree walks.
        positions = {uid: position for position, uid in enumerate(order)}
        ends: dict[UUID, int] = {}
        for uid in self.hierarchy.postorder():
            children = self.hierarchy.children(uid)
            ends[uid] = ends[children[-1]] if children else positions[uid] + 1
        for uid, entry in entries.items():
            if not isinstance(entry, RollupEntry):
                raise TypeError("entries must contain RollupEntry objects")
            if any(
                owner not in positions
                or not positions[uid] <= positions[owner] < ends[uid]
                for owner in (*entry.coverage.selected, *entry.coverage.undecided)
            ):
                raise RollupError("coverage must belong to its corresponding subtree")
            if any(owner not in value_ids for owner in entry.coverage.measured):
                raise RollupError(
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
                raise RollupError("value_ids must record selected owners' local Values")
        object.__setattr__(self, "entries", MappingProxyType(entries))
        object.__setattr__(self, "value_ids", MappingProxyType(value_ids))

    @property
    def root_value(self) -> Quantity | Flow | None:
        """Return the result at the Hierarchy root under the coverage policy."""
        return self.value(self.hierarchy.root)

    def value(self, id: UUID) -> Quantity | Flow | None:
        """Return one node's result; None when required coverage is incomplete."""
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
        """Return the contributor coverage for one node."""
        self.hierarchy.view.entity(id)
        return self.entries[id].coverage

    def available_value(self, id: UUID) -> Quantity | Flow | None:
        """Return the result over measured contributors, despite missing ones."""
        self.hierarchy.view.entity(id)
        return self.entries[id].available

    def display(self, *, transpose: bool = False, precision: int = 2) -> "StreamTable":
        """Display available Flow results; owner and period coverage remain inspectable."""
        from rangekeeper.flow import Stream

        flows = {}
        for index, identity in enumerate(self.hierarchy.preorder()):
            value = self.value(identity)
            if value is None:
                continue
            if not isinstance(value, Flow):
                raise RollupError(
                    "display shows Flow rollup results; this result holds Quantities"
                )
            entity = self.hierarchy.view.entity(identity)
            label = entity.name or entity.code or f"Entity {index + 1}"
            if label in flows:
                label = f"{label} ({index + 1})"
            flows[label] = value
        return Stream(flows=flows).display(transpose=transpose, precision=precision)


def classified(
    *,
    model: Model,
    classification: UUID,
    exclusive: bool = False,
) -> Callable[[Entity], bool]:
    """Return a contributor rule that selects Entities in a Classification.

    The rule includes the Classification's sub-types in its Taxonomy, as
    ``View.filter`` does. ``exclusive=True`` selects only that Classification.
    The UUID must exist in the Model. Unclassified Entities never match.
    """
    from rangekeeper.model.definitions import _classes

    if not isinstance(model, Model):
        raise TypeError("model must be a canonical Model")
    classes = _classes(model.definitions, classification, exclusive=exclusive)

    def contributes(entity: Entity) -> bool:
        return entity.classification in classes

    return contributes


@dataclass(frozen=True, kw_only=True)
class QuantityPopulation:
    """Raw quantities, contributor coverage and selected identities for one scope.

    ``View.quantities`` returns it. ``quantities`` are the recorded Quantities
    of the measured contributors, in the units asked for; ``coverage`` gives
    the selected, measured and missing contributors; ``value_ids`` maps each
    contributor with a selected Value to that Value's UUID.
    """

    quantities: tuple[Quantity, ...]
    coverage: Coverage
    value_ids: Mapping[UUID, UUID]


def _collect_quantities(
    selections: Iterable[tuple[Entity, Value | None]],
    units: str | None,
    unit_system: UnitSystem,
) -> QuantityPopulation:
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
    return QuantityPopulation(
        quantities=tuple(quantities),
        coverage=Coverage(
            selected=tuple(selected),
            measured=tuple(measured),
            missing=tuple(missing),
        ),
        value_ids=MappingProxyType(value_ids),
    )


class _Decision:
    """An internal three-valued contributor rule: True, False or None.

    None means that a Filter could not decide the Entity, because a tested value
    is missing. Pivots build these rules; users pass a ``Filter``.
    """

    __slots__ = ("test",)

    def __init__(self, test: Callable[[Entity], bool | None]) -> None:
        self.test = test

    def __call__(self, entity: Entity) -> bool | None:
        return self.test(entity)


def _decision(
    contributors: "Contributor | Filter | Callable[[Entity], bool]",
    model: Model,
    *,
    unit_system: UnitSystem,
) -> "Contributor | _Decision | Callable[[Entity], bool]":
    """Return a Filter's three-valued test; other rules stay as they are.

    The Filter's Value tests convert units with ``unit_system``.
    """
    if isinstance(contributors, Filter):
        return _Decision(_prepare(model, contributors, unit_system=unit_system))
    return contributors


@dataclass(frozen=True, kw_only=True)
class _Rollup:
    """Fields and contributor selection that both rollups share."""

    key: str
    reducer: Reducer = Reducer.SUM
    units: str | None = None
    measure: UUID | None = None
    contributors: Contributor | Filter | Callable[[Entity], bool] = Contributor.LEAVES
    require_complete: bool = True

    _kind = ValueKind.MEASUREMENT

    def __post_init__(self) -> None:
        require_text(self.key, "key")
        if self.measure is not None:
            require_uuid(self.measure, "measure")
        if not isinstance(self.reducer, Reducer):
            raise TypeError("reducer must be a Reducer")
        if not isinstance(self.contributors, (Contributor, Filter)) and not callable(
            self.contributors
        ):
            raise TypeError("contributors must be a Contributor, Filter or callable")
        if type(self.require_complete) is not bool:
            raise TypeError("require_complete must be a bool")
        if self.units is not None:
            require_text(self.units, "units")

    def execute(self, hierarchy: Hierarchy) -> RollupResult:
        """Return a detached derived result over ``hierarchy``."""
        raise NotImplementedError

    def _unit_system(self, model: Model) -> UnitSystem:
        """Return the unit system of the Values and the Filter tests: the Model's."""
        return model.unit_system

    def _contributor_rule(
        self, model: Model
    ) -> "Contributor | _Decision | Callable[[Entity], bool]":
        """Return the contributor rule, with a Filter tested in this unit system."""
        return _decision(self.contributors, model, unit_system=self._unit_system(model))

    def pivot(
        self,
        hierarchy: Hierarchy,
        *,
        by: UUID | None = None,
        depth: int = 1,
        only: UUID | None = None,
        exclusive: bool = False,
        label: str | None = None,
    ) -> "Pivot":
        """Roll up over ``hierarchy`` once per column of a Taxonomy below ``by``.

        The "All" column uses this rollup's contributors, narrowed by ``only``.
        Each further column also requires the column's Classification. Columns are
        the Classifications up to ``depth`` levels below ``by``, in Taxonomy order.
        Classifications include their sub-types unless ``exclusive``. Each cell is
        a ``RollupEntry`` from ``execute``, so means stay correctly weighted.

        With ``label``, a column tests the Entity's Label with that key instead
        of its Classification: an Entity is in every column that one of its
        Label's Classifications matches. Without ``by``, the columns start at the
        root of the one Taxonomy that the rows' Labels use. ``only`` still tests
        the Entity's Classification.
        """
        from rangekeeper.model.system.pivot import pivot

        return pivot(
            self,
            hierarchy,
            by=by,
            depth=depth,
            only=only,
            exclusive=exclusive,
            label=label,
        )

    @staticmethod
    def _eligible(rule, entity: Entity, *, leaf: bool) -> bool | None:
        if rule is Contributor.LEAVES:
            return leaf
        if rule is Contributor.ALL:
            return True
        if isinstance(rule, _Decision):
            return rule(entity)
        eligible = rule(entity)
        if type(eligible) is not bool:
            raise TypeError("contributors must return bool")
        return eligible

    def _selection(self, model: Model, entity: Entity) -> Value | None:
        selected = _local_value(model, entity, key=self.key, measure=self.measure)
        if selected is not None and selected.kind is not self._kind:
            raise RollupError(f"expected {self._kind.value} Values")
        return selected

    def _population(self, hierarchy: Hierarchy):
        """Select each eligible owner's Value once; list each subtree's owners.

        Also list each subtree's undecided owners: those that a Filter could not
        decide because a tested value is missing.
        """
        if not isinstance(hierarchy, Hierarchy):
            raise TypeError("hierarchy must be a Hierarchy")
        model = hierarchy.view.model
        if self.measure is not None:
            # A supplied Measure must exist even when no owner has the key.
            model._index.get(self.measure, Measure)
        rule = self._contributor_rule(model)
        selected: dict[UUID, Value | None] = {}
        populations: dict[UUID, tuple[UUID, ...]] = {}
        undecided: dict[UUID, tuple[UUID, ...]] = {}
        for identity in hierarchy.postorder():
            entity = hierarchy.view.entity(identity)
            children = hierarchy.children(identity)
            eligible = self._eligible(rule, entity, leaf=not children)
            if eligible:
                selected[identity] = self._selection(model, entity)
            populations[identity] = (() if not eligible else (identity,)) + tuple(
                owner for child in children for owner in populations[child]
            )
            undecided[identity] = (() if eligible is not None else (identity,)) + tuple(
                owner for child in children for owner in undecided[child]
            )
        return selected, populations, undecided


@dataclass(frozen=True, kw_only=True)
class QuantityRollup(_Rollup):
    """Roll up one measurement Value, by owner-local key, over a Hierarchy.

    Each contributor's Value with ``key`` converts to ``units``, then the
    ``reducer`` combines the raw contributors of each subtree. ``Reducer.COUNT``
    takes no ``units``; every other reducer requires them. ``measure`` asserts
    the Measure UUID of each selected Value; it never selects a Value by itself.
    Contributors default to the leaves, so a parent that records a total is not
    counted twice. Missing Values and unresolved Quantities count as missing,
    never as zero. ``unit_system`` converts the Values and the Value tests of a
    ``Filter`` contributor rule; without it, ``execute`` uses the Model's.
    """

    unit_system: UnitSystem | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.unit_system is not None and not isinstance(
            self.unit_system, UnitSystem
        ):
            raise TypeError("unit_system must be a UnitSystem")
        if self.reducer is Reducer.COUNT:
            if self.units is not None:
                raise RollupError("count rollups take no units")
        elif self.units is None:
            raise RollupError("quantity rollups require units")
        elif self.unit_system is not None:
            # Without a unit system, execute checks units against the Model's.
            self.unit_system.validate_units(self.units)

    def execute(self, hierarchy: Hierarchy) -> RollupResult:
        """Return a detached derived result; never revise, persist or solve a Model.

        Raw contributors are combined at each subtree, so means stay correctly
        weighted. Missing keys and unresolved quantities count as missing.
        """
        selected, populations, undecided = self._population(hierarchy)
        unit_system = self._unit_system(hierarchy.view.model)
        if self.units is not None:
            unit_system.validate_units(self.units)
        quantities = {
            owner: quantity
            for owner, value in selected.items()
            if (quantity := _recorded_quantity(value, self.units, unit_system))
            is not None
        }
        reduce = _QUANTITY_REDUCERS[self.reducer]
        entries = {}
        for node, population in populations.items():
            measured = tuple(owner for owner in population if owner in quantities)
            missing = tuple(owner for owner in population if owner not in quantities)
            available = None
            if measured:
                result = reduce(tuple(quantities[owner] for owner in measured))
                available = (
                    result
                    if self.units is None
                    else unit_system.convert(quantity=result, to=self.units)
                )
            entries[node] = RollupEntry(
                available=available,
                coverage=Coverage(
                    selected=population,
                    measured=measured,
                    missing=missing,
                    undecided=undecided[node],
                ),
            )
        value_ids = {
            owner: value.id for owner, value in selected.items() if value is not None
        }
        return RollupResult(
            hierarchy=hierarchy,
            entries=entries,
            value_ids=value_ids,
            require_complete=self.require_complete,
        )

    def _unit_system(self, model: Model) -> UnitSystem:
        """Return ``unit_system``, or the Model's when it is None."""
        return model.unit_system if self.unit_system is None else self.unit_system


@dataclass(frozen=True)
class _FlowRule:
    periods: "tuple[Period, ...] | None"
    resampling: "ResampleMethod | None"
    aggregation: "AggregationMethod"
    missing: "MissingValueHandling"
    join: "AlignmentJoin"


@dataclass(frozen=True, kw_only=True)
class FlowRollup(_Rollup):
    """Roll up one Flow Value, by owner-local key, over a Hierarchy.

    The Flows of each subtree's raw contributors combine at each coordinate with
    ``Reducer.SUM``, ``MIN`` or ``MAX``. With ``periods`` and ``resampling``,
    each Flow is resampled first. ``missing`` and ``join`` treat unknown
    Movements and coordinates that only some Flows have. ``units`` converts the
    results; without it the Flows keep their own units. Contributors default to
    the leaves, as for ``QuantityRollup``. A contributor without a Flow counts as
    missing. ``MissingValueHandling.ZERO`` is refused: a rollup never reads a
    missing Movement or coordinate as zero.
    """

    periods: "Sequence[Period] | None" = None
    resampling: "ResampleMethod | None" = None
    missing: "MissingValueHandling | None" = None
    join: "AlignmentJoin | None" = None
    _rule: _FlowRule = field(init=False, repr=False, compare=False)

    _kind = ValueKind.FLOW

    def __post_init__(self) -> None:
        from rangekeeper.flow import (
            AggregationMethod,
            AlignmentJoin,
            MissingValueHandling,
            ResampleMethod,
        )

        super().__post_init__()
        if self.reducer not in (Reducer.SUM, Reducer.MIN, Reducer.MAX):
            raise RollupError("Flow rollups take Reducer.SUM, MIN or MAX")
        if (self.periods is None) != (self.resampling is None):
            raise RollupError("supply both periods and resampling, or neither")
        if self.resampling is not None and not isinstance(
            self.resampling, ResampleMethod
        ):
            raise TypeError("resampling must be a ResampleMethod")
        missing = MissingValueHandling.ERROR if self.missing is None else self.missing
        join = AlignmentJoin.EXACT if self.join is None else self.join
        if not isinstance(missing, MissingValueHandling) or not isinstance(
            join, AlignmentJoin
        ):
            raise TypeError("missing and join require their enum types")
        if missing is MissingValueHandling.ZERO:
            raise RollupError(
                "a Flow rollup never treats a missing value as zero; "
                "use ERROR, PROPAGATE or SKIP"
            )
        object.__setattr__(
            self,
            "_rule",
            _FlowRule(
                None if self.periods is None else tuple(self.periods),
                self.resampling,
                AggregationMethod(self.reducer.value),
                missing,
                join,
            ),
        )

    def execute(self, hierarchy: Hierarchy) -> RollupResult:
        """Return a detached derived result; never revise, persist or solve a Model.

        Each owner's Flow is selected once, and the collection is prepared once.
        All subtree results are then batched over the original contributors.
        """
        from rangekeeper.flow import Stream

        selected, populations, undecided = self._population(hierarchy)
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
            rule = self._rule
            stream = Stream(
                flows={str(i): available[owner].flow for i, owner in enumerate(owners)},
                missing=rule.missing,
                join=rule.join,
            )
            if rule.periods is not None and rule.resampling is not None:
                stream = stream.resample(periods=rule.periods, method=rule.resampling)
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
                    strict=True,
                )
            )
        entries = {}
        for node, population in populations.items():
            measured = tuple(owner for owner in population if owner in available)
            missing = tuple(owner for owner in population if owner not in available)
            result = results.get(node)
            entries[node] = RollupEntry(
                available=None if result is None else result.flow,
                coverage=Coverage(
                    selected=population,
                    measured=measured,
                    missing=missing,
                    undecided=undecided[node],
                ),
                period_coverage=() if result is None else result.coverage,
            )
        return RollupResult(
            hierarchy=hierarchy,
            entries=entries,
            value_ids=value_ids,
            require_complete=self.require_complete,
        )

    def formulate(
        self,
        hierarchy: Hierarchy,
        *,
        id: UUID,
        aggregates: Mapping[UUID, UUID],
    ) -> "Formulation":
        """Declare hierarchy sums over the same original structural contributors."""
        from rangekeeper.model.formulation.hierarchy import formulate

        if self.reducer is not Reducer.SUM:
            raise RollupError("formulate requires Reducer.SUM")
        if not isinstance(self.contributors, Contributor):
            raise RollupError(
                "symbolic selection requires Contributor.LEAVES or ALL; "
                "select a structural View explicitly"
            )
        selected, populations, _ = self._population(hierarchy)
        return formulate(
            hierarchy,
            id=id,
            aggregates=aggregates,
            selected=selected,
            populations=populations,
            rule=self._rule,
        )


__all__ = [
    "RollupResult",
    "RollupEntry",
    "Coverage",
    "CoverageStatus",
    "Contributor",
    "Reducer",
    "QuantityRollup",
    "FlowRollup",
    "classified",
]
