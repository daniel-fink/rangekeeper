"""Canonical native Excel addresses, shared by snapshots and extraction rules.

This small standard-library boundary keeps specification construction independent
of optional openpyxl imports. It does not assign Evidence or graph identities.
"""

import re

MAX_ROW = 1048576
MAX_COLUMN = 16384


def column_number(value: str) -> int:
    if type(value) is not str or re.fullmatch(r"[A-Z]{1,3}", value) is None:
        raise ValueError("Column must be uppercase Excel letters")
    number = 0
    for character in value:
        number = number * 26 + ord(character) - ord("A") + 1
    if number > MAX_COLUMN:
        raise ValueError("Column exceeds XFD")
    return number


def address(value: str) -> tuple[int, int]:
    if type(value) is not str:
        raise TypeError("Cell coordinate must be str")
    match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]{0,6})", value)
    if match is None or int(match[2]) > MAX_ROW:
        raise ValueError("Expected a canonical Excel cell coordinate, such as A8")
    return int(match[2]), column_number(match[1])


def merged_bounds(value: str) -> tuple[str, int, int, int, int]:
    if type(value) is not str:
        raise TypeError("Merged range must be str")
    parts = value.split(":")
    if len(parts) not in (1, 2):
        raise ValueError("Invalid merged range")
    r1, c1 = address(parts[0])
    r2, c2 = address(parts[-1])
    if r1 > r2 or c1 > c2:
        raise ValueError("Invalid merged range")
    return parts[0], r1, c1, r2, c2
