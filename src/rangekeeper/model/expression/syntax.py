"""The grammar of equation text: its operators, its syntax tree and its parser.

The grammar is Python's expression grammar, with the changes of ADR-015 (D32):
``=`` is equality, ``and``, ``or`` and ``not`` are the logical operators, a
number followed by unit words is a quantity literal, and ``NEVER`` is a
constant. ``parse`` makes a syntax tree in which each node has its position in
the text. ``rangekeeper.model.expression.text`` makes Expression records from
the tree, and writes records back as text with the same operator table.
"""

from dataclasses import dataclass
from enum import IntEnum
from keyword import iskeyword

from rangekeeper.model.expression.tokens import Token, TokenKind, tokenize
from rangekeeper.schema.enums import Operator
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import EquationError


class Precedence(IntEnum):
    """How tightly an operator binds its operands; a higher level binds tighter.

    The order is Python's: ``or``, ``and``, ``not``, the comparisons, ``+`` and
    ``-``, ``*`` and ``/``, negation, then ``**``.
    """

    NONE = 0
    OR = 1
    AND = 2
    NOT = 3
    COMPARISON = 4
    SUM = 5
    PRODUCT = 6
    NEGATION = 7
    POWER = 8
    ATOM = 9


@dataclass(frozen=True, slots=True)
class Spelling:
    """How equation text writes one operator, and how tightly it binds."""

    symbol: str
    operator: Operator
    precedence: Precedence


# The operators between two operands, by their symbol or word.
INFIX: dict[str, Spelling] = {
    spelling.symbol: spelling
    for spelling in (
        Spelling("or", Operator.LOGICAL_OR, Precedence.OR),
        Spelling("and", Operator.LOGICAL_AND, Precedence.AND),
        Spelling("=", Operator.EQUAL, Precedence.COMPARISON),
        Spelling("!=", Operator.NOT_EQUAL, Precedence.COMPARISON),
        Spelling("<", Operator.LESS_THAN, Precedence.COMPARISON),
        Spelling("<=", Operator.LESS_THAN_OR_EQUAL, Precedence.COMPARISON),
        Spelling(">", Operator.GREATER_THAN, Precedence.COMPARISON),
        Spelling(">=", Operator.GREATER_THAN_OR_EQUAL, Precedence.COMPARISON),
        Spelling("+", Operator.ADD, Precedence.SUM),
        Spelling("-", Operator.SUBTRACT, Precedence.SUM),
        Spelling("*", Operator.MULTIPLY, Precedence.PRODUCT),
        Spelling("/", Operator.DIVIDE, Precedence.PRODUCT),
        Spelling("**", Operator.POWER, Precedence.POWER),
    )
}
# The operators before one operand.
PREFIX: dict[str, Spelling] = {
    spelling.symbol: spelling
    for spelling in (
        Spelling("not", Operator.LOGICAL_NOT, Precedence.NOT),
        Spelling("-", Operator.NEGATE, Precedence.NEGATION),
    )
}
# The spelling of each operator, for writing records as text.
SPELLINGS: dict[Operator, Spelling] = {
    spelling.operator: spelling for spelling in (*INFIX.values(), *PREFIX.values())
}
# Python spellings that equation text writes in another way.
MISSPELLINGS = {"==": "=", "&": "and", "|": "or", "~": "not", "^": "**"}
# The words that name constants.
TRUE = "True"
FALSE = "False"
NEVER = "NEVER"
CONSTANTS = frozenset({TRUE, FALSE, NEVER})


@dataclass(frozen=True, slots=True, kw_only=True)
class Node:
    """A node of the syntax tree; ``text[start:end]`` is its source text."""

    start: int
    end: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Literal(Node):
    """A number, with the unit words that follow it.

    ``units`` is None for a bare number. The unit words start at ``units_start``.
    """

    number: str
    units: str | None
    units_start: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Constant(Node):
    """``True``, ``False`` or ``NEVER``."""

    word: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Name(Node):
    """A name: a value key, an entity code, or ``rx`` before a function name."""

    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Member(Node):
    """``base.name``: a key of another entity, a function name or a method."""

    base: Node
    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Argument(Node):
    """One argument of a call; ``name`` is None for a positional argument."""

    name: str | None
    value: Node


@dataclass(frozen=True, slots=True, kw_only=True)
class Call(Node):
    """A call of a function or a method, with its arguments in order."""

    callee: Node
    arguments: tuple[Argument, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Unary(Node):
    """An operator before one operand: negation or ``not``."""

    operator: Operator
    operand: Node


@dataclass(frozen=True, slots=True, kw_only=True)
class Binary(Node):
    """An operator between two operands."""

    operator: Operator
    left: Node
    right: Node


def parse(text: str) -> Node:
    """Return the syntax tree of equation text.

    Text that does not parse raises EquationError with the code
    ``EQUATION_SYNTAX`` and the position of the part that fails.
    """
    if not text.strip():
        raise _error("equation text is empty", text=text, start=0, end=len(text))
    return _Parser(text).parse()


def path(node: Node) -> tuple[str, ...] | None:
    """Return the names of ``a.b.c`` in order, or None if a part is not a name."""
    if isinstance(node, Name):
        return (node.name,)
    if isinstance(node, Member):
        base = path(node.base)
        return None if base is None else (*base, node.name)
    return None


class _Parser:
    """A precedence-climbing parser over the tokens of one equation text."""

    __slots__ = ("_text", "_tokens", "_index")

    def __init__(self, text: str) -> None:
        self._text = text
        self._tokens = tokenize(text)
        self._index = 0

    def parse(self) -> Node:
        node = self._expression(Precedence.NONE)
        token = self._peek()
        if token.kind is not TokenKind.END:
            raise self._unexpected(token)
        return node

    def _expression(self, floor: Precedence) -> Node:
        """Parse an operand and the operators after it that bind above ``floor``.

        A comparison does not chain: ``a < b < c`` raises EquationError.
        """
        left = self._prefix()
        compared = False
        while (spelling := self._infix(self._peek())) is not None:
            if spelling.precedence <= floor:
                break
            if spelling.precedence is Precedence.COMPARISON:
                if compared:
                    raise self._chained(self._peek())
                compared = True
            self._advance()
            # ``**`` groups to the right; the other operators group to the left.
            right = self._expression(
                Precedence(spelling.precedence - 1)
                if spelling.operator is Operator.POWER
                else spelling.precedence
            )
            left = Binary(
                start=left.start,
                end=right.end,
                operator=spelling.operator,
                left=left,
                right=right,
            )
        return left

    def _infix(self, token: Token) -> Spelling | None:
        """Return the operator that ``token`` writes between operands, if any."""
        if token.kind is TokenKind.SYMBOL and token.text in MISSPELLINGS:
            raise self._misspelled(token)
        if token.kind in (TokenKind.SYMBOL, TokenKind.NAME):
            return INFIX.get(token.text)
        return None

    def _prefix(self) -> Node:
        token = self._peek()
        spelling = (
            PREFIX.get(token.text) if token.kind is not TokenKind.NUMBER else None
        )
        if spelling is None:
            return self._postfix(self._atom())
        self._advance()
        operand = self._expression(Precedence(spelling.precedence - 1))
        return Unary(
            start=token.start,
            end=operand.end,
            operator=spelling.operator,
            operand=operand,
        )

    def _atom(self) -> Node:
        token = self._advance()
        if token.kind is TokenKind.NUMBER:
            return self._literal(token)
        if token.kind is TokenKind.NAME:
            return self._word(token)
        if token.text == "(":
            node = self._expression(Precedence.NONE)
            self._expect(")", opened=token)
            return node
        if token.text in MISSPELLINGS:
            raise self._misspelled(token)
        raise self._unexpected(token)

    def _literal(self, number: Token) -> Literal:
        """Read a number and the unit words after it: names, ``%`` and ``per``."""
        words: list[Token] = []
        while _unit_word(self._peek()):
            words.append(self._advance())
        return Literal(
            start=number.start,
            end=words[-1].end if words else number.end,
            number=number.text,
            units=" ".join(word.text for word in words) if words else None,
            units_start=words[0].start if words else number.end,
        )

    def _word(self, token: Token) -> Node:
        if token.text in CONSTANTS:
            return Constant(start=token.start, end=token.end, word=token.text)
        if token.text in INFIX:
            raise self._unexpected(token)
        if iskeyword(token.text):
            raise _error(
                f"{token.text!r} is a Python keyword; equation text does not use it",
                text=self._text,
                start=token.start,
                end=token.end,
            )
        return Name(start=token.start, end=token.end, name=token.text)

    def _postfix(self, node: Node) -> Node:
        """Read the members and calls after an operand: ``a.b`` and ``f(...)``."""
        while self._peek().text in (".", "("):
            token = self._advance()
            if token.text == "(":
                node = self._call(node, opened=token)
                continue
            name = self._advance()
            if name.kind is not TokenKind.NAME or iskeyword(name.text):
                raise self._unexpected(name)
            node = Member(start=node.start, end=name.end, base=node, name=name.text)
        return node

    def _call(self, callee: Node, *, opened: Token) -> Call:
        arguments: list[Argument] = []
        while self._peek().text != ")":
            arguments.append(self._argument(arguments))
            if self._peek().text != ",":
                break
            self._advance()
        closing = self._expect(")", opened=opened)
        return Call(
            start=callee.start,
            end=closing.end,
            callee=callee,
            arguments=tuple(arguments),
        )

    def _argument(self, before: list[Argument]) -> Argument:
        """Read one argument: ``name=value`` or a positional value."""
        token = self._peek()
        if token.kind is TokenKind.NAME and self._peek(1).text == "=":
            if any(argument.name == token.text for argument in before):
                raise _error(
                    f"argument {token.text!r} is given twice",
                    text=self._text,
                    start=token.start,
                    end=token.end,
                )
            self._advance()
            self._advance()
            value = self._expression(Precedence.NONE)
            return Argument(
                start=token.start, end=value.end, name=token.text, value=value
            )
        value = self._expression(Precedence.NONE)
        if any(argument.name is not None for argument in before):
            raise _error(
                "a positional argument follows a named argument",
                text=self._text,
                start=value.start,
                end=value.end,
            )
        return Argument(start=value.start, end=value.end, name=None, value=value)

    def _peek(self, ahead: int = 0) -> Token:
        return self._tokens[min(self._index + ahead, len(self._tokens) - 1)]

    def _advance(self) -> Token:
        token = self._peek()
        self._index = min(self._index + 1, len(self._tokens) - 1)
        return token

    def _expect(self, symbol: str, *, opened: Token) -> Token:
        token = self._peek()
        if token.text != symbol or token.kind is not TokenKind.SYMBOL:
            raise _error(
                f"expected {symbol!r}; a {opened.text!r} is not closed",
                text=self._text,
                start=token.start,
                end=token.end,
            )
        return self._advance()

    def _unexpected(self, token: Token) -> EquationError:
        if token.kind is TokenKind.END:
            return _error(
                "the text ends where an operand is expected",
                text=self._text,
                start=token.start,
                end=token.end,
            )
        return _error(
            f"unexpected {token.text!r}",
            text=self._text,
            start=token.start,
            end=token.end,
        )

    def _misspelled(self, token: Token) -> EquationError:
        spelling = MISSPELLINGS[token.text]
        return _error(
            f"equation text writes {spelling!r}, not {token.text!r}",
            text=self._text,
            start=token.start,
            end=token.end,
            suggestions=(spelling,),
        )

    def _chained(self, token: Token) -> EquationError:
        return _error(
            f"comparisons do not chain; join them with 'and' before {token.text!r}",
            text=self._text,
            start=token.start,
            end=token.end,
            suggestions=("and",),
        )


def _unit_word(token: Token) -> bool:
    """Return whether ``token`` can be a word of a literal's units."""
    if token.kind is TokenKind.SYMBOL:
        return token.text == "%"
    return (
        token.kind is TokenKind.NAME
        and not iskeyword(token.text)
        and token.text not in CONSTANTS
    )


def _error(
    message: str,
    *,
    text: str,
    start: int,
    end: int,
    suggestions: tuple[str, ...] = (),
) -> EquationError:
    return EquationError(
        message,
        code=Code.EQUATION_SYNTAX,
        text=text,
        start=start,
        end=end,
        suggestions=suggestions,
    )


__all__ = [
    "Argument",
    "Binary",
    "Call",
    "Constant",
    "Literal",
    "Member",
    "Name",
    "Node",
    "Precedence",
    "Spelling",
    "Unary",
    "INFIX",
    "PREFIX",
    "SPELLINGS",
    "parse",
    "path",
]
