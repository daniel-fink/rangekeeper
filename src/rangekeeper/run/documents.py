"""Find documents by UUID, and the documents that a document depends on (#423).

``Documents`` holds documents by UUID and reads every other UUID from a fallback
resolver: its own documents first, else the resolver. ``dependencies`` gives the
one list of the documents that a document needs to be read, and ``closure``
resolves them, once each. Execution, Run validation and IO use these three; they
are documented here for internal use, not exported by ``rangekeeper.run``.
"""

from collections.abc import Iterable, Iterator
from typing import TypeAlias
from uuid import UUID

from rangekeeper.market.paths import Paths
from rangekeeper.model.model import Model
from rangekeeper.run.run import Run
from rangekeeper.schema.records import Diagnostic, Step
from rangekeeper.schema.runtime import Record
from rangekeeper.shared.arguments import require_uuid
from rangekeeper.shared.errors import (
    ContractError,
    MissingReferenceError,
    ReferenceTypeError,
    RevisionConflictError,
)
from rangekeeper.shared.references import SpecificationResolver, require_revision
from rangekeeper.specification.specification import Specification

Document: TypeAlias = Model | Specification | Run | Paths
# The document kinds, in the order that a lookup with no kind tries them.
KINDS: tuple[type[Document], ...] = (Model, Specification, Run, Paths)


def dependencies(document: Document) -> Iterator[tuple[UUID, type[Document] | None]]:
    """Yield the UUID and the kind of each document that ``document`` needs.

    A Specification needs its Model, its includes and its cases. A Run needs
    its Specification, its outputs, the Runs that it spawned and the
    documents that its report names; their kind is not recorded, so it is
    None. A Model and market paths need none. Historical predecessors are
    not followed.
    """
    if isinstance(document, Specification):
        record = document.record
        if record.model is not None:
            yield record.model, Model
        for identity in (*(record.includes or ()), *(record.cases or ())):
            yield identity, Specification
    elif isinstance(document, Run):
        run = document.record
        yield run.specification, Specification
        for identity in run.outputs or ():
            yield identity, Model
        for identity in run.spawns or ():
            yield identity, Run
        named: tuple[Diagnostic | Step, ...] = (
            *(run.report.diagnostics or ()),
            *(run.report.trace or ()),
        )
        for item in named:
            if item.document is not None:
                yield item.document, None


def require_same(existing: Document, candidate: Document) -> None:
    """Require two documents with one UUID to have the same kind and content.

    The comparison is schema-directed; it does not change either document's
    encounter order. Another kind or other content raises RevisionConflictError.
    """
    if type(existing) is not type(candidate) or not _record(existing).equivalent(
        _record(candidate)
    ):
        raise RevisionConflictError(
            f"different content or kind for revision {candidate.id}"
        )


class Documents:
    """Documents by UUID, else a fallback resolver: a read-only DocumentResolver.

    The documents are immutable; two with one UUID must be the same revision.
    A UUID that they do not hold is read from ``fallback``, which can be a
    store or another resolver; without one, or when the fallback cannot read
    that kind, the lookup raises MissingReferenceError with ``where``.
    """

    __slots__ = ("_documents", "_fallback", "_where")
    _documents: dict[UUID, Document]
    _fallback: SpecificationResolver | None
    _where: str

    def __init__(
        self,
        documents: Iterable[Document] = (),
        *,
        fallback: SpecificationResolver | None = None,
        where: str = "Documents",
    ) -> None:
        self._documents = {}
        self._fallback = fallback
        self._where = where
        for document in documents:
            self._hold(document)

    def _hold(self, document: Document) -> None:
        """Hold one more document; a second one with its UUID must be the same."""
        if not isinstance(document, KINDS):
            raise TypeError(
                "documents must be Models, Specifications, Runs or market paths"
            )
        existing = self._documents.get(document.id)
        if existing is None:
            self._documents[document.id] = document
        else:
            require_same(existing, document)

    def __contains__(self, id: object) -> bool:
        return id in self._documents

    def __len__(self) -> int:
        return len(self._documents)

    def __iter__(self) -> Iterator[Document]:
        """Iterate over the documents held, in the order that they were added."""
        return iter(tuple(self._documents.values()))

    def get(self, id: UUID) -> Document | None:
        """Return the document with this UUID that these documents hold, or None."""
        return self._documents.get(id)

    def documents(self) -> tuple[Document, ...]:
        """Return the documents held, in the order of their UUID text."""
        return tuple(
            item for _, item in sorted(self._documents.items(), key=lambda p: str(p[0]))
        )

    def load(self, id: UUID, kind: type[Document] | None = None) -> Document:
        """Return the document with this UUID and kind: held, else from the fallback.

        With no ``kind``, the fallback is asked for each kind in turn. A held
        document of another kind raises ReferenceTypeError; a UUID that none
        of them reads raises MissingReferenceError.
        """
        require_uuid(id, "id")
        held = self._documents.get(id)
        if held is not None:
            return held if kind is None else require_revision(held, id, kind)
        failure: MissingReferenceError | ReferenceTypeError | None = None
        for candidate in KINDS if kind is None else (kind,):
            try:
                return self._read(id, candidate)
            except (MissingReferenceError, ReferenceTypeError) as error:
                if kind is not None:
                    raise
                failure = error
        assert failure is not None
        raise failure

    def load_model(self, id: UUID) -> Model:
        """Return the Model with this UUID."""
        return require_revision(self.load(id, Model), id, Model)

    def load_specification(self, id: UUID) -> Specification:
        """Return the Specification with this UUID."""
        return require_revision(self.load(id, Specification), id, Specification)

    def load_run(self, id: UUID) -> Run:
        """Return the Run with this UUID."""
        return require_revision(self.load(id, Run), id, Run)

    def load_paths(self, id: UUID) -> Paths:
        """Return the market paths with this UUID."""
        return require_revision(self.load(id, Paths), id, Paths)

    def _read(self, id: UUID, kind: type[Document]) -> Document:
        """Read a document of one kind from the fallback, and check its identity."""
        loader = getattr(self._fallback, "load_" + kind.__name__.lower(), None)
        if loader is None:
            raise MissingReferenceError(id, kind=kind.__name__, where=self._where)
        return require_revision(loader(id), id, kind)


def closure(
    roots: Iterable[Document],
    *,
    resolver: SpecificationResolver | None,
    limit: int | None = None,
    where: str = "Documents",
) -> Documents:
    """Return the roots and each document that they depend on, each resolved once.

    The dependencies come from ``resolver``. The result holds no fallback. A
    missing or wrong-kind dependency raises, and more than ``limit`` documents
    raise ContractError.
    """
    found = Documents(roots)
    lookup = Documents(fallback=resolver, where=where)
    pending = list(found.documents())
    while pending:
        _require_within(found, limit)
        document = pending.pop()
        for identity, kind in dependencies(document):
            held = found.get(identity)
            if held is not None:
                if kind is not None:
                    require_revision(held, identity, kind)
                continue
            dependency = lookup.load(identity, kind)
            found._hold(dependency)
            pending.append(dependency)
    _require_within(found, limit)
    return found


def _require_within(found: Documents, limit: int | None) -> None:
    if limit is not None and len(found) > limit:
        raise ContractError(
            f"the document limit of {limit} is exceeded",
            values={"limit": limit, "documents": len(found)},
        )


def _record(document: Document) -> Record:
    return document._record if isinstance(document, Model) else document.record


__all__ = ["Document", "Documents", "closure", "dependencies", "require_same"]
