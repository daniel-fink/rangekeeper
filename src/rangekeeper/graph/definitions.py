from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from uuid import UUID

from ..measure import Measure
from ._catalog import Catalog
from .classification import Classification
from .errors import (
    CatalogInstanceError,
    IdentityConflictError,
    UnknownDefinitionError,
)
from .taxonomy import Taxonomy


Definition = Taxonomy | Classification | Measure

__all__ = ["Definitions"]


@dataclass(frozen=True, slots=True, init=False)
class Definitions:
    """Canonical taxonomies and measures shared by every object in a Graph."""

    taxonomies: Catalog[Taxonomy]
    measures: Catalog[Measure]
    _definition_by_id: Mapping[UUID, Definition] = field(
        init=False,
        repr=False,
        compare=False,
    )
    _taxonomy_by_classification_id: Mapping[UUID, Taxonomy] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __init__(
        self,
        *,
        taxonomies: Iterable[Taxonomy] | Mapping[str, Taxonomy] = (),
        measures: Iterable[Measure] | Mapping[str, Measure] = (),
    ) -> None:
        taxonomy_catalog = Catalog.from_input(
            taxonomies,
            item_type=Taxonomy,
            field="taxonomies",
            kind="taxonomy",
            scope="Definitions",
        )
        measure_catalog = Catalog.from_input(
            measures,
            item_type=Measure,
            field="measures",
            kind="measure",
            scope="Definitions",
        )
        taxonomies = tuple(taxonomy_catalog.values())
        measures = tuple(measure_catalog.values())
        definition_by_id: dict[UUID, Definition] = {}
        taxonomy_by_classification_id: dict[UUID, Taxonomy] = {}

        def register(definition: Definition) -> None:
            if definition.id in definition_by_id:
                raise IdentityConflictError(
                    f"duplicate definition UUID {definition.id}"
                )
            definition_by_id[definition.id] = definition

        for taxonomy in taxonomies:
            register(taxonomy)
            for classification in taxonomy.classifications.values():
                register(classification)
                taxonomy_by_classification_id[classification.id] = taxonomy
        for measure in measures:
            register(measure)

        object.__setattr__(self, "taxonomies", taxonomy_catalog)
        object.__setattr__(self, "measures", measure_catalog)
        object.__setattr__(
            self,
            "_definition_by_id",
            MappingProxyType(definition_by_id),
        )
        object.__setattr__(
            self,
            "_taxonomy_by_classification_id",
            MappingProxyType(taxonomy_by_classification_id),
        )

    def taxonomy_for(
        self,
        classification: UUID | Classification,
    ) -> Taxonomy:
        """Return the Taxonomy that owns a registered Classification."""
        registered = self._resolve_classification(classification)
        assert registered is not None
        return self._taxonomy_by_classification_id[registered.id]

    def _resolve_classification(
        self,
        classification: UUID | Classification | None,
    ) -> Classification | None:
        """Resolve a classification and reject noncanonical object instances."""

        if classification is None:
            return None
        if not isinstance(classification, (UUID, Classification)):
            raise TypeError("classification must be a UUID, Classification, or None")
        identifier = (
            classification if isinstance(classification, UUID) else classification.id
        )
        definition = self._definition_by_id.get(identifier)
        if not isinstance(definition, Classification):
            raise UnknownDefinitionError(
                "classification", identifier, scope="Definitions"
            )
        if (
            isinstance(classification, Classification)
            and definition is not classification
        ):
            taxonomy = self._taxonomy_by_classification_id[identifier]
            raise CatalogInstanceError(
                "classification",
                identifier,
                scope=f"taxonomy {taxonomy.code!r}",
            )
        return definition

    def _resolve_measure(self, measure: str | UUID | Measure) -> Measure:
        """Resolve a measure code, UUID, or canonical instance."""

        return self.measures._resolve(measure)

    def _classification_matches(
        self,
        actual: Classification | None,
        requested: Classification | None,
    ) -> bool:
        """Match exact or descendant classifications within one taxonomy."""

        if requested is None:
            return True
        if actual is None:
            return False
        requested_taxonomy = self.taxonomy_for(requested)
        actual_taxonomy = self.taxonomy_for(actual)
        return actual_taxonomy is requested_taxonomy and actual_taxonomy.is_a(
            actual,
            requested,
        )
