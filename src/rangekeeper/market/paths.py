"""Market paths: a captured, replayable document of named series (ADR-014).

``Paths`` is the document. Each member is a ``MarketPath``: one possible
history of external conditions, with one Flow for each named series. The
document stores the amounts, so a use of the paths draws no random numbers.
Its capture record says how they were made; ``regenerate`` makes them again
with another seed.
"""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Self
from uuid import UUID, uuid5

from rangekeeper.duration import Period, shift
from rangekeeper.flow import Flow
from rangekeeper.market.generator import generators
from rangekeeper.market.validation import check_lag, validate_record
from rangekeeper.quantity import Quantity, UnitSystem, default_units
from rangekeeper.schema.records import MarketPath as MarketPathRecord
from rangekeeper.schema.records import (
    Metadata,
    PathAmounts,
    PathCapture,
    PathSeries,
)
from rangekeeper.schema.records import Paths as PathsRecord
from rangekeeper.schema.runtime import UNSET
from rangekeeper.schema.validation import document_version, supports_version
from rangekeeper.shared.arguments import optional_text
from rangekeeper.shared.codes import Code
from rangekeeper.shared.diagnostics import ValidationReport
from rangekeeper.shared.encoding import digest
from rangekeeper.shared.errors import (
    ContractError,
    MissingReferenceError,
    UnsupportedVersionError,
)

__all__ = ["MarketPath", "Paths"]

# The namespace of the content-derived UUID of each Paths revision.
_NAMESPACE = UUID("6a1d4c36-3c49-5f0e-9a61-1f3e0f6a8b52")
_IDENTITY = "market-paths/v1:"
_ZERO = "0 days"

Lag = Quantity | str


@dataclass(frozen=True, eq=False)
class MarketPath:
    """One path of a ``Paths`` document: its key and one Flow for each series.

    ``path["rent_index"]`` gives the Flow of a series over the Periods of the
    document, in the units of the series. Each read makes a new Flow with the
    same amounts.
    """

    paths: "Paths"
    record: MarketPathRecord

    @property
    def key(self) -> str:
        """The key of the path in its document."""
        return self.record.key

    @property
    def names(self) -> tuple[str, ...]:
        """The names of the series, in the order of their declarations."""
        return self.paths.names

    def __getitem__(self, name: str) -> Flow:
        """Return the Flow of the series ``name``."""
        series = self.paths.series(name=name)
        (amounts,) = (item for item in self.record.amounts if item.series == name)
        return Flow.from_periods(
            periods=self.paths.periods,
            magnitudes=amounts.magnitudes,
            units=series.units,
        )

    def __iter__(self) -> Iterator[str]:
        return iter(self.names)

    def __len__(self) -> int:
        return len(self.names)

    def __repr__(self) -> str:
        return f"MarketPath(key={self.key!r}, names={list(self.names)!r})"


@dataclass(frozen=True, init=False, eq=False)
class Paths:
    """A captured, replayable set of market paths over one sequence of Periods.

    ``rk.market.generate`` makes one, and ``Paths.from_flows`` makes one from
    data. ``paths.keys`` lists the paths; ``paths[key]`` returns one
    ``MarketPath`` and ``paths[key]["rent_index"]`` the Flow of one series.
    ``paths.mean(name=)`` gives the mean Flow of a series over the paths.
    ``capture`` says how the paths were made, and ``regenerate(seed=)`` makes
    them again with another seed.

    The document is immutable. Its UUID is a digest of its content, so the
    same content gives the same revision, and ``==`` compares the content.
    """

    __slots__ = ("_record",)
    _record: PathsRecord

    def __init__(self, record: PathsRecord) -> None:
        """Validate a record and return its document."""
        if not isinstance(record, PathsRecord):
            raise TypeError("record must be a generated Paths record")
        if not supports_version(
            record.metadata.schema_version, document_version("Paths")
        ):
            raise UnsupportedVersionError(record.metadata.schema_version)
        validate_record(record, units=default_units).raise_if_invalid()
        object.__setattr__(self, "_record", record)

    @classmethod
    def from_data(cls, data: Mapping[str, object]) -> "Paths":
        """Decode and validate a Paths document; nothing else is read."""
        return cls(PathsRecord.from_data(data))

    @classmethod
    def create(
        cls,
        *,
        periods: Sequence[Period],
        series: Sequence[PathSeries],
        members: Sequence[MarketPathRecord],
        capture: PathCapture,
        name: str | None = None,
        description: str | None = None,
    ) -> "Paths":
        """Return a new Paths revision; its UUID is a digest of its content.

        A path generator makes its paths with this call. ``series`` declares
        each series, ``members`` holds the amounts of each path, and
        ``capture`` says how they were made.
        """
        optional_text(name, "name", empty=False)
        optional_text(description, "description")
        record = PathsRecord(
            metadata=Metadata(
                id=UUID(int=0),
                schema_version=document_version("Paths"),
                name=UNSET if name is None else name,
                description=UNSET if description is None else description,
            ),
            periods=tuple(periods),
            series=tuple(series),
            members=tuple(members),
            capture=capture,
        )
        identity = _identity(record)
        return cls(record.replace(metadata=record.metadata.replace(id=identity)))

    @classmethod
    def from_flows(
        cls,
        *,
        flows: Mapping[str, Mapping[str, Flow]],
        lag: Lag | Mapping[str, Lag] = _ZERO,
        name: str | None = None,
        description: str | None = None,
    ) -> "Paths":
        """Make Paths from data: a mapping from each path key to its Flows by name.

        Every path has the same series names, and every Flow has the same
        Periods and, for each name, the same units. ``lag`` is the time after
        the end of a Period when its amount is known: one length for every
        series, such as ``"1 month"``, or a mapping from each name to its
        length. The capture record has no generator, so ``regenerate`` raises.
        """
        periods, series, members = _from_flows(flows=flows, lag=lag)
        return cls.create(
            periods=periods,
            series=series,
            members=members,
            capture=PathCapture(
                count=len(members), parameters=(), streams=(), versions=()
            ),
            name=name,
            description=description,
        )

    @property
    def id(self) -> UUID:
        """The UUID of this revision."""
        return self._record.metadata.id

    @property
    def metadata(self) -> Metadata:
        """The identity, schema version, name and description of this revision."""
        return self._record.metadata

    @property
    def record(self) -> PathsRecord:
        """Read-only typed access to the generated fields."""
        return self._record

    def to_data(self) -> dict[str, object]:
        """Return detached JSON-compatible content."""
        return self._record.to_data()

    def validate(
        self,
        *,
        resolver: object | None = None,
        units: UnitSystem | None = None,
    ) -> ValidationReport:
        """Report the problems of this document; content problems raise nothing.

        The document refers to no other document, so ``resolver`` changes
        nothing. ``units`` replaces the default unit system for the units of
        the series.
        """
        del resolver
        return validate_record(self._record, units=units or default_units)

    def check(
        self,
        *,
        resolver: object | None = None,
        units: UnitSystem | None = None,
    ) -> Self:
        """Return this document if ``validate`` finds no problem.

        Otherwise raise ValidationError; its ``report`` holds the problems.
        """
        self.validate(resolver=resolver, units=units).raise_if_invalid()
        return self

    @property
    def periods(self) -> tuple[Period, ...]:
        """The Periods of every series, in order."""
        return tuple(self._record.periods)

    @property
    def names(self) -> tuple[str, ...]:
        """The names of the series, in the order of their declarations."""
        return tuple(series.name for series in self._record.series)

    @property
    def keys(self) -> tuple[str, ...]:
        """The keys of the paths, in order."""
        return tuple(member.key for member in self._record.members)

    @property
    def capture(self) -> PathCapture:
        """How the paths were made: generator, fingerprint, parameters, seed and versions."""
        return self._record.capture

    def series(self, *, name: str) -> PathSeries:
        """Return the declaration of one series: its name, units and lag.

        A name that the document does not declare raises MissingReferenceError
        with the names that it declares.
        """
        for series in self._record.series:
            if series.name == name:
                return series
        raise MissingReferenceError(
            name,
            kind="series",
            by="name",
            where=self._where,
            document_id=self.id,
            candidates=self.names,
        )

    def available(self, *, name: str) -> tuple[date, ...]:
        """Return the date on which each amount of a series is known.

        It is the end of each Period plus the lag of the series (ADR-021).
        """
        lag = self.series(name=name).lag
        dates = []
        for period in self._record.periods:
            known = shift(on=period.end, by=lag)
            assert isinstance(known, date)
            dates.append(known)
        return tuple(dates)

    def __getitem__(self, key: str) -> MarketPath:
        """Return the path with the key ``key``.

        A key that the document does not hold raises MissingReferenceError
        with the keys that it holds.
        """
        for member in self._record.members:
            if member.key == key:
                return MarketPath(self, member)
        raise MissingReferenceError(
            key,
            kind="MarketPath",
            by="key",
            where=self._where,
            document_id=self.id,
            candidates=self.keys,
        )

    def __iter__(self) -> Iterator[str]:
        return iter(self.keys)

    def __len__(self) -> int:
        return len(self._record.members)

    def __contains__(self, key: object) -> bool:
        return key in self.keys

    def mean(self, *, name: str) -> Flow:
        """Return the mean of a series over the paths, Period by Period."""
        series = self.series(name=name)
        columns = [
            amounts.magnitudes
            for member in self._record.members
            for amounts in member.amounts
            if amounts.series == name
        ]
        return Flow.from_periods(
            periods=self.periods,
            magnitudes=[
                sum(values) / len(columns) for values in zip(*columns, strict=True)
            ],
            units=series.units,
        )

    def regenerate(self, *, seed: int) -> "Paths":
        """Make the paths again with another seed: the same generator, Periods and count.

        The same seed gives the same paths. Paths made from data have no
        generator and raise ContractError. A generator whose name the registry
        does not know raises UnknownExtensionError.
        """
        capture = self.capture
        if capture.generator is None:
            raise ContractError(
                "these paths were made from data, so no generator can make them again",
                document_id=self.id,
                values={"seed": seed},
            )
        return generators.get(capture.generator).generate(
            parameters=capture.parameters,
            periods=self.periods,
            seed=seed,
            count=capture.count,
        )

    def __eq__(self, other: object) -> bool:
        """Compare the content of two documents, their UUIDs included."""
        if not isinstance(other, Paths):
            return NotImplemented
        return self._record.equivalent(other._record)

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return (
            f"Paths(id={self.id!r}, names={list(self.names)!r}, "
            f"paths={len(self)}, periods={len(self._record.periods)})"
        )

    @property
    def _where(self) -> str:
        return f"Paths {self.metadata.name or self.id}"


def _identity(record: PathsRecord) -> UUID:
    """Return the UUID of a Paths revision: a digest of its content without its UUID."""
    data = record.to_data()
    metadata = dict(data["metadata"])  # type: ignore[call-overload]
    metadata.pop("id")
    return uuid5(_NAMESPACE, _IDENTITY + digest({**data, "metadata": metadata}))


def _from_flows(
    *,
    flows: Mapping[str, Mapping[str, Flow]],
    lag: Lag | Mapping[str, Lag],
) -> tuple[tuple[Period, ...], tuple[PathSeries, ...], tuple[MarketPathRecord, ...]]:
    """Return the Periods, series declarations and paths of Flows by key and name."""
    if not isinstance(flows, Mapping) or not flows:
        raise TypeError("flows takes a mapping from each path key to its Flows")
    first = next(iter(flows.values()))
    if not isinstance(first, Mapping) or not first:
        raise TypeError("each path takes a mapping from each series name to its Flow")
    names = tuple(first)
    lags = _lags(lag, names=names)
    reference = {name: _shape(first[name], name=name) for name in names}
    periods = reference[names[0]][1]
    members = []
    for key, path in flows.items():
        if not isinstance(path, Mapping) or tuple(path) != names:
            raise ContractError(
                f"path {key} has other series than the first path",
                values={"key": key, "series": list(names)},
            )
        members.append(
            MarketPathRecord(
                key=key,
                amounts=tuple(
                    _amounts(
                        path[name], name=name, shape=reference[name], periods=periods
                    )
                    for name in names
                ),
            )
        )
    series = tuple(
        PathSeries(name=name, units=reference[name][0], lag=lags[name])
        for name in names
    )
    return periods, series, tuple(members)


def _lags(
    lag: Lag | Mapping[str, Lag], *, names: tuple[str, ...]
) -> dict[str, Quantity]:
    """Return the lag of each series: one for all, or one for each name."""
    if not isinstance(lag, Mapping):
        return {name: _lag(lag) for name in names}
    if set(lag) != set(names):
        raise ContractError(
            "lag names a lag for each series",
            values={"series": list(names), "lags": sorted(lag)},
        )
    return {name: _lag(lag[name]) for name in names}


def _lag(lag: Lag) -> Quantity:
    """Return a lag as a Quantity after its check."""
    quantity = Quantity(text=lag) if isinstance(lag, str) else lag
    if not isinstance(quantity, Quantity):
        raise TypeError("a lag must be a Quantity or its text, such as '1 month'")
    # A length that is not a whole number of calendar steps raises UnitError.
    shift(on=date(2000, 1, 1), by=quantity)
    check_lag(quantity)
    return quantity


def _shape(flow: Flow, *, name: str) -> tuple[str, tuple[Period, ...]]:
    """Return the units and Periods of a Flow of period amounts."""
    if not isinstance(flow, Flow):
        raise TypeError(f"series {name} must be a Flow")
    periods = []
    for movement in flow.movements:
        if movement.period is None:
            raise ContractError(
                f"series {name} has a dated amount; market paths take an amount "
                "for each Period",
                values={"series": name},
            )
        periods.append(movement.period)
    return flow.units, tuple(periods)


def _amounts(
    flow: Flow,
    *,
    name: str,
    shape: tuple[str, tuple[Period, ...]],
    periods: tuple[Period, ...],
) -> PathAmounts:
    """Return the amounts of one Flow, after a check of its units and Periods."""
    units, own = _shape(flow, name=name)
    if (units, own) != (shape[0], periods):
        raise ContractError(
            f"each Flow of series {name} needs the units {shape[0]} and the "
            "Periods of the first path",
            code=Code.ALIGNMENT_DIFFER,
            values={"series": name, "units": units},
        )
    return PathAmounts(series=name, magnitudes=tuple(m.number for m in flow.movements))
