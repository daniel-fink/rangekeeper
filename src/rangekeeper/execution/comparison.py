"""Compare two or more Outcomes with one call: side by side, or paired with a baseline.

``compare`` returns a ``SideBySide`` without a baseline and a ``Paired`` with
one, so that each result has only the members that apply to it. The cases of
two batches pair by case key.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Self, overload

from rangekeeper.execution.outcome import Outcome
from rangekeeper.flow._table import render
from rangekeeper.quantity import Quantity, isclose
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, MissingReferenceError
from rangekeeper.shared.table import Table

Member = tuple[str | None, Outcome]
"""One leaf case of an Outcome with its case key, or a leaf Outcome with None."""


@overload
def compare(
    *,
    outcomes: Mapping[str, Outcome],
    keys: Sequence[str],
    baseline: None = None,
) -> "SideBySide": ...


@overload
def compare(
    *,
    outcomes: Mapping[str, Outcome],
    keys: Sequence[str],
    baseline: str,
) -> "Paired": ...


def compare(
    *,
    outcomes: Mapping[str, Outcome],
    keys: Sequence[str],
    baseline: str | None = None,
) -> "SideBySide | Paired":
    """Compare two or more named Outcomes on ``keys``.

    Without ``baseline``, return a ``SideBySide`` of the values. With
    ``baseline``, the name of one of the Outcomes, return a ``Paired``: each
    other Outcome's differences from the baseline, paired case by case. The
    call is the same for two Outcomes and for more.
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


@dataclass(frozen=True)
class Pair:
    """One Outcome member and the baseline member that it is paired with.

    ``case`` is the case key of the pair, as in the ``case`` column of
    ``Outcome.table``: the keys of nested batches joined by ``/``. It is None
    when both sides are leaf Outcomes.
    """

    case: str | None
    member: Outcome
    baseline: Outcome


@dataclass(frozen=True, init=False)
class SideBySide:
    """The values of named leaf Outcomes on some keys, side by side.

    Make it with ``rk.execution.compare`` without a baseline. ``values`` gives
    one row for each key and one column for each Outcome. It displays as a
    table (with the ``calculations`` extra).
    """

    outcomes: Mapping[str, Outcome]
    keys: tuple[str, ...]

    @classmethod
    def _of(cls, outcomes: Mapping[str, Outcome], keys: tuple[str, ...]) -> Self:
        for name, outcome in outcomes.items():
            if outcome.cases:
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


@dataclass(frozen=True, init=False)
class Paired:
    """The paired differences of named Outcomes from a baseline, on some keys.

    Make it with ``rk.execution.compare(..., baseline=)``. ``differences``
    gives one row for each Outcome, key and pair, and ``summary()`` the
    statistics of the paired differences.

    Each member of an Outcome is one leaf case, in ``walk()`` order; a leaf
    Outcome has one member. The members of two batches pair by case key, and
    the batches must have the same case keys. A leaf pairs with every member
    of the other side.

    It displays as a table (with the ``calculations`` extra): the values and
    differences of leaf Outcomes, or the ``summary()`` of batches.
    """

    outcomes: Mapping[str, Outcome]
    keys: tuple[str, ...]
    baseline: str
    _members: Mapping[str, tuple[Member, ...]] = field(repr=False, compare=False)

    @classmethod
    def _of(
        cls,
        outcomes: Mapping[str, Outcome],
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
        outcomes: Mapping[str, Outcome],
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

        Members of two batches pair by case key; a leaf on either side pairs
        with each member of the other. Batches with different case keys, or
        with a key that two cases share, raise ContractError
        (``comparison.cases``).
        """
        members = self._members[self._compared(outcome)]
        bases = self._members[self.baseline]
        if bases[0][0] is None:  # a leaf baseline pairs with every member
            return tuple(Pair(case, member, bases[0][1]) for case, member in members)
        if members[0][0] is None:  # a leaf pairs with every baseline member
            return tuple(Pair(case, members[0][1], base) for case, base in bases)
        self._require_same_cases(outcome)
        by_case = dict(bases)
        return tuple(Pair(case, member, by_case[case]) for case, member in members)

    def difference(self, *, outcome: str, key: str) -> tuple[Quantity, ...]:
        """Return the paired differences of one Outcome on one key, in pair order.

        Each difference is the Outcome's value less the baseline's value, in
        the baseline's units.
        """
        _require_key(self.keys, key)
        return tuple(
            _difference(pair, key=key, name=outcome, baseline=self.baseline)
            for pair in self.pairs(outcome=outcome)
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

        The columns are ``outcome``, ``key``, ``count``, ``mean``, ``minimum``,
        ``maximum`` and ``share_above_zero``: the share of pairs whose
        difference is above zero.
        """
        rows = [
            _statistics(name, key, self.difference(outcome=name, key=key))
            for name in self.compared
            for key in self.keys
        ]
        return Table(
            (
                "outcome",
                "key",
                "count",
                "mean",
                "minimum",
                "maximum",
                "share_above_zero",
            ),
            rows,
        )

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


def _outcomes(outcomes: Mapping[str, Outcome]) -> Mapping[str, Outcome]:
    """Return the named Outcomes after checking their types and number."""
    if not isinstance(outcomes, Mapping):
        raise TypeError("outcomes must be a mapping from names to Outcomes")
    for name, outcome in outcomes.items():
        if not isinstance(name, str) or not name:
            raise TypeError("each Outcome name must be a non-empty string")
        if not isinstance(outcome, Outcome):
            raise TypeError(f"{name} must be an Outcome")
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


def _case_members(outcome: Outcome) -> tuple[Member, ...]:
    """Return each leaf case with its case key, or the leaf itself with None."""
    if not outcome.cases:
        return ((None, outcome),)
    return tuple(("/".join(path), leaf) for path, leaf in outcome._keyed_leaves(()))


def _case_keys(outcome: Outcome, name: str) -> set[str | None]:
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


def _scalar(outcome: Outcome, key: str, name: str | None) -> Quantity:
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


def _statistics(name: str, key: str, found: tuple[Quantity, ...]) -> dict[str, Any]:
    """Return one summary row: the statistics of the differences on one key."""
    zero = Quantity(magnitude=0, units=found[0].units)
    return {
        "outcome": name,
        "key": key,
        "count": len(found),
        "mean": sum(found[1:], found[0]) / len(found),
        "minimum": min(found, key=_number),
        "maximum": max(found, key=_number),
        "share_above_zero": sum(1 for item in found if item > zero) / len(found),
    }


def _matches(value: object, wanted: object) -> bool:
    """Return whether a value equals ``wanted``, or any item of a list of them.

    Quantities compare after unit conversion, within ``isclose``'s defaults.
    """
    if isinstance(wanted, (list, tuple, set, frozenset)):
        return any(_matches(value, item) for item in wanted)
    if isinstance(value, Quantity) and isinstance(wanted, Quantity):
        return isclose(actual=value, expected=wanted)
    return value == wanted


def _number(quantity: Quantity) -> float:
    return float(quantity.magnitude)


def _text(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.2%}"
    if value is None:
        return "—"
    return str(value)
