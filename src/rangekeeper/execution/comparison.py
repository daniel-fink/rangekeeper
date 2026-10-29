"""Compare two or more Outcomes with one call: side by side, or paired with a baseline."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from rangekeeper.execution.outcome import Outcome
from rangekeeper.quantity import Quantity, isclose
from rangekeeper.shared.table import Table


def compare(
    *,
    outcomes: Mapping[str, Outcome],
    keys: Sequence[str],
    baseline: str | None = None,
) -> "Comparison":
    """Return the Comparison of two or more named Outcomes on ``keys``.

    Without ``baseline``, the Comparison shows the values side by side. With
    ``baseline``, the name of one of the Outcomes, it gives each other
    Outcome's differences from the baseline, paired case by case. The call is
    the same for two Outcomes and for more.
    """
    if not isinstance(outcomes, Mapping):
        raise TypeError("outcomes must be a mapping from names to Outcomes")
    if len(outcomes) < 2:
        raise ValueError("compare takes two or more Outcomes")
    for name, outcome in outcomes.items():
        if not isinstance(name, str) or not name:
            raise TypeError("each Outcome name must be a non-empty string")
        if not isinstance(outcome, Outcome):
            raise TypeError(f"{name} must be an Outcome")
    if isinstance(keys, str):
        raise TypeError("keys must be a list of keys, not one string")
    keys = tuple(keys)
    if not keys or not all(isinstance(key, str) and key for key in keys):
        raise TypeError("keys must be one or more non-empty strings")
    if len(set(keys)) != len(keys):
        raise ValueError("keys must not repeat")
    if baseline is not None and baseline not in outcomes:
        raise KeyError(
            f"baseline {baseline!r} is not one of the Outcomes: "
            + ", ".join(repr(name) for name in outcomes)
        )
    comparison = Comparison(MappingProxyType(dict(outcomes)), keys, baseline)
    comparison._check()
    return comparison


Member = tuple[int | None, Outcome]
"""One leaf case of an Outcome with its position, or a leaf Outcome with None."""


@dataclass(frozen=True)
class Pair:
    """One Outcome member and the baseline member that it is paired with.

    ``case`` is the position of the member's case in its batch, in ``walk()``
    order, or None for a leaf Outcome that pairs with every baseline member.
    """

    case: int | None
    member: Outcome
    baseline: Outcome


@dataclass(frozen=True)
class Comparison:
    """The values of named Outcomes on some keys, side by side or paired.

    Make it with ``rk.execution.compare``. Without a baseline, ``values``
    gives one row for each key and one column for each Outcome. With a
    baseline, ``differences`` gives one row for each Outcome, key and pair,
    and ``summary()`` gives the statistics of the paired differences.

    Each member of an Outcome is one leaf case, in ``walk()`` order; a leaf
    Outcome has one member. Members pair by case position. A leaf pairs with
    every member of the other side.

    A Comparison displays as a table (with the ``calculations`` extra): the
    values side by side; with a baseline, the values and differences of leaf
    Outcomes, or the ``summary()`` of batches.
    """

    outcomes: Mapping[str, Outcome]
    keys: tuple[str, ...]
    baseline: str | None = None
    members: Mapping[str, tuple[Member, ...]] = field(
        default_factory=lambda: MappingProxyType({}), repr=False
    )

    def __post_init__(self) -> None:
        if not self.members:
            object.__setattr__(
                self,
                "members",
                MappingProxyType(
                    {name: _members(item) for name, item in self.outcomes.items()}
                ),
            )

    def _check(self) -> None:
        if self.baseline is None:
            for name, outcome in self.outcomes.items():
                if outcome.cases:
                    raise TypeError(
                        f"{name} is a batch: compare it with baseline=, "
                        "or compare one of its cases"
                    )
        else:
            for name in self.compared:
                self.pairs(outcome=name)
        for name, members in self.members.items():
            for _, member in members:
                for key in self.keys:
                    _scalar(member, key, name)

    @property
    def compared(self) -> tuple[str, ...]:
        """Return the names of the Outcomes that are not the baseline, in order."""
        return tuple(name for name in self.outcomes if name != self.baseline)

    @property
    def values(self) -> Table:
        """Return the values side by side: a ``key`` column, then one per Outcome.

        Without a baseline only; each cell is the Outcome's Quantity.
        """
        if self.baseline is not None:
            raise TypeError("a Comparison with a baseline has differences, not values")
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

    def pairs(self, *, outcome: str) -> tuple[Pair, ...]:
        """Return the pairs of one compared Outcome with the baseline, in case order.

        Members pair by case position; a leaf on either side pairs with each
        member of the other. Batches with different cases raise ValueError.
        """
        if self.baseline is None:
            raise TypeError("pairs need a baseline")
        if outcome not in self.compared:
            raise KeyError(f"{outcome!r} is not a compared Outcome")
        members = self.members[outcome]
        bases = self.members[self.baseline]
        if bases[0][0] is None:  # a leaf baseline pairs with every member
            return tuple(Pair(case, member, bases[0][1]) for case, member in members)
        if members[0][0] is None:  # a leaf pairs with every baseline member
            return tuple(Pair(case, members[0][1], base) for case, base in bases)
        cases = dict(bases)
        if len(_members(self.outcomes[outcome])) != len(
            _members(self.outcomes[self.baseline])
        ) or any(case not in cases for case, _ in members):
            raise ValueError(
                f"{outcome} and {self.baseline} have different cases: "
                "paired differences need the same cases"
            )
        return tuple(Pair(case, member, cases[case]) for case, member in members)

    def difference(self, *, outcome: str, key: str) -> tuple[Quantity, ...]:
        """Return the paired differences of one Outcome on one key, in pair order.

        Each difference is the Outcome's value less the baseline's value, in
        the baseline's units.
        """
        if key not in self.keys:
            raise KeyError(f"{key!r} is not a compared key")
        return tuple(
            _difference(pair, key, outcome, self.baseline)
            for pair in self.pairs(outcome=outcome)
        )

    @property
    def differences(self) -> Table:
        """Return one row for each compared Outcome, key and pair.

        The columns are ``outcome``, ``key``, ``case``, ``value``,
        ``baseline`` and ``difference``.
        """
        self._require_baseline()
        rows = []
        for name in self.compared:
            for pair in self.pairs(outcome=name):
                for key in self.keys:
                    rows.append(
                        {
                            "outcome": name,
                            "key": key,
                            "case": pair.case,
                            "value": _scalar(pair.member, key, name),
                            "baseline": _scalar(pair.baseline, key, self.baseline),
                            "difference": _difference(pair, key, name, self.baseline),
                        }
                    )
        return Table(
            ("outcome", "key", "case", "value", "baseline", "difference"), rows
        )

    def summary(self) -> Table:
        """Return the statistics of the paired differences of each Outcome and key.

        The columns are ``outcome``, ``key``, ``count``, ``mean``, ``minimum``,
        ``maximum`` and ``share_above_zero``: the share of pairs whose
        difference is above zero.
        """
        self._require_baseline()
        rows = []
        for name in self.compared:
            for key in self.keys:
                found = self.difference(outcome=name, key=key)
                zero = Quantity(magnitude=0, units=found[0].units)
                rows.append(
                    {
                        "outcome": name,
                        "key": key,
                        "count": len(found),
                        "mean": sum(found[1:], found[0]) / len(found),
                        "minimum": min(found, key=_number),
                        "maximum": max(found, key=_number),
                        "share_above_zero": sum(1 for item in found if item > zero)
                        / len(found),
                    }
                )
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

    def select(self, *keys: str) -> "Comparison":
        """Return the same Comparison on some of its keys, in the order given."""
        if not keys:
            raise TypeError("select takes at least one key")
        missing = [key for key in keys if key not in self.keys]
        if missing:
            raise KeyError(f"{missing[0]!r} is not a compared key")
        return replace(self, keys=tuple(dict.fromkeys(keys)))

    def where(self, **values: object) -> "Comparison":
        """Return the Comparison of the pairs whose compared member has these values.

        Name each value by its key: ``where(b_design="hotel")`` keeps the pairs
        where the compared Outcome's value equals it, and a list keeps any of
        its items (D40). Quantities compare after unit conversion. The
        baseline keeps all its members.
        """
        self._require_baseline()
        if not values:
            raise TypeError("where takes at least one key")
        members = dict(self.members)
        for name in self.compared:
            kept = tuple(
                (case, member)
                for case, member in members[name]
                if all(_matches(member[key], wanted) for key, wanted in values.items())
            )
            if not kept:
                raise ValueError(f"no case of {name} has these values")
            members[name] = kept
        return replace(self, members=MappingProxyType(members))

    def _require_baseline(self) -> None:
        if self.baseline is None:
            raise TypeError("differences need a baseline; compare with baseline=")

    def _cells(self) -> tuple[list[str], list[list[str]]]:
        if self.baseline is None:
            table = self.values
            headers = list(table.columns)
            body = [
                [str(row.values["key"])]
                + [_text(row.values[name]) for name in self.outcomes]
                for row in table.rows
            ]
            return headers, body
        single = all(len(self.pairs(outcome=name)) == 1 for name in self.compared)
        if single:
            headers = ["key", self.baseline, *self.compared]
            headers += [f"{name} − {self.baseline}" for name in self.compared]
            body = []
            for key in self.keys:
                base = _scalar(self.outcomes[self.baseline], key, self.baseline)
                values = [
                    _scalar(self.outcomes[name], key, name) for name in self.compared
                ]
                body.append(
                    [key, _text(base)]
                    + [_text(value) for value in values]
                    + [
                        _text(self.difference(outcome=n, key=key)[0])
                        for n in self.compared
                    ]
                )
            return headers, body
        table = self.summary()
        return list(table.columns), [
            [_text(row.values[column]) for column in table.columns]
            for row in table.rows
        ]

    def _repr_html_(self) -> str:
        from rangekeeper.flow._table import render

        return render(*self._cells(), html=True)

    def __str__(self) -> str:
        from rangekeeper.flow._table import render

        return render(*self._cells(), html=False)

    def __repr__(self) -> str:
        return str(self)


def _members(outcome: Outcome) -> tuple[Member, ...]:
    """Return each leaf case with its position, or the leaf itself with None."""
    if not outcome.cases:
        return ((None, outcome),)
    leaves = [item for item in outcome.walk() if not item.cases]
    return tuple(enumerate(leaves))


def _scalar(outcome: Outcome, key: str, name: str | None) -> Quantity:
    value = outcome[key]
    if not isinstance(value, Quantity):
        raise TypeError(f"{key} of {name} is not a scalar value; compare scalars")
    return value


def _difference(pair: Pair, key: str, name: str, baseline: str | None) -> Quantity:
    base = _scalar(pair.baseline, key, baseline)
    value = _scalar(pair.member, key, name).to(units=base.units)
    return value - base


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
