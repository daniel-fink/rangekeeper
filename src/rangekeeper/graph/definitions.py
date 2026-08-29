from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from uuid import UUID

from ..measure import Measure
from ._index import Catalog, catalog_values
from .classification import Classification
from .errors import IdentityConflictError
from .taxonomy import Taxonomy


Definition = Taxonomy | Classification | Measure


@dataclass(frozen=True, slots=True, init=False)
class Definitions:
    taxonomies: Catalog[Taxonomy]
    measures: Catalog[Measure]
    _lookup: Mapping[UUID, tuple[Definition, Taxonomy | None]] = field(
        init=False, repr=False, compare=False
    )

    def __init__(
        self,
        *,
        taxonomies: Iterable[Taxonomy] | Mapping[str, Taxonomy] = (),
        measures: Iterable[Measure] | Mapping[str, Measure] = (),
    ) -> None:
        taxonomies = catalog_values(taxonomies)
        measures = catalog_values(measures)
        if any(not isinstance(item, Taxonomy) for item in taxonomies):
            raise TypeError("taxonomies must contain only Taxonomy objects")
        if any(not isinstance(item, Measure) for item in measures):
            raise TypeError("measures must contain only Measure objects")
        taxonomy_catalog = Catalog(taxonomies, "taxonomy", scope="Definitions")
        measure_catalog = Catalog(measures, "measure", scope="Definitions")
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
