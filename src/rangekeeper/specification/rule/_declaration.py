"""The public query of a rule (ADR-021, D42), and its stored record.

``Window(...).where(condition=...).first(otherwise=...)`` returns a ``Rule``. It
holds what the author writes, as text, so it needs no Model. ``fix`` then reads it
against the pinned Model: ``declare`` makes the stored ``RuleRecord``, and
``rule_of`` makes a ``Rule`` from a stored record again. ``query_of`` gives the
rule engine what it reads.
"""

from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID

from rangekeeper.duration import NEVER, Never, Period, PeriodTiming
from rangekeeper.model import Model
from rangekeeper.model.expression import syntax, terms
from rangekeeper.model.expression.text import (
    read,
    render,
    render_condition,
)
from rangekeeper.model.targets import target_units
from rangekeeper.quantity import Quantity
from rangekeeper.schema.enums import DomainKind, ExpressionKind, Operator, ValueKind
from rangekeeper.schema.records import (
    Assignment,
    Expression,
    Movement,
    Reference,
    Value,
)
from rangekeeper.schema.records import Rule as RuleRecord
from rangekeeper.schema.runtime import UNSET, Unset
from rangekeeper.shared.codes import Code
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.shared.errors import ContractError, MissingReferenceError
from rangekeeper.specification.roles import fixed_content
from rangekeeper.specification.rule._query import (
    RuleQuery,
    check_queries,
    names_of,
    parse_condition_text,
    read_targets,
    references,
)
from rangekeeper.specification.targets import checked_quantity

RuleValue = Quantity | str | int | float | Decimal | date | Never
"""What a rule can fix: a date or NEVER for a date Value, else a quantity."""

_CONDITIONS = frozenset(
    {
        Operator.EQUAL,
        Operator.NOT_EQUAL,
        Operator.LESS_THAN,
        Operator.LESS_THAN_OR_EQUAL,
        Operator.GREATER_THAN,
        Operator.GREATER_THAN_OR_EQUAL,
        Operator.LOGICAL_AND,
        Operator.LOGICAL_OR,
        Operator.LOGICAL_NOT,
    }
)


@dataclass(frozen=True, kw_only=True)
class Rule:
    """A query that fixes one value during the solve: ``Window(...).where(...).first(...)``.

    Fix it by key: ``spec.fix(start_date=rule)``. On each path, the value is the
    first window date on which ``condition`` holds (or ``then``), and otherwise
    ``otherwise``. ``triggers`` holds the fixed values that the rule reads, by key,
    when ``Specification.rules`` gives the rule: ``fix`` brings each one that the
    other Specification does not fix.
    """

    window: "Window"
    condition: str
    otherwise: RuleValue
    then: RuleValue | None = None
    triggers: Mapping[str, RuleValue] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class Where:
    """A window with a condition; ``first`` makes it a Rule."""

    window: "Window"
    condition: str

    def first(self, *, otherwise: RuleValue, then: RuleValue | None = None) -> Rule:
        """Return the Rule: the first window date that meets the condition.

        ``then`` is the value on that date; without it, the date itself.
        ``otherwise`` is the value when no window date qualifies. For a date, it
        can be ``rk.duration.NEVER``.
        """
        if otherwise is None:
            raise TypeError("otherwise must be a value")
        return Rule(
            window=self.window,
            condition=self.condition,
            otherwise=otherwise,
            then=then,
        )


@dataclass(frozen=True, kw_only=True)
class Window:
    """The dates on which a rule may act, with optional inclusive bounds.

    Without ``periods``, a window date is each date on which a value that the
    condition reads becomes known. With ``periods``, it is the ``timing`` day of
    each Period. ``earliest`` and ``latest`` are each a date, or date text such as
    ``"shared_start + 1 year"``. ``earliest`` after ``latest``, no Periods, and
    ``timing`` without Periods raise ContractError with ``rule_capability``.
    """

    earliest: date | str | None = None
    latest: date | str | None = None
    periods: Sequence[Period] | None = None
    timing: PeriodTiming = PeriodTiming.FIRST

    def __post_init__(self) -> None:
        for item in (self.earliest, self.latest):
            _check_bound(item)
        if self.periods is not None:
            object.__setattr__(self, "periods", _periods(self.periods))
        if not isinstance(self.timing, PeriodTiming):
            raise TypeError("timing must be a PeriodTiming")
        if self.periods is None and self.timing is not PeriodTiming.FIRST:
            raise _capability("a window with timing needs periods")
        first, last = self.earliest, self.latest
        if isinstance(first, date) and isinstance(last, date) and first > last:
            raise _capability(f"a window has earliest {first} after latest {last}")

    def where(self, *, condition: str) -> Where:
        """Return this window with a condition in the equation language.

        It uses comparisons, ``==`` for equality, ``and``, ``or``, ``not`` and
        ``NEVER``. Text that does not parse raises EquationError; ``fix`` reads
        its names.
        """
        if not isinstance(condition, str):
            raise TypeError("condition must be text")
        syntax.parse_condition(condition)
        return Where(window=self, condition=condition)


class Rules(Mapping[str, Rule]):
    """The rules of a Specification by key, in the order that they run."""

    __slots__ = ("_rules", "_where")

    def __init__(self, *, rules: Mapping[str, Rule], where: str) -> None:
        self._rules = MappingProxyType(dict(rules))
        self._where = where

    def __getitem__(self, key: str) -> Rule:
        """Return the Rule that decides ``key``; no such rule raises MissingReferenceError."""
        if key not in self._rules:
            raise MissingReferenceError(
                key,
                kind="Rule",
                by="key",
                where=self._where,
                candidates=list(self._rules),
            )
        return self._rules[key]

    def __contains__(self, key: object) -> bool:
        return key in self._rules

    def get(self, key: str, default: object = None) -> object:  # type: ignore[override]
        """Return the Rule that decides ``key``, or ``default`` without one."""
        return self._rules.get(key, default)

    def __iter__(self) -> Iterator[str]:
        return iter(self._rules)

    def __len__(self) -> int:
        return len(self._rules)

    def __repr__(self) -> str:
        return f"Rules({dict(self._rules)!r})"


def declare(rule: Rule, *, target: Value, model: Model) -> RuleRecord:
    """Return the stored record of ``rule``, which decides ``target`` in ``model``.

    A name that the Model lacks raises EquationError. A target that is not a date
    or a scalar measurement, a value of the wrong kind and a condition or a bound
    of the wrong kind raise ContractError with ``rule_capability``.
    """
    if target.kind not in (ValueKind.DATE, ValueKind.MEASUREMENT):
        raise _capability(
            f"a rule decides a date or a scalar value, and {target.key} is neither",
            targets=(target.id,),
        )
    window = rule.window
    return RuleRecord(
        target=Reference(target=target.id),
        condition=_condition(rule.condition, model=model),
        otherwise=_literal(rule.otherwise, target=target, model=model),
        then=(
            UNSET
            if rule.then is None
            else _literal(rule.then, target=target, model=model)
        ),
        earliest=_stored_bound(window.earliest, model=model),
        latest=_stored_bound(window.latest, model=model),
        periods=UNSET if window.periods is None else tuple(window.periods),
        timing=UNSET if window.timing is PeriodTiming.FIRST else window.timing,
    )


def query_of(record: RuleRecord) -> RuleQuery:
    """Return what the rule engine reads from one stored rule."""
    return RuleQuery(
        target=record.target.target,
        condition=record.condition,
        otherwise=_content(record.otherwise),
        then=None if record.then is None else _content(record.then),
        earliest=record.earliest,
        latest=record.latest,
        periods=tuple(record.periods) if record.periods else None,
        timing=record.timing or PeriodTiming.FIRST,
    )


def rule_of(
    record: RuleRecord, *, model: Model, assignments: Sequence[Assignment] = ()
) -> Rule:
    """Return the Rule of one stored rule, with the fixed values that it reads.

    ``assignments`` are the fixed values of its Specification.
    """

    def name(reference: Reference) -> str:
        return model.key_of(reference.target)

    window = Window(
        earliest=_bound_of(record.earliest, model=model),
        latest=_bound_of(record.latest, model=model),
        periods=record.periods or None,
        timing=record.timing or PeriodTiming.FIRST,
    )
    return Rule(
        window=window,
        condition=render_condition(expression=record.condition, name=name),
        otherwise=_content(record.otherwise),
        then=None if record.then is None else _content(record.then),
        triggers=_triggers(record, model=model, assignments=assignments),
    )


def path_movements(model: Model) -> frozenset[UUID]:
    """Return each Movement of the Model: what a later ``across`` can fix."""
    return frozenset(
        record.id
        for record in model._index.records.values()
        if isinstance(record, Movement)
    )


def check_declared(
    declared: Sequence[RuleRecord],
    *,
    model: Model,
    fixed: Collection[UUID],
    document_id: UUID,
) -> None:
    """Raise when the stored rules read the future, a later rule or a free input.

    A look-ahead raises AvailabilityError. ``rule_order``, ``rule_reads_unknown``
    and ``rule_capability`` raise ValidationError, whose ``report`` holds the issue.
    """
    try:
        check_queries(
            rules=[query_of(record) for record in declared], model=model, fixed=fixed
        )
    except ContractError as error:
        issue = Issue.from_error(error, document_id=document_id)
        ValidationReport((issue,)).raise_if_invalid()


def _condition(text: str, *, model: Model) -> Expression:
    expression = parse_condition_text(text=text, model=model)
    if expression.kind is not ExpressionKind.BOOLEAN and (
        expression.operator not in _CONDITIONS
    ):
        raise _capability(f"a rule's condition tests a value, and {text!r} does not")
    return expression


def _stored_bound(bound: date | str | None, *, model: Model) -> Expression | Unset:
    """Return the Expression of a bound, or UNSET without one."""
    if bound is None:
        return UNSET
    if isinstance(bound, date):
        return terms.constant(bound).to_expression()
    term = read(text=bound, names=names_of(model))
    if term.kind is not DomainKind.DATE:
        raise _capability(f"a window bound is a date, and {bound!r} is not")
    return term.to_expression()


def _bound_of(node: Expression | None, *, model: Model) -> date | str | None:
    if node is None:
        return None
    if node.kind is ExpressionKind.DATE and node.date is not None:
        return node.date
    return render(expression=node, name=lambda item: model.key_of(item.target))


def _literal(value: RuleValue, *, target: Value, model: Model) -> Expression:
    """Return the literal that fixes ``target``: a date or NEVER, or a quantity."""
    dated = value is NEVER or (
        isinstance(value, date) and not isinstance(value, datetime)
    )
    if target.kind is ValueKind.DATE:
        if not dated:
            raise _capability(
                f"{target.key} is a date Value: a rule fixes it to a date or NEVER",
                targets=(target.id,),
            )
        assert isinstance(value, (date, Never))
        return terms.constant(value).to_expression()
    if dated:
        raise _capability(
            f"a date fixes a date Value, and {target.key} is not one",
            targets=(target.id,),
        )
    quantity = checked_quantity(
        value,
        target=target.key,
        units=target_units(model, Reference(target=target.id)),
        unit_system=model.unit_system,
    )
    return terms.quantity(quantity).to_expression()


def _content(node: Expression) -> Quantity | date | Never:
    """Return the value of a literal; another Expression raises ContractError."""
    if node.kind is ExpressionKind.QUANTITY and node.quantity is not None:
        return node.quantity
    if node.kind is ExpressionKind.DATE:
        if node.never is not None:
            return NEVER
        if node.date is not None:
            return node.date
    raise _capability("a rule's otherwise and then are literal values")


def _triggers(
    record: RuleRecord, *, model: Model, assignments: Sequence[Assignment]
) -> Mapping[str, RuleValue]:
    fixed = {item.target.target: item for item in assignments}
    reads = dict.fromkeys(read_targets(record.condition))
    for bound in (record.earliest, record.latest):
        if bound is not None:
            reads.update(dict.fromkeys(references(bound)))
    return {
        model.key_of(token): fixed_content(fixed[token])  # type: ignore[misc]
        for token in reads
        if token in fixed
    }


def _check_bound(bound: object) -> None:
    if bound is None:
        return
    # NEVER is text in Python, and a bound of NEVER is no window at all.
    is_text = isinstance(bound, str) and bound is not NEVER
    is_date = isinstance(bound, date) and not isinstance(bound, datetime)
    if not is_text and not is_date:
        raise TypeError("earliest and latest must each be a date or text")


def _periods(periods: Sequence[Period]) -> tuple[Period, ...]:
    if isinstance(periods, (str, bytes)) or not isinstance(periods, Sequence):
        raise TypeError("periods must be a sequence of Periods")
    found = tuple(periods)
    if not all(isinstance(item, Period) for item in found):
        raise TypeError("periods must be a sequence of Periods")
    if not found:
        raise _capability("a window with periods needs at least one Period")
    return found


def _capability(message: str, *, targets: tuple[UUID, ...] = ()) -> ContractError:
    return ContractError(message, code=Code.RULE_CAPABILITY, targets=targets)


__all__ = [
    "Rule",
    "RuleValue",
    "Rules",
    "Where",
    "Window",
    "check_declared",
    "declare",
    "path_movements",
    "query_of",
    "rule_of",
]
