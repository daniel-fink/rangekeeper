"""Bounded inspection of captured documents, independent of native format."""

import json
from abc import ABC, abstractmethod
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from itertools import islice
from typing import Any, Generic, TypeVar

from ... import validate
from ..provenance import Location, Method, Source
from . import _structured
from .operation import Operation, Outcome, _Failure, _invoke

__all__ = [
    "TEXT_PREVIEW_LIMIT",
    "ContentItem",
    "Description",
    "Document",
    "Inspection",
    "Page",
    "children",
    "describe",
    "inspect",
    "search",
]
T = TypeVar("T")
TEXT_PREVIEW_LIMIT = 2000


@dataclass(frozen=True, slots=True, kw_only=True)
class ContentItem:
    location: Location
    kind: str
    label: str

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location):
            raise TypeError("location must be Location")
        validate.require_text(self.kind, "kind")
        if type(self.label) is not str:
            raise TypeError("label must be str")


@dataclass(frozen=True, slots=True, kw_only=True)
class Page(Generic[T]):
    items: tuple[T, ...]
    next_cursor: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        if self.next_cursor is not None:
            validate.require_text(self.next_cursor, "next_cursor")


@dataclass(frozen=True, slots=True, kw_only=True)
class Inspection(Generic[T]):
    location: Location
    kind: str
    content: T
    truncated: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.location, Location):
            raise TypeError("location must be Location")
        validate.require_text(self.kind, "kind")
        if type(self.truncated) is not bool:
            raise TypeError("truncated must be bool")


@dataclass(frozen=True, slots=True, kw_only=True)
class Description:
    source: Source
    format: str
    capabilities: tuple[str, ...]
    metadata: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.source, Source):
            raise TypeError("source must be Source")
        validate.require_text(self.format, "format")
        capabilities = tuple(self.capabilities)
        for item in capabilities:
            validate.require_text(item, "capability")
        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(self, "metadata", _structured.freeze_mapping(self.metadata))


class Document(ABC):
    """Backend interface. Public functions below record every inspection invocation.

    Implementations bind all access to their immutable snapshot and return immutable
    native payloads. The base does not require eager storage or an open session.
    """

    source: Source

    @property
    @abstractmethod
    def fingerprint(self) -> str: ...

    @property
    @abstractmethod
    def format(self) -> str: ...

    @property
    def capabilities(self) -> tuple[str, ...]:
        return ("describe",)

    @abstractmethod
    def _describe(self) -> Description: ...

    def _children(self, location: Location) -> Iterable[ContentItem]:
        raise _unsupported(self, "children")

    def _inspect(self, location: Location) -> Inspection[Any]:
        raise _unsupported(self, "inspect")

    def _search(self, query: str, case_sensitive: bool) -> Iterable[ContentItem]:
        raise _unsupported(self, "search")


def _unsupported(document: Document, capability: str) -> _Failure:
    return _Failure(
        "unsupported_capability",
        f"Document does not support {capability}",
        locations=(Location(source=document.source),),
        details={"capability": capability, "format": document.format},
    )


def _request(
    document: Document,
    name: str,
    spec: Mapping[str, object],
    run: Callable[[Operation], T],
) -> Outcome[T]:
    if not isinstance(document, Document):
        raise TypeError("document must implement Document")

    def execute(operation: Operation) -> T:
        if name not in document.capabilities:
            raise _unsupported(document, name)
        return run(operation)

    return _invoke(
        Method(code=f"rk.document.{name}", version="1"),
        spec,
        {"document": document.fingerprint},
        execute,
    )


def _location_spec(location: Location | None) -> Mapping[str, object] | None:
    if location is None:
        return None
    if not isinstance(location, Location):
        raise TypeError("location must be Location")
    return {
        "source_id": location.source.id,
        "checksum": location.source.checksum,
        "reference": location.reference,
    }


def _location(document: Document, location: Location | None) -> Location:
    if location is None:
        return Location(source=document.source)
    if location.source != document.source:
        raise _Failure(
            "source_mismatch",
            "Location belongs to another source snapshot",
            locations=(Location(source=document.source),),
            details={"requested": _location_spec(location)},
        )
    return Location(source=document.source, reference=location.reference)


def describe(document: Document) -> Outcome[Description]:
    return _request(document, "describe", {}, lambda _: document._describe())


def inspect(document: Document, location: Location) -> Outcome[Inspection[Any]]:
    specification = {
        "location": _location_spec(location),
        "text_limit": TEXT_PREVIEW_LIMIT,
    }
    return _request(
        document,
        "inspect",
        specification,
        lambda _: document._inspect(_location(document, location)),
    )


def _page_args(limit: int, cursor: str | None) -> None:
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("limit must be an integer from 1 to 500")
    if cursor is not None and (type(cursor) is not str or not cursor):
        raise TypeError("cursor must be nonempty text or None")


def _page(
    items: Iterable[T],
    *,
    binding: str,
    limit: int,
    cursor: str | None,
) -> Page[T]:
    offset = 0
    if cursor is not None:
        try:
            payload = json.loads(urlsafe_b64decode(cursor.encode("ascii")))
        except (ValueError, UnicodeError) as exc:
            raise ValueError("Malformed document cursor") from exc
        if (
            type(payload) is not dict
            or set(payload) != {"binding", "offset"}
            or type(payload["offset"]) is not int
            or payload["offset"] < 0
            or type(payload["binding"]) is not str
        ):
            raise ValueError("Malformed document cursor")
        if payload["binding"] != binding:
            raise _Failure(
                "cursor_mismatch", "Cursor belongs to another snapshot/query"
            )
        offset = payload["offset"]
    selected = tuple(islice(items, offset, offset + limit + 1))
    next_cursor = None
    if len(selected) > limit:
        payload = json.dumps(
            {"binding": binding, "offset": offset + limit},
            sort_keys=True,
            separators=(",", ":"),
        )
        next_cursor = urlsafe_b64encode(payload.encode("ascii")).decode("ascii")
    return Page(items=selected[:limit], next_cursor=next_cursor)


def _binding(document: Document, kind: str, query: object) -> str:
    return _structured.fingerprint((document.fingerprint, kind, query))


def children(
    document: Document,
    location: Location | None = None,
    *,
    limit: int = 50,
    cursor: str | None = None,
) -> Outcome[Page[ContentItem]]:
    _page_args(limit, cursor)
    location_spec = _location_spec(location)
    return _request(
        document,
        "children",
        {"location": location_spec, "limit": limit, "cursor": cursor},
        lambda _: _page(
            document._children(_location(document, location)),
            binding=_binding(document, "children", location_spec),
            limit=limit,
            cursor=cursor,
        ),
    )


def search(
    document: Document,
    query: str,
    *,
    limit: int = 50,
    cursor: str | None = None,
    case_sensitive: bool = True,
) -> Outcome[Page[ContentItem]]:
    validate.require_text(query, "query")
    _page_args(limit, cursor)
    if type(case_sensitive) is not bool:
        raise TypeError("case_sensitive must be bool")
    return _request(
        document,
        "search",
        {
            "query": query,
            "case_sensitive": case_sensitive,
            "limit": limit,
            "cursor": cursor,
        },
        lambda _: _page(
            document._search(query, case_sensitive),
            binding=_binding(document, "search", (query, case_sensitive)),
            limit=limit,
            cursor=cursor,
        ),
    )
