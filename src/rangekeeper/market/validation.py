"""The checks of a market paths document (ADR-011, ADR-014).

``validate_record`` reports the problems of one record; it reads no other
document and draws no random numbers.
"""

import math
from collections.abc import Iterable, Sequence
from datetime import date
from itertools import pairwise

from rangekeeper.duration import shift
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.schema.records import PathCapture, PathSeries
from rangekeeper.schema.records import Paths as PathsRecord
from rangekeeper.shared import pointer
from rangekeeper.shared.codes import Code
from rangekeeper.shared.diagnostics import ValidationReport
from rangekeeper.shared.errors import UnitError
from rangekeeper.shared.validation import bounded, require

__all__ = ["check_lag", "validate_record"]


def validate_record(record: PathsRecord, *, units: UnitSystem) -> ValidationReport:
    """Report the problems of one Paths record; content problems raise nothing."""

    def check() -> None:
        check_periods(record)
        check_series(record.series, units=units)
        check_members(record)
        check_capture(record.capture, record=record)

    return bounded([], check, document=record.to_data())


def check_periods(record: PathsRecord) -> None:
    """Require Periods in order that do not overlap."""
    periods = record.periods
    require(bool(periods), "market paths need at least one Period", path="/periods")
    for index, (left, right) in enumerate(pairwise(periods)):
        require(
            left.end <= right.start,
            f"the Periods overlap or are out of order: {left.start} to {left.end} "
            f"and {right.start} to {right.end}",
            path=pointer.child("/periods", index + 1),
        )


def check_series(series: Sequence[PathSeries], *, units: UnitSystem) -> None:
    """Require unique series names, known units and whole lags of zero or more."""
    require(bool(series), "market paths need at least one series", path="/series")
    _require_unique((item.name for item in series), label="series name", path="/series")
    for index, item in enumerate(series):
        path = pointer.child("/series", index)
        try:
            units.validate_units(item.units)
        except UnitError as error:
            require(False, str(error), code=Code.UNITS, path=path + "/units")
        check_lag(item.lag, path=path + "/lag")


def check_lag(lag: Quantity, *, path: str = "") -> None:
    """Require a lag that is a whole length of zero or more, such as ``1 month``."""
    text = f"{lag.magnitude} {lag.units}"
    try:
        later = shift(on=date(2000, 1, 1), by=lag)
    except UnitError as error:
        require(False, str(error), code=Code.UNITS, path=path, values={"lag": text})
    require(
        isinstance(later, date) and later >= date(2000, 1, 1),
        f"a lag must not be negative, not {text}",
        path=path,
        values={"lag": text},
    )


def check_members(record: PathsRecord) -> None:
    """Require unique keys, and every series in every path with one finite amount a Period."""
    members = record.members
    require(bool(members), "market paths need at least one path", path="/members")
    _require_unique((m.key for m in members), label="path key", path="/members")
    names = [item.name for item in record.series]
    count = len(record.periods)
    for index, member in enumerate(members):
        path = pointer.child("/members", index)
        given = [amounts.series for amounts in member.amounts]
        require(
            given == names,
            f"path {member.key} has the series {given}; the document declares {names}",
            path=path + "/amounts",
            values={"key": member.key, "series": given, "declared": names},
        )
        for position, amounts in enumerate(member.amounts):
            magnitudes = amounts.magnitudes
            at = pointer.child(path + "/amounts", position)
            require(
                len(magnitudes) == count,
                f"series {amounts.series} of path {member.key} has "
                f"{len(magnitudes)} amounts for {count} Periods",
                path=at,
                values={"key": member.key, "series": amounts.series},
            )
            require(
                all(math.isfinite(x) for x in magnitudes),
                f"series {amounts.series} of path {member.key} has an amount that "
                "is not finite",
                path=at,
                values={"key": member.key, "series": amounts.series},
            )


def check_capture(capture: PathCapture, *, record: PathsRecord) -> None:
    """Require a capture record that agrees with the paths that it describes."""
    require(
        capture.count == len(record.members),
        f"the capture record counts {capture.count} paths; the document holds "
        f"{len(record.members)}",
        path="/capture/count",
    )
    require(
        (capture.generator is None) == (capture.fingerprint is None),
        "a generator and its fingerprint are recorded together",
        path="/capture",
    )
    if capture.generator is None:
        require(
            capture.seed is None and not capture.parameters and not capture.streams,
            "paths made from data have no seed, parameters or random streams",
            path="/capture",
        )
    require(
        bool(capture.streams) == (capture.algorithm is not None),
        "random streams are recorded with their algorithm",
        path="/capture",
    )
    require(
        not capture.streams or capture.seed is not None,
        "random streams need the seed that seeds them",
        path="/capture/seed",
    )
    check_parameters(capture, names={item.name for item in record.series})
    _require_unique(
        (s.name for s in capture.streams), label="stream", path="/capture/streams"
    )
    _require_unique(
        (v.name for v in capture.versions), label="library", path="/capture/versions"
    )


def check_parameters(capture: PathCapture, *, names: set[str]) -> None:
    """Require parameters of declared series, each with one value, once per series."""
    seen: set[tuple[str, str]] = set()
    for index, parameter in enumerate(capture.parameters):
        path = pointer.child("/capture/parameters", index)
        require(
            parameter.series in names,
            f"parameter {parameter.name} is for series {parameter.series}, which "
            "the document does not declare",
            path=path + "/series",
            values={"series": parameter.series, "declared": sorted(names)},
        )
        require(
            (parameter.quantity is None) != (parameter.distribution is None),
            f"parameter {parameter.name} of {parameter.series} needs exactly one "
            "quantity or distribution",
            path=path,
        )
        pair = (parameter.series, parameter.name)
        require(
            pair not in seen,
            f"parameter {parameter.name} of {parameter.series} is given twice",
            code=Code.UNIQUE,
            path=path,
        )
        seen.add(pair)


def _require_unique(values: Iterable[str], *, label: str, path: str) -> None:
    """Require distinct values in one collection."""
    seen: set[str] = set()
    for index, value in enumerate(values):
        require(
            value not in seen,
            f"duplicate {label}: {value}",
            code=Code.UNIQUE,
            path=pointer.child(path, index),
            values={"value": value},
        )
        seen.add(value)
