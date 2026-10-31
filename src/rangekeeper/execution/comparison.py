"""Compare two or more Outcomes with one call: side by side, or paired with a baseline.

``compare`` returns a ``SideBySide`` without a baseline and a ``Paired`` with
one, so that each result has only the members that apply to it. The cases of
two batches across market paths pair by path; other cases pair by case key.
``compare`` takes the ``Mean`` of a batch, from
``Outcome.mean()``, as one leaf Outcome. ``Paired.by(key=)`` and
``Paired.by_case`` put the pairs in ``Groups``, with the statistics of each
group.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from itertools import groupby
from types import MappingProxyType
from typing import TYPE_CHECKING, Self, overload
from uuid import UUID

from rangekeeper.duration.dates import DateValue, Never, order
from rangekeeper.execution.distribution import SUMMARY, Distribution, Mean
from rangekeeper.execution.outcome import Outcome
from rangekeeper.flow.table import render
from rangekeeper.quantity import Quantity, isclose
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, MissingReferenceError
from rangekeeper.shared.table import Table

Compared = Outcome | Mean
"""An Outcome, or the Mean of a batch, which compares as one leaf Outcome."""
Member = tuple[str | None, Compared]
"""One leaf case of an Outcome with its case key, or a leaf Outcome with None."""
PathKey = tuple[UUID, str | None]
"""The path of a case across market paths: the Paths UUID and the path key."""
_SUMMARY = ("key", *SUMMARY, "share_above_zero")
"""The columns of a paired summary after the labels of its rows."""

if TYPE_CHECKING:
    from _typeshed import SupportsRichComparison


@overload
def compare(
    *,
    outcomes: Mapping[str, Compared],
    keys: Sequence[str],
    baseline: None = None,
) -> "SideBySide": ...


@overload
def compare(
    *,
    outcomes: Mapping[str, Compared],
    keys: Sequence[str],
    baseline: str,
) -> "Paired": ...


def compare(
    *,
    outcomes: Mapping[str, Compared],
    keys: Sequence[str],
    baseline: str | None = None,
) -> "SideBySide | Paired":
    """Compare two or more named Outcomes on ``keys``.

    Without ``baseline``, return a ``SideBySide`` of the values. With
    ``baseline``, the name of one of the Outcomes, return a ``Paired``: each
    other Outcome's differences from the baseline, paired case by case. The
    call is the same for two Outcomes and for more. The ``Mean`` of a batch,
    ``outcome.mean()``, compares as one leaf Outcome.
    """
    named = _outcomes(outcomes)
    wanted = _keys(keys)
    if baseline is None:
        return SideBySide._of(named, wanted)
    if baseline not in named:
        raise MissingReferenceError(
            baseline, kind="Outcome", by="name", where="compare", candidates=named
        )
    return Paired._of(named, wanted, baseline)


@dataclass(frozen=True, kw_only=True)
class Pair:
    """One Outcome member and the baseline member that it is paired with.

    ``case`` is the case key of the pair, as in the ``case`` column of
    ``Outcome.table``: the keys of nested batches joined by ``/``. It is None
    when both sides are leaf Outcomes.
    """

    case: str | None
    member: Outcome | Mean
    baseline: Outcome | Mean


@dataclass(frozen=True, kw_only=True, init=False)
class SideBySide:
    """The values of named leaf Outcomes on some keys, side by side.

    Make it with ``rk.execution.compare`` without a baseline. ``values`` gives
    one row for each key and one column for each Outcome. It displays as a
    table (with the ``calculations`` extra).
    """

    outcomes: Mapping[str, Compared]
    keys: tuple[str, ...]

    @classmethod
    def _of(cls, outcomes: Mapping[str, Compared], keys: tuple[str, ...]) -> Self:
        for name, outcome in outcomes.items():
            if _is_batch(outcome):
                raise ContractError(
                    f"{name} is a batch: compare it with baseline=, "
                    "or compare one of its cases",
                    code=Code.COMPARISON_BATCH,
                    values={"outcome": name},
                )
            for key in keys:
                _scalar(outcome, key, name)
        made = object.__new__(cls)
        object.__setattr__(made, "outcomes", outcomes)
        object.__setattr__(made, "keys", keys)
        return made

    @property
    def values(self) -> Table:
        """Return the values: a ``key`` column, then one column for each Outcome.

        Each cell is the Outcome's Quantity.
        """
        return Table(
            ("key", *self.outcomes),
            (
                {
                    "key": key,
                    **{
                        name: _scalar(outcome, key, name)
                        for name, outcome in self.outcomes.items()
                    },
                }
                for key in self.keys
            ),
        )

    def select(self, *keys: str) -> "SideBySide":
        """Return the same comparison on some of its keys, in the order given."""
        return SideBySide._of(self.outcomes, _selected(self.keys, keys))

    def _cells(self) -> tuple[list[str], list[list[str]]]:
        table = self.values
        body = [
            [str(row.values["key"])]
            + [_text(row.values[name]) for name in self.outcomes]
            for row in table.rows
        ]
        return list(table.columns), body

    def _repr_html_(self) -> str:
        return render(*self._cells(), html=True)

    def __str__(self) -> str:
        return render(*self._cells(), html=False)

    def __repr__(self) -> str:
        return str(self)


@dataclass(frozen=True, kw_only=True, init=False)
class Paired:
    """The paired differences of named Outcomes from a baseline, on some keys.

    Make it with ``rk.execution.compare(..., baseline=)``. ``differences``
    gives one row for each Outcome, key and pair, ``summary()`` the
    statistics of the paired differences, and ``distribution(outcome=,
    key=)`` the distribution of one Outcome's differences. ``by(key=)`` and
    ``by_case`` give the statistics of groups of pairs.

    Each member of an Outcome is one leaf case, in ``walk()`` order; a leaf
    Outcome has one member. When every case of two batches takes a market
    path, their members pair by path: the Paths that each case's Run pins and
    the path key, so a batch of cases each across the paths pairs with one
    batch across the same paths. Other batches pair by case key, and must
    have the same case keys. A leaf pairs with every member of the other side.

    It displays as a table (with the ``calculations`` extra): the values and
    differences of leaf Outcomes, or the ``summary()`` of batches.
    """

    outcomes: Mapping[str, Compared]
    keys: tuple[str, ...]
    baseline: str
    _members: Mapping[str, tuple[Member, ...]] = field(repr=False, compare=False)

    @classmethod
    def _of(
        cls,
        outcomes: Mapping[str, Compared],
        keys: tuple[str, ...],
        baseline: str,
    ) -> Self:
        members = {name: _case_members(item) for name, item in outcomes.items()}
        made = cls._with(
            outcomes=outcomes,
            keys=keys,
            baseline=baseline,
            members=MappingProxyType(members),
        )
        for name in made.compared:
            made.pairs(outcome=name)
        for name, found in members.items():
            for _, member in found:
                for key in keys:
                    _scalar(member, key, name)
        return made

    @classmethod
    def _with(
        cls,
        *,
        outcomes: Mapping[str, Compared],
        keys: tuple[str, ...],
        baseline: str,
        members: Mapping[str, tuple[Member, ...]],
    ) -> Self:
        made = object.__new__(cls)
        for name, value in (
            ("outcomes", outcomes),
            ("keys", keys),
            ("baseline", baseline),
            ("_members", members),
        ):
            object.__setattr__(made, name, value)
        return made

    @property
    def compared(self) -> tuple[str, ...]:
        """Return the names of the Outcomes that are not the baseline, in order."""
        return tuple(name for name in self.outcomes if name != self.baseline)

    def pairs(self, *, outcome: str) -> tuple[Pair, ...]:
        """Return the pairs of one compared Outcome with the baseline, in case order.

        Members of two batches across market paths pair by path, and other
        members of two batches by case key; a leaf on either side pairs with
        each member of the other. ``Pair.case`` is the case key of the
        compared member. Batches across other Paths raise ContractError
        (``comparison.paths``). Batches with other paths or case keys, or
        with a path or a key that two baseline cases share, raise
        ContractError (``comparison.cases``).
        """
        members = self._members[self._compared(outcome)]
        bases = self._members[self.baseline]
        if bases[0][0] is None:  # a leaf baseline pairs with every member
            return tuple(
                Pair(case=case, member=member, baseline=bases[0][1])
                for case, member in members
            )
        if members[0][0] is None:  # a leaf pairs with every baseline member
            return tuple(
                Pair(case=case, member=members[0][1], baseline=base)
                for case, base in bases
            )
        if _across_paths(self.outcomes[outcome]) and _across_paths(
            self.outcomes[self.baseline]
        ):
            self._require_same_paths(outcome)
            by_path = {_path(base): base for _, base in bases}
            return tuple(
                Pair(case=case, member=member, baseline=by_path[_path(member)])
                for case, member in members
            )
        self._require_same_cases(outcome)
        by_case = dict(bases)
        return tuple(
            Pair(case=case, member=member, baseline=by_case[case])
            for case, member in members
        )

    def difference(self, *, outcome: str, key: str) -> tuple[Quantity, ...]:
        """Return the paired differences of one Outcome on one key, in pair order.

        Each difference is the Outcome's value less the baseline's value, in
        the baseline's units.
        """
        return self.distribution(outcome=outcome, key=key).values

    def distribution(self, *, outcome: str, key: str) -> Distribution[Pair]:
        """Return the distribution of one Outcome's paired differences on one key.

        Each pair has the same weight. Each difference is the Outcome's value
        less the baseline's value, in the baseline's units: ``mean()``,
        ``quantile(level=)``, ``probability(below=, above=)`` and
        ``summary()`` read the differences, and ``case(quantile=)`` returns
        the ``Pair`` at a quantile.
        """
        _require_key(self.keys, key)
        return _differences(
            self.pairs(outcome=outcome), key=key, name=outcome, baseline=self.baseline
        )

    @property
    def differences(self) -> Table:
        """Return one row for each compared Outcome, key and pair.

        The columns are ``outcome``, ``key``, ``case``, ``value``,
        ``baseline`` and ``difference``. ``case`` is the case key of the pair.
        """
        rows = [
            {
                "outcome": name,
                "key": key,
                "case": pair.case,
                "value": _scalar(pair.member, key, name),
                "baseline": _scalar(pair.baseline, key, self.baseline),
                "difference": _difference(
                    pair, key=key, name=name, baseline=self.baseline
                ),
            }
            for name in self.compared
            for pair in self.pairs(outcome=name)
            for key in self.keys
        ]
        return Table(
            ("outcome", "key", "case", "value", "baseline", "difference"), rows
        )

    def summary(self) -> Table:
        """Return the statistics of the paired differences of each Outcome and key.

        The columns are ``outcome``, then the columns of the differences'
        ``Distribution.summary()``: ``key``, ``count``, ``mean``,
        ``standard_deviation``, ``minimum``, ``quantile_05``, ``quantile_95``
        and ``maximum``; and ``share_above_zero``, the share of pairs whose
        difference is above zero.
        """
        rows = [
            _summary_row(
                labels={"outcome": name},
                found=self.distribution(outcome=name, key=key),
            )
            for name in self.compared
            for key in self.keys
        ]
        return Table(("outcome", *_SUMMARY), rows)

    def by(self, *, key: str) -> "Groups":
        """Return the pairs of each compared Outcome in groups by a value of its member.

        A group holds the pairs whose compared member has one value at
        ``key``, which need not be a compared key: ``by(key="start_date")``
        groups the pairs by each case's start date. The groups are in
        ascending order of value, with ``NEVER`` after every date. A Flow
        value raises ContractError (``comparison.scalar``).
        """
        groups = {
            name: _by_value(self.pairs(outcome=name), key=key, name=name)
            for name in self.compared
        }
        return Groups._of(paired=self, column=key, groups=groups)

    @property
    def by_case(self) -> "Groups":
        """Return the pairs of each compared Outcome in groups by case.

        A batch has one group for each of its direct cases, in case order,
        with the pairs of that case's leaf cases; the ``case`` column holds
        the case key. A leaf Outcome is one group with its key, and a
        ``Mean`` one group without a key.
        """
        groups = {
            name: _by_case(self.outcomes[name], self.pairs(outcome=name))
            for name in self.compared
        }
        return Groups._of(paired=self, column="case", groups=groups)

    def select(self, *keys: str) -> "Paired":
        """Return the same comparison on some of its keys, in the order given."""
        return Paired._with(
            outcomes=self.outcomes,
            keys=_selected(self.keys, keys),
            baseline=self.baseline,
            members=self._members,
        )

    def where(self, **values: object) -> "Paired":
        """Return the comparison of the pairs whose compared member has these values.

        Name each value by its key: ``where(b_design="hotel")`` keeps the pairs
        where the compared Outcome's value equals it, and a list keeps any of
        its items (D40). Quantities compare after unit conversion. The
        baseline keeps all its members. When no case of an Outcome has these
        values, raise ContractError (``comparison.empty``).
        """
        if not values:
            raise TypeError("where takes at least one key")
        members = dict(self._members)
        for name in self.compared:
            kept = tuple(
                (case, member)
                for case, member in members[name]
                if all(_matches(member[key], wanted) for key, wanted in values.items())
            )
            if not kept:
                raise ContractError(
                    f"no case of {name} has these values",
                    code=Code.COMPARISON_EMPTY,
                    values={"outcome": name, "keys": list(values)},
                )
            members[name] = kept
        return Paired._with(
            outcomes=self.outcomes,
            keys=self.keys,
            baseline=self.baseline,
            members=MappingProxyType(members),
        )

    def _compared(self, outcome: str) -> str:
        if outcome not in self.compared:
            raise MissingReferenceError(
                outcome,
                kind="Outcome",
                by="name",
                where="Paired",
                candidates=self.compared,
            )
        return outcome

    def _require_same_paths(self, outcome: str) -> None:
        """Require two batches across the same Paths, with the same paths."""
        paths = _paths_of(self.outcomes[outcome], outcome, unique=False)
        bases = _paths_of(self.outcomes[self.baseline], self.baseline, unique=True)
        documents = {item[0] for item in paths}
        expected = {item[0] for item in bases}
        if documents != expected:
            raise ContractError(
                f"{outcome} and {self.baseline} take their cases from other "
                "Paths: paired differences need the same market paths",
                code=Code.COMPARISON_PATHS,
                values={
                    "outcome": outcome,
                    "baseline": self.baseline,
                    "paths": sorted(str(item) for item in documents),
                    "baseline_paths": sorted(str(item) for item in expected),
                },
            )
        if paths != bases:
            raise ContractError(
                f"{outcome} and {self.baseline} have different paths: "
                "paired differences need the same path keys",
                code=Code.COMPARISON_CASES,
                values={
                    "outcome": outcome,
                    "baseline": self.baseline,
                    "missing": sorted((key for _, key in bases - paths), key=str),
                    "extra": sorted((key for _, key in paths - bases), key=str),
                },
            )

    def _require_same_cases(self, outcome: str) -> None:
        cases = _case_keys(self.outcomes[outcome], outcome)
        bases = _case_keys(self.outcomes[self.baseline], self.baseline)
        if cases != bases:
            raise ContractError(
                f"{outcome} and {self.baseline} have different cases: "
                "paired differences need the same case keys",
                code=Code.COMPARISON_CASES,
                values={
                    "outcome": outcome,
                    "baseline": self.baseline,
                    "missing": sorted(bases - cases, key=str),
                    "extra": sorted(cases - bases, key=str),
                },
            )

    def _cells(self) -> tuple[list[str], list[list[str]]]:
        if all(len(self.pairs(outcome=name)) == 1 for name in self.compared):
            return self._single()
        table = self.summary()
        return list(table.columns), [
            [_text(row.values[column]) for column in table.columns]
            for row in table.rows
        ]

    def _single(self) -> tuple[list[str], list[list[str]]]:
        """Return the cells of leaf Outcomes: values, then differences."""
        headers = ["key", self.baseline, *self.compared]
        headers += [f"{name} − {self.baseline}" for name in self.compared]
        body = []
        for key in self.keys:
            base = _scalar(self.outcomes[self.baseline], key, self.baseline)
            values = [_scalar(self.outcomes[name], key, name) for name in self.compared]
            differences = [
                self.difference(outcome=name, key=key)[0] for name in self.compared
            ]
            body.append([key, *(_text(item) for item in (base, *values, *differences))])
        return headers, body

    def _repr_html_(self) -> str:
        return render(*self._cells(), html=True)

    def __str__(self) -> str:
        return render(*self._cells(), html=False)

    def __repr__(self) -> str:
        return str(self)


type Group = tuple[object, tuple[Pair, ...]]
"""One group of pairs: its label and its pairs, in pair order."""


@dataclass(frozen=True, kw_only=True, init=False)
class Groups:
    """The pairs of a paired comparison in groups, with the statistics of each group.

    Make it with ``Paired.by(key=)``, which groups the pairs of each compared
    Outcome by its member's value at a key, or ``Paired.by_case``, which
    groups them by case. ``column`` names the group column: the key, or
    ``case``. ``summary()`` gives one row for each compared Outcome, group
    and compared key. It displays as its ``summary()``.
    """

    paired: Paired
    column: str
    _groups: Mapping[str, tuple[Group, ...]] = field(repr=False, compare=False)

    @classmethod
    def _of(
        cls,
        *,
        paired: Paired,
        column: str,
        groups: Mapping[str, tuple[Group, ...]],
    ) -> Self:
        made = object.__new__(cls)
        object.__setattr__(made, "paired", paired)
        object.__setattr__(made, "column", column)
        object.__setattr__(made, "_groups", MappingProxyType(dict(groups)))
        return made

    def summary(self) -> Table:
        """Return the statistics of each group's paired differences.

        The columns are ``outcome``, the group column, then the columns of
        ``Paired.summary()`` from ``key``: ``count``, ``mean``,
        ``standard_deviation``, ``minimum``, ``quantile_05``, ``quantile_95``,
        ``maximum`` and ``share_above_zero``. The rows are in the order of the
        compared Outcomes, then of the groups, then of the compared keys.
        """
        baseline = self.paired.baseline
        rows = [
            _summary_row(
                labels={"outcome": name, self.column: label},
                found=_differences(pairs, key=key, name=name, baseline=baseline),
            )
            for name, groups in self._groups.items()
            for label, pairs in groups
            for key in self.paired.keys
        ]
        return Table(("outcome", self.column, *_SUMMARY), rows)

    def _repr_html_(self) -> str:
        return self.summary()._repr_html_()

    def __repr__(self) -> str:
        count = sum(len(groups) for groups in self._groups.values())
        return f"Groups(column={self.column!r}, groups={count})"


def _outcomes(outcomes: Mapping[str, Compared]) -> Mapping[str, Compared]:
    """Return the named Outcomes after checking their types and number."""
    if not isinstance(outcomes, Mapping):
        raise TypeError("outcomes must be a mapping from names to Outcomes")
    for name, outcome in outcomes.items():
        if not isinstance(name, str) or not name:
            raise TypeError("each Outcome name must be a non-empty string")
        if not isinstance(outcome, (Outcome, Mean)):
            raise TypeError(f"{name} must be an Outcome, or the Mean of one")
    if len(outcomes) < 2:
        raise ContractError(
            "compare takes two or more Outcomes",
            code=Code.CONTRACT,
            values={"count": len(outcomes)},
        )
    return MappingProxyType(dict(outcomes))


def _keys(keys: Sequence[str]) -> tuple[str, ...]:
    """Return the compared keys after checking their types; a key appears once."""
    if isinstance(keys, str):
        raise TypeError("keys must be a list of keys, not one string")
    found = tuple(keys)
    if not found or not all(isinstance(key, str) and key for key in found):
        raise TypeError("keys must be one or more non-empty strings")
    if len(set(found)) != len(found):
        raise ContractError(
            "keys must not repeat",
            code=Code.CONTRACT,
            values={"keys": list(found)},
        )
    return found


def _selected(keys: tuple[str, ...], wanted: tuple[str, ...]) -> tuple[str, ...]:
    """Return the wanted keys, in their order, after checking each one is compared."""
    if not wanted:
        raise TypeError("select takes at least one key")
    for key in wanted:
        _require_key(keys, key)
    return tuple(dict.fromkeys(wanted))


def _require_key(keys: tuple[str, ...], key: str) -> None:
    if key not in keys:
        raise MissingReferenceError(
            key, kind="Value", by="key", where="the comparison", candidates=keys
        )


def _is_batch(outcome: Compared) -> bool:
    """Return whether an Outcome is a batch; a Mean compares as a leaf."""
    return isinstance(outcome, Outcome) and bool(outcome.cases)


def _case_members(outcome: Compared) -> tuple[Member, ...]:
    """Return each leaf case with its case key, or the leaf itself with None."""
    if not isinstance(outcome, Outcome) or not outcome.cases:
        return ((None, outcome),)
    return tuple(("/".join(path), leaf) for path, leaf in outcome._keyed_leaves(()))


def _case_keys(outcome: Compared, name: str) -> set[str | None]:
    """Return the case keys of a batch; two cases with one key cannot pair."""
    keys = [case for case, _ in _case_members(outcome)]
    repeated = sorted({key for key in keys if keys.count(key) > 1}, key=str)
    if repeated:
        raise ContractError(
            f"{name} has more than one case with the key {repeated[0]!r}: "
            "paired differences need a unique key for each case",
            code=Code.COMPARISON_CASES,
            values={"outcome": name, "repeated": repeated},
        )
    return set(keys)


def _across_paths(outcome: Compared) -> bool:
    """Return whether each leaf case of a batch takes a market path."""
    return all(_path(member) is not None for _, member in _case_members(outcome))


def _path(member: Compared) -> PathKey | None:
    """Return the Paths UUID and the path key of a case across market paths, or None.

    The Run of a case across market paths records both (ADR-014).
    """
    if not isinstance(member, Outcome) or member.run.paths is None:
        return None
    return member.run.paths, member.run.path_key


def _paths_of(outcome: Compared, name: str, *, unique: bool) -> set[PathKey]:
    """Return the paths of a batch's cases; with ``unique``, two cases cannot share one."""
    found = [
        path
        for path in (_path(member) for _, member in _case_members(outcome))
        if path is not None
    ]
    repeated = sorted({item[1] for item in found if found.count(item) > 1}, key=str)
    if unique and repeated:
        raise ContractError(
            f"{name} has more than one case on the path {repeated[0]!r}: "
            "paired differences need one case for each path",
            code=Code.COMPARISON_CASES,
            values={"outcome": name, "repeated": repeated},
        )
    return set(found)


def _scalar(outcome: Compared, key: str, name: str | None) -> Quantity:
    value = outcome[key]
    if not isinstance(value, Quantity):
        raise ContractError(
            f"{key} of {name} is not a scalar value; compare scalars",
            code=Code.COMPARISON_SCALAR,
            values={"key": key, "outcome": name},
        )
    return value


def _difference(pair: Pair, *, key: str, name: str, baseline: str) -> Quantity:
    base = _scalar(pair.baseline, key, baseline)
    value = _scalar(pair.member, key, name).to(units=base.units)
    return value - base


def _differences(
    pairs: tuple[Pair, ...],
    *,
    key: str,
    name: str,
    baseline: str,
) -> Distribution[Pair]:
    """Return the distribution of the differences of some pairs on one key."""
    return Distribution._of(
        key=key,
        items=[
            (pair, _difference(pair, key=key, name=name, baseline=baseline))
            for pair in pairs
        ],
    )


def _summary_row(
    *,
    labels: Mapping[str, object],
    found: Distribution[Pair],
) -> dict[str, object]:
    """Return one row of a paired summary: its labels, then the statistics."""
    zero = Quantity(magnitude=0, units=found.units)
    return {
        **labels,
        **found.summary().rows[0].values,
        "share_above_zero": found.probability(above=zero),
    }


def _by_value(pairs: tuple[Pair, ...], *, key: str, name: str) -> tuple[Group, ...]:
    """Return the pairs in groups by their member's value at ``key``, in ascending order."""
    values = [_groupable(pair.member, key=key, name=name) for pair in pairs]
    ascending = sorted(range(len(pairs)), key=lambda index: _ordered(values[index]))
    groups = []
    for _, positions in groupby(ascending, key=lambda index: _ordered(values[index])):
        found = tuple(positions)
        groups.append((values[found[0]], tuple(pairs[index] for index in found)))
    return tuple(groups)


def _by_case(outcome: Compared, pairs: tuple[Pair, ...]) -> tuple[Group, ...]:
    """Return the pairs in groups by the direct case of their member, in case order."""
    if isinstance(outcome, Mean):
        return ((None, pairs),)
    if not outcome.cases:
        return ((outcome.key, pairs),)
    groups = []
    for position, case in enumerate(outcome.cases):
        leaves = {id(leaf) for leaf in case.walk() if not leaf.cases}
        found = tuple(pair for pair in pairs if id(pair.member) in leaves)
        if found:
            groups.append((case.key or str(position), found))
    return tuple(groups)


def _groupable(member: Compared, *, key: str, name: str) -> Quantity | DateValue:
    """Return a member's scalar or date value at ``key``; a Flow cannot group pairs."""
    value = member[key]
    if isinstance(value, (Quantity, date, Never)):
        return value
    raise ContractError(
        f"{key} of {name} is not a scalar or a date value; group by one of them",
        code=Code.COMPARISON_SCALAR,
        values={"key": key, "outcome": name},
    )


def _ordered(value: Quantity | DateValue) -> "SupportsRichComparison":
    """Return a sort key: Quantities by their units and magnitude, then dates."""
    if isinstance(value, Quantity):
        return (0, value.units, value.magnitude)
    return (1, *order(value))


def _matches(value: object, wanted: object) -> bool:
    """Return whether a value equals ``wanted``, or any item of a list of them.

    Quantities compare after unit conversion, within ``isclose``'s defaults.
    """
    if isinstance(wanted, (list, tuple, set, frozenset)):
        return any(_matches(value, item) for item in wanted)
    if isinstance(value, Quantity) and isinstance(wanted, Quantity):
        return isclose(actual=value, expected=wanted)
    return value == wanted


def _text(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.2%}"
    if value is None:
        return "—"
    return str(value)
