"""Resolve the immutable case graph once before any execution is persisted."""

from uuid import UUID
from .._schema.validation import document_version
from .._validation import bounded
from ..diagnostics import Issue, ValidationReport
from ..errors import ValidationError, ReferenceTypeError, IdentityConflictError
from ..io.store import RecordStore
from ..model import Model
from ..specification import Composition, Specification
from ..specification.composition import compose
from ..specification.composition import specification_catalogue


class Plan:
    """A per-execution resolver. Failed leaf compositions remain reportable attempts.

    Caches are confined to one execute call so later calls recheck their resolver.
    Batch pin assertions and cycles fail before persistence starts.
    """

    def __init__(self, store: RecordStore) -> None:
        self.store = store
        self.models: dict[UUID, Model] = {}
        self.specifications: dict[UUID, Specification] = {}

    def resolve(
        self,
        root: Specification,
    ) -> tuple[dict[UUID, Specification], dict[UUID, Composition | ValidationError]]:
        """Resolve the case graph and compose each leaf once for this execution tree.

        Reuse these immutable views for pin checks and scalar preparation. Keep
        composition failures so each leaf attempt can record its own Run evidence.
        """
        documents = {root.id: root}
        pending = [root]
        while pending:
            current = pending.pop()
            if current.record.model is not None:
                model = self.models.get(current.record.model)
                if model is None:
                    model = self.store.load_model(current.record.model)
                if not isinstance(model, Model):
                    raise ReferenceTypeError(
                        "input reference did not resolve to a Model"
                    )
                if model.id != current.record.model:
                    raise IdentityConflictError(
                        "input resolver returned a different revision"
                    )
                self.models[model.id] = model
            for id in (current.record.includes or ()) + (current.record.cases or ()):
                if id in documents:
                    continue
                found = self.store.load_specification(id)
                if not isinstance(found, Specification):
                    raise ReferenceTypeError(
                        "case/include did not resolve to a Specification"
                    )
                if found.id != id:
                    raise IdentityConflictError(
                        "case/include resolver returned a different revision"
                    )
                documents[id] = found
                pending.append(found)
        # Cycles cannot form a finalized acyclic execution tree. Composition
        # conflicts and invalid numerical roles are deliberately left for leaves.
        data = {str(id): spec.to_data() for id, spec in documents.items()}
        bounded(
            [],
            lambda: specification_catalogue(
                root.to_data(), data, document_version("Specification")
            ),
        ).raise_if_invalid()

        compositions: dict[UUID, Composition | ValidationError] = {}

        def check_pins(current: Specification, pins: tuple[UUID, ...] = ()) -> None:
            if current.record.cases:
                pins += (
                    (current.record.model,) if current.record.model is not None else ()
                )
                for id in current.record.cases:
                    check_pins(documents[id], pins)
            else:
                if current.id not in compositions:
                    try:
                        compositions[current.id] = compose(
                            current, resolver=self, documents=documents, catalogue=data
                        )
                    except ValidationError as error:
                        compositions[current.id] = error
                view = compositions[current.id]
                if isinstance(view, ValidationError):
                    return  # the leaf will record its conflicting composition
                if view.model_id is not None and any(
                    pin != view.model_id for pin in pins
                ):
                    raise ValidationError(
                        ValidationReport(
                            (
                                Issue(
                                    "batch.model",
                                    "batch input Model assertion mismatch",
                                    current.id,
                                ),
                            )
                        )
                    )

        check_pins(root)
        self.specifications = documents
        return documents, compositions

    def load_model(self, identity: UUID) -> Model:
        if identity not in self.models:
            self.models[identity] = self.store.load_model(identity)
        return self.models[identity]

    def load_specification(self, identity: UUID) -> Specification:
        return self.specifications[identity]
