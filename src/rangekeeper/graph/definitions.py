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


@dataclass(frozen=True, slots=True, init=False)
class Definitions:
    taxonomies: Catalog[Taxonomy]
    measures: Catalog[Measure]
    _lookup: Mapping[UUID, tuple[Definition, Taxonomy | None]] = field(
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
        lookup: dict[UUID, tuple[Definition, Taxonomy | None]] = {}

        def register(
            definition: Definition,
            taxonomy: Taxonomy | None = None,
        ) -> None:
            if definition.id in lookup:
                raise IdentityConflictError(
                    f"duplicate definition UUID {definition.id}"
                )
            lookup[definition.id] = (definition, taxonomy)

        for taxonomy in taxonomies:
            register(taxonomy)
            for classification in taxonomy.classifications.values():
                register(classification, taxonomy)
        for measure in measures:
            register(measure)

        object.__setattr__(self, "taxonomies", taxonomy_catalog)
        object.__setattr__(self, "measures", measure_catalog)
        object.__setattr__(self, "_lookup", MappingProxyType(lookup))

    def _lookup_classification(
        self, identifier: UUID
    ) -> tuple[Classification, Taxonomy]:
        if not isinstance(identifier, UUID):
            raise TypeError("classification id must be a UUID")
        entry = self._lookup.get(identifier)
        if entry is None:
            raise UnknownDefinitionError(
                "classification", identifier, scope="Definitions"
            )
        definition, taxonomy = entry
        if not isinstance(definition, Classification) or taxonomy is None:
            raise UnknownDefinitionError(
                "classification", identifier, scope="Definitions"
            )
        return definition, taxonomy

    def _require_classification_instance(
        self, classification: Classification
    ) -> tuple[Classification, Taxonomy]:
        if not isinstance(classification, Classification):
            raise TypeError("classification must be a Classification")
        registered, taxonomy = self._lookup_classification(classification.id)
        if registered is not classification:
            raise CatalogInstanceError(
                "classification",
                classification.id,
                scope=f"taxonomy {taxonomy.code!r}",
            )
        return registered, taxonomy
