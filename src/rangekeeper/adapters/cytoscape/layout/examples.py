"""Synthetic, source-independent review cases."""

from .model import Assembly as A
from .model import Node as N
from .model import Problem


def examples():
    return {
        "disjoint": Problem(
            tuple(N(i, i.upper()) for i in "abcdef"),
            (
                A("west", "West assembly", tuple("abc")),
                A("east", "East assembly", tuple("def")),
            ),
        ),
        "nested": Problem(
            tuple(N(i, i.upper()) for i in "abcdef"),
            (
                A("west", "West assembly", tuple("abc")),
                A("east", "East assembly", tuple("def")),
                A("root", "Whole assembly", ("west", "east")),
            ),
        ),
        "shared-node": Problem(
            (N("a", "A only"), N("s", "Shared"), N("z", "B only")),
            (A("A", "Assembly A", ("a", "s")), A("B", "Assembly B", ("s", "z"))),
        ),
        "crossing": Problem(
            tuple(N(i, i.upper()) for i in "abcd"),
            (
                A("ab", "A + B", tuple("ab")),
                A("bc", "B + C", tuple("bc")),
                A("cd", "C + D", tuple("cd")),
                A("da", "D + A", tuple("da")),
            ),
        ),
        "shared-child": Problem(
            (N("a", "A only"), N("s", "Shared service"), N("z", "B only")),
            (
                A("child", "Shared assembly", ("s",)),
                A("A", "Assembly A", ("a", "child")),
                A("B", "Assembly B", ("child", "z")),
            ),
        ),
        "variable-sizes": Problem(
            (
                N("a", "Short", 72, 36),
                N("b", "Long equipment label", 208, 48),
                N("c", "Two-line label", 160, 64),
                N("d", "Compact", 88, 36),
            ),
            (A("group", "Variable footprints", tuple("abcd"), 208),),
        ),
        # Every four-of-five subset is a rectangle: impossible, independent of canvas.
        # At least one of five rectangles does not uniquely determine any of the
        # four extrema. The bounding box of the other four contains it.
        "impossible-five": Problem(
            tuple(N(i, i.upper(), 56, 32) for i in "abcde"),
            tuple(
                A(
                    "except-" + i,
                    "All except " + i.upper(),
                    tuple(j for j in "abcde" if j != i),
                    160,
                )
                for i in "abcde"
            ),
        ),
    }
