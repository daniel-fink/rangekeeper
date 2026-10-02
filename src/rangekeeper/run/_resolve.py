"""Collect exact referenced revisions through an explicitly supplied resolver."""

from uuid import UUID

from ..errors import MissingReferenceError, ReferenceTypeError, IdentityConflictError
from ..model.model import Model
from ..specification.specification import Specification
from ..references import DocumentResolver
from .run import Run
from .._schema.records import Diagnostic, Step


def collect_documents(root: Run, resolver: DocumentResolver) -> tuple[dict, dict, dict]:
    """Cache each resolved revision; leave cycle/ownership decisions to validation.

    The root is supplied in memory, allowing validation before its first store write.
    Includes, cases, spawns, outputs, Model pins and scoped report documents resolve.
    Historical predecessors are not required to interpret the current document.
    Untyped report-document references use the resolver's three typed lookups.
    """
    found: dict[UUID, Model | Specification | Run] = {root.id: root}
    pending: list[Model | Specification | Run] = [root]
    loaders = {
        Model: resolver.load_model,
        Specification: resolver.load_specification,
        Run: resolver.load_run,
    }

    def resolve(identity, kind=None):
        if identity in found:
            document = found[identity]
            if kind is not None and not isinstance(document, kind):
                raise ReferenceTypeError(f"{identity} is not a {kind.__name__}")
            return
        candidates = (kind,) if kind is not None else (Model, Specification, Run)
        failures = []
        for candidate in candidates:
            try:
                document = loaders[candidate](identity)
            except (MissingReferenceError, ReferenceTypeError) as error:
                failures.append(error)
                continue
            if not isinstance(document, candidate):
                raise ReferenceTypeError(
                    f"resolver did not return a {candidate.__name__}"
                )
            if document.id != identity:
                raise IdentityConflictError(
                    f"resolver returned a different revision for {identity}"
                )
            found[identity] = document
            pending.append(document)
            return
        raise failures[-1]

    while pending:
        document = pending.pop()
        if isinstance(document, Run):
            record = document.record
            resolve(record.specification, Specification)
            for identity in record.spawns or ():
                resolve(identity, Run)
            for identity in record.outputs or ():
                resolve(identity, Model)
            references: tuple[Diagnostic | Step, ...] = (
                *(record.report.diagnostics or ()),
                *(record.report.trace or ()),
            )
            for item in references:
                if item.document is not None:
                    resolve(item.document)
        elif isinstance(document, Specification):
            spec_record = document.record
            if spec_record.model is not None:
                resolve(spec_record.model, Model)
            for identity in (*(spec_record.includes or ()), *(spec_record.cases or ())):
                resolve(identity, Specification)

    def catalogue(kind):
        return {
            str(identity): doc.to_data()
            for identity, doc in found.items()
            if isinstance(doc, kind)
        }

    return catalogue(Run), catalogue(Specification), catalogue(Model)
