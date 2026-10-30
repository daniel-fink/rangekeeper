"""The notebook display and the repr of a Table (#461)."""

import re
from decimal import Decimal
from enum import Enum, StrEnum
from uuid import UUID

import rangekeeper as rk
from rangekeeper.shared.table import Row, Table

FIRST = UUID("11111111-2222-3333-4444-555555555555")
SECOND = UUID("66666666-7777-8888-9999-000000000000")
OTHER = UUID("abcdef01-2345-6789-abcd-ef0123456789")


class Role(StrEnum):
    FIXED = "fixed"


class Level(Enum):
    HIGH = 3


def cells(table: Table) -> list[list[str]]:
    """Return the header and body cells of a Table's notebook display."""
    html = table._repr_html_()
    rows = re.findall(r"<tr>(.*?)</tr>", html)
    return [re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row) for row in rows]


def test_repr_gives_the_shape_and_the_column_names():
    table = Table(("key", "role"), ({"key": "rent", "role": Role.FIXED},))
    assert repr(table) == "Table(1 row, 2 columns: key, role)"
    assert repr(Table((), ())) == "Table(0 rows, 0 columns)"
    wide = Table([f"c{index}" for index in range(10)], ())
    assert repr(wide) == (
        "Table(0 rows, 10 columns: c0, c1, c2, c3, c4, c5, c6, c7, ... 2 more)"
    )


def test_html_shows_headers_rows_and_readable_cells():
    table = Table(
        ("key", "role", "level", "amount", "count", "ready", "note"),
        (
            {
                "key": "rent",
                "role": Role.FIXED,
                "level": Level.HIGH,
                "amount": Decimal("1234567.5"),
                "count": 12000,
                "ready": True,
                "note": None,
            },
        ),
    )
    assert cells(table) == [
        ["key", "role", "level", "amount", "count", "ready", "note"],
        ["rent", "fixed", "HIGH", "1,234,567.5", "12,000", "True", "—"],
    ]


def test_html_rounds_floats_to_six_significant_digits():
    values = (0.0859717270, 1.0347826086, 2e7, 9344547.8456, 0.0, 1e-20, float("inf"))
    table = Table(("value",), ({"value": value} for value in values))
    assert [row[0] for row in cells(table)[1:]] == [
        "0.0859717",
        "1.03478",
        "20,000,000",
        "9,344,548",
        "0",
        "1e-20",
        "inf",
    ]


def test_html_puts_shared_units_in_the_header():
    table = Table(
        ("key", "cost", "quantity"),
        (
            {
                "key": "land",
                "cost": rk.Quantity(text="20e6 AUD"),
                "quantity": rk.Quantity(text="65 %"),
            },
            {
                "key": "works",
                "cost": None,
                "quantity": rk.Quantity(text="1.25 ratio"),
            },
        ),
    )
    assert cells(table) == [
        ["key", "cost [AUD]", "quantity"],
        ["land", "20,000,000", "65 %"],
        ["works", "—", "1.25 ratio"],
    ]


def test_html_shows_keys_and_names_in_place_of_uuids():
    table = Table(
        ("name", "parent_id", "other"),
        (
            Row({"name": "Site", "parent_id": None, "other": FIRST}, FIRST),
            Row({"name": "Tower", "parent_id": FIRST, "other": OTHER}, SECOND),
        ),
    )
    # A row's own UUID and a UUID outside the Table keep their first digits.
    assert cells(table)[1:] == [
        ["Site", "—", "11111111…"],
        ["Tower", "Site", "abcdef01…"],
    ]


def test_html_keeps_uuids_whose_label_is_not_unique():
    table = Table(
        ("key", "target"),
        (
            Row({"key": "rent", "target": SECOND}, FIRST),
            Row({"key": "rent", "target": FIRST}, SECOND),
        ),
    )
    assert [row[1] for row in cells(table)[1:]] == ["66666666…", "11111111…"]


def test_html_limits_the_rows_and_counts_the_others():
    table = Table(("index",), ({"index": index} for index in range(53)))
    html = table._repr_html_()
    assert len(cells(table)) == 1 + 50 + 1
    assert '<tfoot><tr><td colspan="1">… 3 more rows</td></tr></tfoot>' in html
    single = Table(("index",), ({"index": index} for index in range(51)))
    assert "… 1 more row<" in single._repr_html_()
    assert "<tfoot>" not in Table(("index",), ({"index": 1},))._repr_html_()


def test_html_escapes_cells_and_headers():
    table = Table(("<b>",), ({"<b>": "a & <i>b</i>"},))
    html = table._repr_html_()
    assert "<th>&lt;b&gt;</th>" in html
    assert "<td>a &amp; &lt;i&gt;b&lt;/i&gt;</td>" in html
