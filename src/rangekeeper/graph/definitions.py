from __future__ import annotations

import warnings
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import overload
from uuid import UUID

from ..measure import Measure
from ._index import Catalog, index_by_id
from .classification import Classification
from .taxonomy import Taxonomy


Definition = Taxonomy | Classification | Measure
_MISSING = object()


@dataclass(frozen=True, slots=True)
class _DefinitionsIndex:
    taxonomies: Catalog[Taxonomy]
    classifications: Catalog[Classification]
    measures: Catalog[Measure]
    definition_ids: frozenset[UUID]
    classification_owners: Mapping[UUID, Taxonomy]

    @classmethod
    def build(
        cls,
        taxonomies: tuple[Taxonomy, ...],
        measures: tuple[Measure, ...],
    ) -> _DefinitionsIndex:
        classifications = tuple(
            classification
            for taxonomy in taxonomies
            for classification in taxonomy.classifications
        )
        definitions: tuple[Definition, ...] = (
            *taxonomies,
            *classifications,
            *measures,
        )
        definition_ids = frozenset(index_by_id(definitions, "definition"))
        classification_owners = MappingProxyType(
            {
                classification.id: taxonomy
                for taxonomy in taxonomies
                for classification in taxonomy.classifications
            }
        )
        return cls(
            taxonomies=Catalog(taxonomies, "taxonomy", scope="Definitions"),
            classifications=Catalog(
                classifications,
                "classification",
                unique_codes=False,
                scope="Definitions",
            ),
            measures=Catalog(measures, "measure", scope="Definitions"),
            definition_ids=definition_ids,
            classification_owners=classification_owners,
        )


@dataclass(frozen=True, slots=True)
class Definitions:
    taxonomies: tuple[Taxonomy, ...] = ()
    measures: tuple[Measure, ...] = ()
    _index: _DefinitionsIndex = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        taxonomies = tuple(self.taxonomies)
        measures = tuple(self.measures)
        if any(not isinstance(item, Taxonomy) for item in taxonomies):
            raise TypeError("taxonomies must contain only Taxonomy objects")
        if any(not isinstance(item, Measure) for item in measures):
            raise TypeError("measures must contain only Measure objects")
        object.__setattr__(self, "taxonomies", taxonomies)
        object.__setattr__(self, "measures", measures)
        object.__setattr__(
            self, "_index", _DefinitionsIndex.build(taxonomies, measures)
        )

    def taxonomy(self, reference: str | UUID | Taxonomy) -> Taxonomy:
        """Return a taxonomy by code.

        UUID and object references remain temporarily supported; prefer
        :meth:`taxonomy_by_id` and :meth:`canonical_taxonomy` for those forms.
        """
        if isinstance(reference, str):
            return self._index.taxonomies.by_code(reference)
        if isinstance(reference, UUID):
            _warn_legacy_reference("taxonomy", "taxonomy_by_id")
            return self.taxonomy_by_id(reference)
        if isinstance(reference, Taxonomy):
            _warn_legacy_reference("taxonomy", "canonical_taxonomy")
            return self.canonical_taxonomy(reference)
        raise TypeError("taxonomy lookup requires a code")

    def taxonomy_by_id(self, identifier: UUID) -> Taxonomy:
        return self._index.taxonomies.by_id(identifier)

    def canonical_taxonomy(self, taxonomy: Taxonomy) -> Taxonomy:
        if not isinstance(taxonomy, Taxonomy):
            raise TypeError("taxonomy must be a Taxonomy")
        return self._index.taxonomies.canonical(taxonomy)

    def find_taxonomy(self, code: str) -> Taxonomy | None:
        return self._index.taxonomies.find(code)

    @overload
    def classification(self, taxonomy: str | Taxonomy, code: str) -> Classification: ...

    @overload
    def classification(
        self, taxonomy: str | UUID | Classification
    ) -> Classification: ...

    def classification(
        self,
        taxonomy: str | UUID | Taxonomy | Classification,
        code: str | object = _MISSING,
    ) -> Classification:
        """Return a classification by taxonomy and code.

        The one-argument, globally scoped form remains temporarily supported
        for compatibility, but becomes ambiguous when taxonomies reuse a code.
        """
        if code is not _MISSING:
            if not isinstance(code, str):
                raise TypeError("classification code must be a string")
            owner = self._taxonomy_scope(taxonomy)
            return owner.classification(code)

        warnings.warn(
            "Definitions.classification(reference) is deprecated; use "
            "classification(taxonomy, code), classification_by_id(), or "
            "canonical_classification()",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._legacy_classification(taxonomy)

    def classification_by_id(self, identifier: UUID) -> Classification:
        return self._index.classifications.by_id(identifier)

    def canonical_classification(
        self, classification: Classification
    ) -> Classification:
        if not isinstance(classification, Classification):
            raise TypeError("classification must be a Classification")
        return self._index.classifications.canonical(classification)

    def find_classification(
        self, taxonomy: str | Taxonomy, code: str
    ) -> Classification | None:
        owner = self._taxonomy_scope(taxonomy)
        return owner.find(code)

    def measure(self, reference: str | UUID | Measure) -> Measure:
        """Return a measure by code.

        UUID and object references remain temporarily supported; prefer
        :meth:`measure_by_id` and :meth:`canonical_measure` for those forms.
        """
        if isinstance(reference, str):
            return self._index.measures.by_code(reference)
        if isinstance(reference, UUID):
            _warn_legacy_reference("measure", "measure_by_id")
            return self.measure_by_id(reference)
        if isinstance(reference, Measure):
            _warn_legacy_reference("measure", "canonical_measure")
            return self.canonical_measure(reference)
        raise TypeError("measure lookup requires a code")

    def measure_by_id(self, identifier: UUID) -> Measure:
        return self._index.measures.by_id(identifier)

    def canonical_measure(self, measure: Measure) -> Measure:
        if not isinstance(measure, Measure):
            raise TypeError("measure must be a Measure")
        return self._index.measures.canonical(measure)

    def find_measure(self, code: str) -> Measure | None:
        return self._index.measures.find(code)

    def taxonomy_of(self, classification: Classification) -> Taxonomy:
        canonical = self.canonical_classification(classification)
        return self._index.classification_owners[canonical.id]

    def taxonomy_for(self, classification: str | UUID | Classification) -> Taxonomy:
        """Compatibility wrapper for :meth:`taxonomy_of`."""
        warnings.warn(
            "Definitions.taxonomy_for() is deprecated; use taxonomy_of() with "
            "a canonical Classification",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.taxonomy_of(self._legacy_classification(classification))

    def contains_definition_id(self, identifier: UUID) -> bool:
        return identifier in self._index.definition_ids

    def _taxonomy_scope(
        self, taxonomy: str | UUID | Taxonomy | Classification
    ) -> Taxonomy:
        if isinstance(taxonomy, str):
            return self.taxonomy(taxonomy)
        if isinstance(taxonomy, Taxonomy):
            return self.canonical_taxonomy(taxonomy)
        raise TypeError("taxonomy scope requires a taxonomy code or Taxonomy")

    def _legacy_classification(
        self, reference: str | UUID | Taxonomy | Classification
    ) -> Classification:
        if isinstance(reference, str):
            return self._index.classifications.by_code(reference)
        if isinstance(reference, UUID):
            return self.classification_by_id(reference)
        if isinstance(reference, Classification):
            return self.canonical_classification(reference)
        raise TypeError(
            "classification lookup requires a taxonomy and code; the legacy "
            "form accepts a code, UUID, or Classification"
        )


def _warn_legacy_reference(kind: str, replacement: str) -> None:
    warnings.warn(
        f"Definitions.{kind}(UUID | {kind.title()}) is deprecated; use "
        f"{replacement}()",
        DeprecationWarning,
        stacklevel=3,
    )
