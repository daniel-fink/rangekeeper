"""The tokens of equation text, each with its position in the text.

A token is a number, a name or a symbol. Names include the words of the text
form (``and``, ``or``, ``not``, ``True``, ``False``, ``NEVER``) and unit words;
the parser gives them their meaning. Symbols that equation text does not use,
such as ``==`` and ``&``, are tokens too, so that the parser can suggest the
right spelling.
"""

import re
from dataclasses import dataclass
from enum import Enum

from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import EquationError


class TokenKind(Enum):
    """The kind of a token."""

    NUMBER = "number"
    NAME = "name"
    SYMBOL = "symbol"
    END = "end"


@dataclass(frozen=True, slots=True, kw_only=True)
class Token:
    """One token: ``text[start:end]`` of the equation text is ``text``."""

    kind: TokenKind
    text: str
    start: int
    end: int


# The number syntax of quantity text: digits, a decimal point and an exponent.
_NUMBER = r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
# A Python identifier, including letters outside ASCII.
_NAME = r"[^\W\d]\w*"
# Longer symbols first, so that "**" is one token and not two "*".
_SYMBOLS = (
    "**",
    "<=",
    ">=",
    "!=",
    "==",
    "=",
    "<",
    ">",
    "+",
    "-",
    "*",
    "/",
    "%",
    "(",
    ")",
    ",",
    ".",
    "&",
    "|",
    "~",
    "^",
)
_TOKEN = re.compile(
    rf"(?P<number>{_NUMBER})|(?P<name>{_NAME})"
    rf"|(?P<symbol>{'|'.join(re.escape(symbol) for symbol in _SYMBOLS)})"
)


def tokenize(text: str) -> tuple[Token, ...]:
    """Return the tokens of ``text``; the last token is an END token.

    A character that starts no token raises EquationError with the code
    ``EQUATION_SYNTAX`` and its position.
    """
    tokens: list[Token] = []
    position = _skip_space(text, 0)
    while position < len(text):
        match = _TOKEN.match(text, position)
        if match is None or match.lastgroup is None:
            raise EquationError(
                f"unexpected character {text[position]!r}",
                code=Code.EQUATION_SYNTAX,
                text=text,
                start=position,
                end=position + 1,
            )
        tokens.append(
            Token(
                kind=TokenKind(match.lastgroup),
                text=match.group(),
                start=position,
                end=match.end(),
            )
        )
        position = _skip_space(text, match.end())
    tokens.append(Token(kind=TokenKind.END, text="", start=len(text), end=len(text)))
    return tuple(tokens)


def _skip_space(text: str, position: int) -> int:
    """Return the first position at or after ``position`` that is not a space."""
    while position < len(text) and text[position].isspace():
        position += 1
    return position


__all__ = ["Token", "TokenKind", "tokenize"]
