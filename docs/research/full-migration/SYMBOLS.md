# Remaining-code symbol inventory

Static capture only. The [review proposal](../../history/FULL_MIGRATION_REVIEW.md) owns dispositions.
Each symbol must receive a behavior-contract row before its implementation is retired.
Private methods and fields are included to expose algorithms and mutation contracts.

## `src/rangekeeper/graph/graph.py`

Review group: `graph-domain`.

- `_Identified` — class, line 34.
- `_Identified.id` — field, line 35.
- `_index_by_id(items: Iterable[_I], kind: str)` — callable, line 42.
- `_group_ids_by(items: Iterable[_I], key: Callable[[_I], _H | None])` — callable, line 53.
- `Graph` — class, line 68.
- `Graph.definitions` — field, line 71.
- `Graph.entities` — field, line 72.
- `Graph.relationships` — field, line 73.
- `Graph.provenance` — field, line 74.
- `Graph._entities_by_id` — field, line 75.
- `Graph._relationships_by_id` — field, line 78.
- `Graph._graph_objects_by_id` — field, line 81.
- `Graph._relationship_ids_by_source` — field, line 84.
- `Graph._relationship_ids_by_target` — field, line 87.
- `Graph.__post_init__(self)` — callable, line 91.
- `Graph.assemblies(self)` — callable, line 162.
- `Graph.entity(self, entity: str | UUID | Entity)` — callable, line 167.
- `Graph.relationship(self, relationship: UUID | Relationship)` — callable, line 193.
- `Graph.apply(self, update: Update)` — callable, line 211.
- `Graph.find_entities(self, *, code: str | None=None, name: str | None=None, classification: UUID | Classification | None=None)` — callable, line 215.
- `Graph.source_of(self, relationship: UUID | Relationship)` — callable, line 239.
- `Graph.target_of(self, relationship: UUID | Relationship)` — callable, line 244.
- `Graph.outgoing_relationships(self, entity: str | UUID | Entity, *, classification: UUID | Classification | None=None)` — callable, line 249.
- `Graph.incoming_relationships(self, entity: str | UUID | Entity, *, classification: UUID | Classification | None=None)` — callable, line 263.
- `Graph.relationships_between(self, source: str | UUID | Entity, target: str | UUID | Entity, *, classification: UUID | Classification | None=None)` — callable, line 277.
- `Graph.entities_in(self, assembly: str | UUID | Assembly, *, recursive: bool=False)` — callable, line 296.
- `Graph.containing_assemblies(self, entity: str | UUID | Entity, *, recursive: bool=False)` — callable, line 318.
- `Graph.relationships_in(self, assembly: str | UUID | Assembly)` — callable, line 337.
- `Graph.view(self, *, entities: Iterable[str | UUID | Entity] | None=None, relationships: Iterable[UUID | Relationship] | None=None, assembly: str | UUID | Assembly | None=None)` — callable, line 351.
- `Graph._relationships_for(self, entity: str | UUID | Entity, *, index: Mapping[UUID, tuple[UUID, ...]], classification: UUID | Classification | None)` — callable, line 369.
- `Graph._validate_definition_references(self, entities: tuple[Entity, ...], relationships: tuple[Relationship, ...])` — callable, line 387.
- `Graph._validate_relationships(relationships: tuple[Relationship, ...], entities_by_id: Mapping[UUID, Entity])` — callable, line 402.
- `Graph._validate_assemblies(entities: tuple[Entity, ...], relationships_by_id: Mapping[UUID, Relationship], entities_by_id: Mapping[UUID, Entity])` — callable, line 413.

## `src/rangekeeper/graph/_catalog.py`

Review group: `graph-domain`.

- `CodedIdentified` — class, line 16.
- `CodedIdentified.id` — field, line 17.
- `CodedIdentified.code` — field, line 18.
- `Catalog` — class, line 25.
- `Catalog._by_code` — field, line 28.
- `Catalog._by_id` — field, line 29.
- `Catalog.item_type` — field, line 30.
- `Catalog.kind` — field, line 31.
- `Catalog.scope` — field, line 32.
- `Catalog.__init__(self, values: Iterable[C], item_type: type[C], kind: str, scope: str | None=None)` — callable, line 34.
- `Catalog.from_input(cls, values: Iterable[C] | Mapping[str, C], *, item_type: type[C], field: str, kind: str, scope: str | None=None)` — callable, line 59.
- `Catalog.__getitem__(self, code: str)` — callable, line 81.
- `Catalog.__iter__(self)` — callable, line 89.
- `Catalog.__len__(self)` — callable, line 92.
- `Catalog.__repr__(self)` — callable, line 95.
- `Catalog.__eq__(self, other: object)` — callable, line 98.
- `Catalog.__hash__(self)` — callable, line 103.
- `Catalog._by_id_lookup(self, identifier: UUID)` — callable, line 106.
- `Catalog._contains_id(self, identifier: UUID)` — callable, line 116.
- `Catalog._require_instance(self, value: C)` — callable, line 119.
- `Catalog._resolve(self, reference: str | UUID | C)` — callable, line 131.

## `src/rangekeeper/graph/entity.py`

Review group: `graph-domain`.

- `Entity` — class, line 16.
- `Entity.id` — field, line 19.
- `Entity.code` — field, line 20.
- `Entity.name` — field, line 21.
- `Entity.classification` — field, line 22.
- `Entity.characteristics` — field, line 23.
- `Entity.__post_init__(self)` — callable, line 25.
- `Entity.labels(self)` — callable, line 38.
- `Entity.measurements(self)` — callable, line 44.
- `Entity.features(self)` — callable, line 50.

## `src/rangekeeper/graph/relationship.py`

Review group: `graph-domain`.

- `Relationship` — class, line 17.
- `Relationship.id` — field, line 20.
- `Relationship.source_id` — field, line 21.
- `Relationship.target_id` — field, line 22.
- `Relationship.classification` — field, line 23.
- `Relationship.characteristics` — field, line 24.
- `Relationship.__post_init__(self)` — callable, line 26.
- `Relationship.labels(self)` — callable, line 36.
- `Relationship.measurements(self)` — callable, line 42.
- `Relationship.features(self)` — callable, line 48.
- `Relationship.between(cls, source: Entity, target: Entity, *, classification: Classification, characteristics: Characteristics | None=None, id: UUID | None=None)` — callable, line 54.

## `src/rangekeeper/graph/assembly.py`

Review group: `graph-domain`.

- `Assembly` — class, line 18.
- `Assembly.entity_ids` — field, line 21.
- `Assembly.relationship_ids` — field, line 22.
- `Assembly.__post_init__(self)` — callable, line 24.
- `Assembly.of(cls, *, entities: Iterable[Entity]=(), relationships: Iterable[Relationship]=(), id: UUID | None=None, code: str | None=None, name: str | None=None, classification: Classification | None=None, characteristics: Characteristics | None=None)` — callable, line 38.

## `src/rangekeeper/graph/characteristics.py`

Review group: `graph-domain`.

- `_freeze_items(values: Mapping[str, T], *, item_type: type[T], key_of: Callable[[T], str], field_name: str)` — callable, line 21.
- `Label` — class, line 41.
- `Label.id` — field, line 44.
- `Label.key` — field, line 45.
- `Label.classifications` — field, line 46.
- `Label.__post_init__(self)` — callable, line 48.
- `Measurement` — class, line 61.
- `Measurement.id` — field, line 64.
- `Measurement.measure` — field, line 65.
- `Measurement.quantity` — field, line 66.
- `Measurement.__post_init__(self)` — callable, line 68.
- `Feature` — class, line 77.
- `Feature.id` — field, line 80.
- `Feature.name` — field, line 81.
- `Feature.value` — field, line 82.
- `Feature.__post_init__(self)` — callable, line 84.
- `Characteristics` — class, line 90.
- `Characteristics.labels` — field, line 93.
- `Characteristics.measurements` — field, line 94.
- `Characteristics.features` — field, line 95.
- `Characteristics.__post_init__(self)` — callable, line 97.
- `Characteristics.label(self, key: str)` — callable, line 129.
- `Characteristics.measurement(self, measure: Measure | str)` — callable, line 136.
- `Characteristics.feature(self, name: str)` — callable, line 144.
- `Characteristics.items(self)` — callable, line 152.

## `src/rangekeeper/graph/classification.py`

Review group: `graph-domain`.

- `Classification` — class, line 13.
- `Classification.id` — field, line 16.
- `Classification.code` — field, line 17.
- `Classification.name` — field, line 18.
- `Classification.definition` — field, line 19.
- `Classification.parent` — field, line 20.
- `Classification.__post_init__(self)` — callable, line 22.
- `Classification.__str__(self)` — callable, line 30.

## `src/rangekeeper/graph/taxonomy.py`

Review group: `graph-domain`.

- `Taxonomy` — class, line 17.
- `Taxonomy.id` — field, line 20.
- `Taxonomy.code` — field, line 21.
- `Taxonomy.name` — field, line 22.
- `Taxonomy.classifications` — field, line 23.
- `Taxonomy.definition` — field, line 24.
- `Taxonomy._root_id` — field, line 25.
- `Taxonomy._children_by_parent_id` — field, line 26.
- `Taxonomy.__init__(self, *, code: str, name: str, classifications: Iterable[Classification] | Mapping[str, Classification], id: UUID | None=None, definition: str | None=None)` — callable, line 32.
- `Taxonomy._validate(self)` — callable, line 61.
- `Taxonomy.root(self)` — callable, line 108.
- `Taxonomy.children(self, classification: Classification)` — callable, line 113.
- `Taxonomy.ancestors(self, classification: Classification)` — callable, line 119.
- `Taxonomy.descendants(self, classification: Classification)` — callable, line 129.
- `Taxonomy.is_a(self, classification: Classification, ancestor: Classification)` — callable, line 141.

## `src/rangekeeper/graph/definitions.py`

Review group: `graph-domain`.

- `Definitions` — class, line 25.
- `Definitions.taxonomies` — field, line 28.
- `Definitions.measures` — field, line 29.
- `Definitions._definition_by_id` — field, line 30.
- `Definitions._taxonomy_by_classification_id` — field, line 35.
- `Definitions.__init__(self, *, taxonomies: Iterable[Taxonomy] | Mapping[str, Taxonomy]=(), measures: Iterable[Measure] | Mapping[str, Measure]=())` — callable, line 41.
- `Definitions.taxonomy_for(self, classification: UUID | Classification)` — callable, line 94.
- `Definitions._resolve_classification(self, classification: UUID | Classification | None)` — callable, line 103.
- `Definitions._resolve_measure(self, measure: str | UUID | Measure)` — callable, line 133.
- `Definitions._classification_matches(self, actual: Classification | None, requested: Classification | None)` — callable, line 138.

## `src/rangekeeper/graph/provenance.py`

Review group: `graph-domain`.

- `EntityState` — class, line 45.
- `EntityState.code` — field, line 48.
- `EntityState.name` — field, line 49.
- `EntityState.classification` — field, line 50.
- `EntityState.from_entity(cls, entity: Entity)` — callable, line 53.
- `AssemblyState` — class, line 66.
- `AssemblyState.entity_ids` — field, line 69.
- `AssemblyState.relationship_ids` — field, line 70.
- `AssemblyState.from_assembly(cls, assembly: Assembly)` — callable, line 73.
- `RelationshipState` — class, line 88.
- `RelationshipState.source_id` — field, line 91.
- `RelationshipState.target_id` — field, line 92.
- `RelationshipState.classification` — field, line 93.
- `RelationshipState.from_relationship(cls, relationship: Relationship)` — callable, line 96.
- `ReconciliationStatus` — class, line 108.
- `ReconciliationStatus.PROVISIONAL` — class-attribute, line 111.
- `ReconciliationStatus.CONFIRMED` — class-attribute, line 112.
- `Reconciliation` — class, line 116.
- `Reconciliation.selected` — field, line 119.
- `Reconciliation.status` — field, line 120.
- `Reconciliation.method` — field, line 121.
- `Reconciliation.__post_init__(self)` — callable, line 123.
- `FactStatus` — class, line 132.
- `FactStatus.DETERMINATE` — class-attribute, line 135.
- `FactStatus.CONFLICT` — class-attribute, line 136.
- `FactStatus.RECONCILED` — class-attribute, line 137.
- `FactTarget` — field, line 140.
- `Fact` — class, line 145.
- `Fact.target` — field, line 152.
- `Fact.claims` — field, line 153.
- `Fact.reconciliation` — field, line 154.
- `Fact.__post_init__(self)` — callable, line 156.
- `Fact.status(self)` — callable, line 178.
- `Fact.current_claim(self)` — callable, line 190.
- `_values_equal(left: object, right: object)` — callable, line 201.
- `_index_evidence(facts: Iterable[Fact[Any]])` — callable, line 219.
- `_index_claims(roots)` — callable, line 229.
- `_validate_fact_values(facts: Iterable[Fact[Any]])` — callable, line 239.
- `Provenance` — class, line 270.
- `Provenance.facts` — field, line 273.
- `Provenance._facts_by_target_id` — field, line 274.
- `Provenance._claims_by_id` — field, line 279.
- `Provenance._sources_by_id` — field, line 284.
- `Provenance.__post_init__(self)` — callable, line 290.
- `Provenance.claims(self)` — callable, line 315.
- `Provenance.sources(self)` — callable, line 321.
- `Provenance.fact_for(self, target: UUID | FactTarget)` — callable, line 326.

## `src/rangekeeper/graph/revision.py`

Review group: `graph-domain`.

- `Modification` — class, line 26.
- `Modification.before` — field, line 29.
- `Modification.after` — field, line 30.
- `Delta` — class, line 34.
- `Delta.added` — field, line 37.
- `Delta.removed` — field, line 38.
- `Delta.modified` — field, line 39.
- `Delta.__post_init__(self)` — callable, line 41.
- `Delta.changed(self)` — callable, line 50.
- `Diff` — class, line 57.
- `Diff.taxonomies` — field, line 60.
- `Diff.classifications` — field, line 61.
- `Diff.measures` — field, line 62.
- `Diff.entities` — field, line 63.
- `Diff.labels` — field, line 64.
- `Diff.measurements` — field, line 65.
- `Diff.features` — field, line 66.
- `Diff.relationships` — field, line 67.
- `Diff.facts` — field, line 68.
- `Diff.claims` — field, line 69.
- `Diff.changed(self)` — callable, line 72.
- `Diff.between(cls, parent: Graph, child: Graph)` — callable, line 92.
- `Revision` — class, line 133.
- `Revision.id` — field, line 136.
- `Revision.graph` — field, line 137.
- `Revision.parent_ids` — field, line 138.
- `Revision.created_at` — field, line 139.
- `Revision.created_by` — field, line 140.
- `Revision.message` — field, line 141.
- `Revision.__post_init__(self)` — callable, line 143.
- `Revision.diff(self, parent: Revision)` — callable, line 162.
- `_changes(parent: Mapping[UUID, T], child: Mapping[UUID, T])` — callable, line 172.
- `_equal(left: object, right: object)` — callable, line 188.
- `_classifications_by_id(graph: Graph)` — callable, line 196.
- `_characteristics_by_id(graph: Graph)` — callable, line 204.

## `src/rangekeeper/graph/update.py`

Review group: `graph-domain`.

- `Update` — class, line 28.
- `Update.definitions` — field, line 31.
- `Update.add_entities` — field, line 32.
- `Update.replace_entities` — field, line 33.
- `Update.remove_entity_ids` — field, line 34.
- `Update.add_relationships` — field, line 35.
- `Update.replace_relationships` — field, line 36.
- `Update.remove_relationship_ids` — field, line 37.
- `Update.add_facts` — field, line 38.
- `Update.replace_facts` — field, line 39.
- `Update.remove_fact_target_ids` — field, line 40.
- `Update.cascade` — field, line 41.
- `Update.__post_init__(self)` — callable, line 43.
- `_RemovalScope` — class, line 64.
- `_RemovalScope.entity_ids` — field, line 67.
- `_RemovalScope.relationship_ids` — field, line 68.
- `_RemovalScope.fact_target_ids` — field, line 69.
- `_RemovalScope.from_update(cls, update: Update)` — callable, line 72.
- `_Candidate` — class, line 83.
- `_Candidate.definitions` — field, line 86.
- `_Candidate.entities` — field, line 87.
- `_Candidate.relationships` — field, line 88.
- `_Candidate.facts` — field, line 89.
- `_Candidate.from_graph(cls, graph: Graph, *, definitions: Definitions)` — callable, line 92.
- `_Candidate.overlay(self, update: Update)` — callable, line 107.
- `_Candidate.remove(self, removals: _RemovalScope)` — callable, line 119.
- `_Candidate.build(self)` — callable, line 129.
- `_validate_update_shape(update: Update)` — callable, line 142.
- `_validate_operation_conflicts(update: Update)` — callable, line 170.
- `_apply(graph: Graph, update: Update)` — callable, line 215.
- `_validate_operations_against_source(candidate: _Candidate, update: Update)` — callable, line 237.
- `_expand_cascade(graph: Graph, update: Update, candidate: _Candidate, removals: _RemovalScope)` — callable, line 282.
- `_cascade_relationships(update: Update, candidate: _Candidate, removals: _RemovalScope)` — callable, line 296.
- `_cascade_facts(update: Update, candidate: _Candidate, removals: _RemovalScope, removed_target_ids: set[UUID])` — callable, line 323.
- `_cascade_assemblies(update: Update, candidate: _Candidate, removals: _RemovalScope)` — callable, line 345.
- `_removed_graph_object_ids(graph: Graph, removals: _RemovalScope)` — callable, line 393.
- `_validate_remaining_dependencies(graph: Graph, candidate: _Candidate, removals: _RemovalScope)` — callable, line 412.

## `src/rangekeeper/adapters/__init__.py`

Review group: `graph-domain`.

No classes or functions; inspect imports, re-exports or commented residue.

## `src/rangekeeper/adapters/json.py`

Review group: `graph-domain`.

- `_fields(obj)` — callable, line 103.
- `dumps(graph: Graph)` — callable, line 120.
- `_unique(pairs)` — callable, line 230.
- `loads(content: str)` — callable, line 239.
- `write(graph: Graph, path: Path)` — callable, line 413.
- `read(path: Path)` — callable, line 435.

## `src/rangekeeper/graph/table.py`

Review group: `graph-domain`.

- `Table` — class, line 37.
- `Table.from_view(cls, view: View, *, fields: Iterable[str]=_DEFAULT_FIELDS, labels: Iterable[str]=(), measures: Mapping[Measure | str, pint.Unit | str | None] | None=None, features: Iterable[str]=())` — callable, line 41.
- `Table.from_arborescence(cls, view: View, *, fields: Iterable[str]=_DEFAULT_FIELDS, labels: Iterable[str]=(), measures: Mapping[Measure | str, pint.Unit | str | None] | None=None, features: Iterable[str]=())` — callable, line 103.
- `_measurement_projections(view: View, measures: Mapping[Measure | str, pint.Unit | str | None] | None)` — callable, line 150.
- `_entity_value(entity: Entity, field_name: str, *, view: View)` — callable, line 184.

## `src/rangekeeper/graph/legacy/__init__.py`

Review group: `graph-domain`.

No classes or functions; inspect imports, re-exports or commented residue.

## `src/rangekeeper/graph/legacy/view.py`

Review group: `graph-domain`.

- `View` — class, line 25.
- `View.graph` — field, line 28.
- `View._entity_ids` — field, line 29.
- `View._relationship_ids` — field, line 30.
- `View.__init__(self, graph: Graph, *, entities: Iterable[str | UUID | Entity] | None=None, relationships: Iterable[UUID | Relationship] | None=None, assembly: str | UUID | Assembly | None=None)` — callable, line 32.
- `View.entities(self)` — callable, line 59.
- `View.relationships(self)` — callable, line 67.
- `View.roots(self)` — callable, line 77.
- `View.leaves(self)` — callable, line 84.
- `View.is_arborescence(self)` — callable, line 91.
- `View.filter(self, *, entity_classification: UUID | Classification | None=None, relationship_classification: UUID | Classification | None=None, predicate: Callable[[Entity], bool] | None=None)` — callable, line 97.
- `View.predecessors(self, entity: str | UUID | Entity, *, relationship_classification: UUID | Classification | None=None)` — callable, line 118.
- `View.successors(self, entity: str | UUID | Entity, *, relationship_classification: UUID | Classification | None=None)` — callable, line 137.
- `View.aggregate(self, reduction: Reduction[T])` — callable, line 156.
- `View._topology(self)` — callable, line 163.
- `View._require_arborescence(self)` — callable, line 181.
- `View._from_ids(cls, graph: Graph, entity_ids: Iterable[UUID], relationship_ids: Iterable[UUID])` — callable, line 192.
- `View._resolve_view_entity_id(self, entity: str | UUID | Entity)` — callable, line 208.
- `_select(graph: Graph, *, entities: Iterable[str | UUID | Entity] | None, relationships: Iterable[UUID | Relationship] | None, assembly: str | UUID | Assembly | None)` — callable, line 215.
- `_filter(graph: Graph, entity_ids: set[UUID], relationship_ids: set[UUID], *, entity_classification: UUID | Classification | None, relationship_classification: UUID | Classification | None, predicate: Callable[[Entity], bool] | None)` — callable, line 264.
- `_validate(graph: Graph, entity_ids: set[UUID], relationship_ids: set[UUID])` — callable, line 314.

## `src/rangekeeper/graph/legacy/reduction.py`

Review group: `graph-domain`.

- `Coverage` — class, line 41.
- `Coverage.selected` — field, line 44.
- `Coverage.measured` — field, line 45.
- `Coverage.missing` — field, line 46.
- `Coverage.complete(self)` — callable, line 49.
- `Coverage.status(self)` — callable, line 53.
- `Aggregation` — class, line 64.
- `Aggregation.view` — field, line 67.
- `Aggregation._values` — field, line 68.
- `Aggregation._coverage` — field, line 70.
- `Aggregation._known_values` — field, line 71.
- `Aggregation._is_sum` — field, line 72.
- `Aggregation.__post_init__(self)` — callable, line 74.
- `Aggregation.root_value(self)` — callable, line 90.
- `Aggregation.__getitem__(self, entity: str | UUID | Entity)` — callable, line 95.
- `Aggregation.__len__(self)` — callable, line 101.
- `Aggregation.__iter__(self)` — callable, line 104.
- `Aggregation.items(self)` — callable, line 107.
- `Aggregation.coverage(self, entity: str | UUID | Entity)` — callable, line 112.
- `Aggregation.available_value(self, entity: str | UUID | Entity)` — callable, line 116.
- `Aggregation.known_subtotal(self, entity: str | UUID | Entity)` — callable, line 120.
- `Reduction` — class, line 127.
- `Reduction._execute(self, view: View)` — callable, line 131.
- `by_measure(reference: str | Measure, *, contributors: Callable[[Entity], bool] | None=None, require_measurement: bool=False)` — callable, line 135.
- `by_feature(name: str, *, reducer: Callable[[tuple[T, ...]], R])` — callable, line 153.
- `_MeasureReduction` — class, line 169.
- `_MeasureReduction.reference` — field, line 170.
- `_MeasureReduction.contributors` — field, line 171.
- `_MeasureReduction.require_measurement` — field, line 172.
- `_MeasureReduction._execute(self, view: View)` — callable, line 174.
- `_FeatureReduction` — class, line 199.
- `_FeatureReduction.name` — field, line 200.
- `_FeatureReduction.reducer` — field, line 201.
- `_FeatureReduction._execute(self, view: View)` — callable, line 203.
- `collect(values: tuple[T, ...])` — callable, line 211.
- `distinct(values: tuple[T, ...])` — callable, line 216.
- `mode(values: tuple[T, ...])` — callable, line 225.
- `_traverse(view: View, *, extractor: Callable[[Entity], T | None], reducer: Callable[[tuple[T, ...]], R], contributors: Callable[[Entity], bool] | None=None, require_value: bool=False, is_sum: bool=False)` — callable, line 242.
- `_mean(values: tuple[pint.Quantity, ...])` — callable, line 289.
- `_MEASUREMENT_REDUCERS` — field, line 298.

## `src/rangekeeper/graph/__init__.py`

Review group: `graph-domain`.

- `__getattr__(name: str)` — callable, line 110.
- `__dir__()` — callable, line 121.

## `src/rangekeeper/graph/errors.py`

Review group: `graph-domain`.

- `SelectionError` — class, line 5.
- `HierarchyError` — class, line 9.
- `HierarchyError.__init__(self, code: str, message: str, *, ids: Iterable[UUID]=())` — callable, line 12.
- `AggregationError` — class, line 18.
- `GraphError` — class, line 39.
- `IdentityConflictError` — class, line 43.
- `AmbiguousLookupError` — class, line 47.
- `UnknownDefinitionError` — class, line 51.
- `UnknownDefinitionError.__init__(self, kind: str, reference: object, *, scope: str | None=None)` — callable, line 54.
- `CatalogInstanceError` — class, line 64.
- `CatalogInstanceError.__init__(self, kind: str, identifier: object, *, scope: str | None=None)` — callable, line 67.
- `MissingEntityError` — class, line 79.
- `MissingRelationshipError` — class, line 83.
- `MissingFactError` — class, line 87.
- `GraphDependencyError` — class, line 91.
- `GraphDependencyError.__init__(self, target_kind: str, target_id: UUID, *, relationship_ids: Iterable[UUID]=(), assembly_ids: Iterable[UUID]=(), fact_target_ids: Iterable[UUID]=())` — callable, line 94.
- `InvalidAssemblyError` — class, line 120.
- `InvalidAggregationError` — class, line 124.
- `_format_ids(ids: Iterable[UUID])` — callable, line 128.

## `src/rangekeeper/measure.py`

Review group: `units`.

- `Index` — class, line 15.
- `Index.registry` — class-attribute, line 16.
- `QuantityKind` — class, line 21.
- `QuantityKind.AREA` — class-attribute, line 22.
- `QuantityKind.LENGTH` — class-attribute, line 23.
- `QuantityKind.CURRENCY` — class-attribute, line 24.
- `QuantityKind.COUNT` — class-attribute, line 25.
- `QuantityKind.RATIO` — class-attribute, line 26.
- `QuantityKind.OTHER` — class-attribute, line 27.
- `AggregationRule` — class, line 30.
- `AggregationRule.SUM` — class-attribute, line 31.
- `AggregationRule.MEAN` — class-attribute, line 32.
- `AggregationRule.MEDIAN` — class-attribute, line 33.
- `AggregationRule.MINIMUM` — class-attribute, line 34.
- `AggregationRule.MAXIMUM` — class-attribute, line 35.
- `AggregationRule.NONE` — class-attribute, line 36.
- `Measure` — class, line 40.
- `Measure.id` — field, line 43.
- `Measure.code` — field, line 44.
- `Measure.name` — field, line 45.
- `Measure.units` — field, line 46.
- `Measure.quantity_kind` — field, line 47.
- `Measure.aggregation` — field, line 48.
- `Measure.definition` — field, line 49.
- `Measure.tags` — field, line 50.
- `Measure.__post_init__(self)` — callable, line 52.
- `Measure._validate_quantity_kind(self)` — callable, line 69.
- `Measure.validate_quantity(self, quantity: pint.Quantity)` — callable, line 90.
- `to_filtered(quantity: pint.Quantity, exclude=('percent',))` — callable, line 97.
- `remove_dimension(quantity: pint.Quantity, dimension: str, registry: pint.UnitRegistry | None=None)` — callable, line 104.
- `multiply_units(units: Iterable[pint.Unit], registry: pint.UnitRegistry | None=None)` — callable, line 125.
- `register_currency(registry: pint.UnitRegistry, code: str | None=None)` — callable, line 136.

## `src/rangekeeper/flux.py`

Review group: `temporal`.

- `_format_series(series: pd.Series, units: pint.Unit, to_datestamps: bool=True, decimals: int=2)` — callable, line 17.
- `Flow` — class, line 52.
- `Flow.name` — field, line 53.
- `Flow.movements` — field, line 54.
- `Flow.units` — field, line 55.
- `Flow.__init__(self, movements: pd.Series, units: Optional[pint.Unit]=None, name: str=None)` — callable, line 61.
- `Flow.__str__(self)` — callable, line 114.
- `Flow._repr_html_(self)` — callable, line 117.
- `Flow.duplicate(self, name: str=None)` — callable, line 122.
- `Flow.display(self, tablefmt: str='github', decimals: int=2)` — callable, line 136.
- `Flow.plot(self, bounds: Optional[Tuple[float, float]]=None, normalize: bool=False, *args, **kwargs)` — callable, line 161.
- `Flow.from_sequence(cls, sequence: pd.PeriodIndex, data: [float], units: Optional[pint.Unit]=None, name: str=None)` — callable, line 179.
- `Flow.from_dict(cls, movements: Dict[datetime.date | pd.Timestamp, float], units: pint.Unit, name: str=None)` — callable, line 208.
- `Flow.from_projection(cls, value: Union[float, pint.Quantity, rk.distribution.Form], proj: rk.projection, units: pint.Unit=None, name: str=None)` — callable, line 231.
- `Flow.negate(self)` — callable, line 275.
- `Flow.collapse(self)` — callable, line 285.
- `Flow.total(self)` — callable, line 296.
- `Flow.pv(self, frequency: rk.duration.Type, rate: float, name: str=None)` — callable, line 302.
- `Flow.irr(self, registry: pint.UnitRegistry=None)` — callable, line 325.
- `Flow.npv(self, rate: Union[float, pint.Quantity])` — callable, line 345.
- `Flow.diff(self, with_previous: bool=True, name: str=None)` — callable, line 362.
- `Flow.resample(self, frequency: rk.duration.Type, origin: Optional[pd.Timestamp, datetime.date]=None, sum: bool=True)` — callable, line 384.
- `Flow.to_periods(self, index: pd.PeriodIndex, origin: Optional[pd.Timestamp, datetime.date]=None)` — callable, line 472.
- `Flow.earliest(self)` — callable, line 516.
- `Flow.latest(self)` — callable, line 528.
- `Flow.trim_empty(self, name: str=None)` — callable, line 540.
- `Flow.trim_to_span(self, span: rk.duration.Span, name: str=None)` — callable, line 556.
- `Flow.to_stream(self, frequency: rk.duration.Type, name: str=None)` — callable, line 573.
- `Flow.clean(self, zeroes: bool=False)` — callable, line 588.
- `Stream` — class, line 604.
- `Stream.name` — field, line 605.
- `Stream.flows` — field, line 606.
- `Stream.frequency` — field, line 607.
- `Stream.start_date` — field, line 608.
- `Stream.end_date` — field, line 609.
- `Stream.frame` — field, line 610.
- `Stream.__init__(self, flows: List[Flow], frequency: rk.duration.Type, name: str=None)` — callable, line 616.
- `Stream.__str__(self)` — callable, line 672.
- `Stream._repr_html_(self)` — callable, line 675.
- `Stream._format_flows(self, decimals: int=2)` — callable, line 680.
- `Stream.display(self, tablefmt: str='github', decimals: int=2)` — callable, line 710.
- `Stream.__add__(self, other)` — callable, line 741.
- `Stream.is_homogeneous(self)` — callable, line 755.
- `Stream.duplicate(self)` — callable, line 758.
- `Stream.from_DataFrame(cls, name: str, data: pd.DataFrame, units: pint.Unit)` — callable, line 766.
- `Stream.plot(self, flows: Dict[str, tuple]=None, normalize: bool=False)` — callable, line 782.
- `Stream.extract(self, name: str)` — callable, line 924.
- `Stream.sum(self, name: str=None)` — callable, line 940.
- `Stream.product(self, name: str=None, registry: pint.UnitRegistry=None)` — callable, line 966.
- `Stream.min(self, name: str=None)` — callable, line 994.
- `Stream.max(self, name: str=None)` — callable, line 1019.
- `Stream.collapse(self)` — callable, line 1044.
- `Stream.total(self)` — callable, line 1056.
- `Stream.extend(self, flows: List[Flow])` — callable, line 1068.
- `Stream.resample(self, frequency: rk.duration.Type)` — callable, line 1086.
- `Stream.trim_to_span(self, span: rk.duration.Span)` — callable, line 1098.
- `Stream.merge(cls, streams, name: str, frequency: rk.duration.Type)` — callable, line 1111.

## `src/rangekeeper/duration.py`

Review group: `temporal`.

- `Type` — class, line 13.
- `Type.DECADE` — class-attribute, line 14.
- `Type.SEMIDECADE` — class-attribute, line 15.
- `Type.BIENNIUM` — class-attribute, line 16.
- `Type.YEAR` — class-attribute, line 17.
- `Type.SEMIYEAR` — class-attribute, line 18.
- `Type.QUARTER` — class-attribute, line 19.
- `Type.MONTH` — class-attribute, line 20.
- `Type.BIWEEK` — class-attribute, line 21.
- `Type.WEEK` — class-attribute, line 22.
- `Type.DAY` — class-attribute, line 23.
- `Type.from_value(value: str)` — callable, line 26.
- `Type.period(type: Type)` — callable, line 51.
- `Type.offset(type: Type)` — callable, line 76.
- `measure(start_date: datetime.date, end_date: datetime.date, duration: Type, inclusive: bool=False)` — callable, line 101.
- `offset(date: datetime.date, duration: Type=Type.DAY, amount: int=1)` — callable, line 155.
- `Period` — class, line 215.
- `Period.include_date(date: datetime.date, duration: Type)` — callable, line 217.
- `Period.to_sequence(period: pd.Period)` — callable, line 229.
- `Period.yearly_count(duration: Type)` — callable, line 236.
- `Sequence` — class, line 254.
- `Sequence.from_datestamps(datestamps: pd.DatetimeIndex, frequency: Type)` — callable, line 256.
- `Sequence.from_bounds(include_start: datetime.date, frequency: Type, bound: Union[datetime.date, int])` — callable, line 266.
- `Sequence.to_datestamps(sequence: pd.PeriodIndex, end: bool=True)` — callable, line 310.
- `Sequence.extend(sequence: pd.PeriodIndex, start_offset: Optional[int]=None, end_offset: Optional[int]=None)` — callable, line 327.
- `Sequence.to_range_index(sequence: pd.PeriodIndex, start_period: pd.Period=None, end_period: pd.Period=None)` — callable, line 354.
- `Span` — class, line 392.
- `Span.start_date` — field, line 393.
- `Span.end_date` — field, line 394.
- `Span.name` — field, line 395.
- `Span.__init__(self, start_date: datetime.date | pd.Timestamp, end_date: datetime.date | pd.Timestamp=None, name: str=None)` — callable, line 400.
- `Span.__str__(self)` — callable, line 438.
- `Span.__repr__(self)` — callable, line 445.
- `Span.merge(cls, name: str, spans: [Span])` — callable, line 449.
- `Span.extend(self, duration: Type, amount: int, bound: str='end', name: str=None)` — callable, line 466.
- `Span.to_sequence(self, frequency: Type)` — callable, line 514.
- `Span.duration(self, type: Type, inclusive: bool=False)` — callable, line 524.
- `Span.from_duration(cls, name: str, date: datetime.date | pd.Timestamp, duration: Type, amount: int=1)` — callable, line 538.
- `Span.from_date_sequence(cls, names: [str], dates: [datetime.date])` — callable, line 588.
- `Span.from_duration_sequence(cls, duration: Type, names: [str], amounts: [int], start_date: datetime.date)` — callable, line 630.
- `Span.from_sequence(cls, sequence: pd.PeriodIndex)` — callable, line 657.

## `src/rangekeeper/distribution.py`

Review group: `numerical`.

- `Type` — class, line 9.
- `Type.UNIFORM` — class-attribute, line 10.
- `Type.TRIANGULAR` — class-attribute, line 11.
- `Type.PERT` — class-attribute, line 13.
- `Form` — class, line 16.
- `Form.type` — field, line 17.
- `Form.__init__(self, generator: Optional[np.random.Generator]=None)` — callable, line 19.
- `Form.sample(self, size: int=1)` — callable, line 23.
- `Form.interval_density(self, parameters: [float])` — callable, line 43.
- `Form.cumulative_density(self, parameters: [float])` — callable, line 62.
- `Symmetric` — class, line 72.
- `Symmetric.__init__(self, type: Type, residual: float, mean: float=0, generator: Optional[np.random.Generator]=None)` — callable, line 73.
- `Symmetric._distribution(self)` — callable, line 100.
- `Symmetric.interval_density(self, parameters: [float])` — callable, line 112.
- `Symmetric.cumulative_density(self, parameters: [float])` — callable, line 115.
- `Uniform` — class, line 119.
- `Uniform.__init__(self, lower: float=0.0, range: float=1.0, generator: Optional[np.random.Generator]=None)` — callable, line 127.
- `Uniform.symmetric(cls, mean: float, residual: float, generator: Optional[np.random.Generator]=None)` — callable, line 138.
- `Uniform.interval_density(self, parameters: [float])` — callable, line 146.
- `Uniform.cumulative_density(self, parameters: [float])` — callable, line 149.
- `Triangular` — class, line 153.
- `Triangular.__init__(self, lower: float=0.0, upper: float=1.0, mode: float=0.5, generator: Optional[np.random.Generator]=None)` — callable, line 158.
- `Triangular.symmetric(cls, mode: float, residual: float)` — callable, line 176.
- `Triangular.interval_density(self, parameters: [float])` — callable, line 179.
- `Triangular.cumulative_density(self, parameters: [float])` — callable, line 182.
- `PERT` — class, line 186.
- `PERT.__init__(self, peak: float=0.5, weighting: float=4.0, minimum: float=0.0, maximum: float=1.0, generator: Optional[np.random.Generator]=None)` — callable, line 203.
- `PERT.symmetric(cls, peak: float, residual: float)` — callable, line 241.
- `PERT.interval_density(self, parameters: [float])` — callable, line 246.
- `PERT.cumulative_density(self, parameters: [float])` — callable, line 249.

## `src/rangekeeper/extrapolation.py`

Review group: `numerical`.

- `Type` — class, line 10.
- `Type.STRAIGHT_LINE` — class-attribute, line 11.
- `Type.COMPOUNDING` — class-attribute, line 12.
- `Type.RECURRING` — class-attribute, line 13.
- `Type.DYNAMIC` — class-attribute, line 16.
- `Form` — class, line 19.
- `Form.type` — field, line 20.
- `Form.terms(self, sequence: pd.RangeIndex)` — callable, line 26.
- `StraightLine` — class, line 33.
- `StraightLine.slope` — field, line 34.
- `StraightLine.__init__(self, slope: float)` — callable, line 40.
- `StraightLine.terms(self, sequence: pd.RangeIndex)` — callable, line 44.
- `Recurring` — class, line 51.
- `Recurring.__init__(self)` — callable, line 52.
- `Compounding` — class, line 57.
- `Compounding.rate` — field, line 58.
- `Compounding.__init__(self, rate: float)` — callable, line 64.
- `Compounding.terms(self, sequence: pd.RangeIndex)` — callable, line 68.
- `Dynamic` — class, line 75.
- `Dynamic.series` — field, line 76.
- `Dynamic.__init__(self, series: pd.Series)` — callable, line 78.
- `Dynamic.terms(self, sequence: pd.RangeIndex)` — callable, line 82.

## `src/rangekeeper/projection.py`

Review group: `numerical`.

- `Padding` — class, line 15.
- `Padding.NIL` — class-attribute, line 19.
- `Padding.UNITIZE` — class-attribute, line 20.
- `Padding.EXTEND` — class-attribute, line 21.
- `Projection` — class, line 24.
- `Projection.sequence` — field, line 25.
- `Projection.bounds` — field, line 26.
- `Projection.__init__(self, sequence: pd.PeriodIndex, bounds: Tuple[pd.Period, pd.Period]=None)` — callable, line 28.
- `Projection._pad(value: float, length: int, type: Optional[Padding])` — callable, line 43.
- `Extrapolation` — class, line 59.
- `Extrapolation.form` — field, line 60.
- `Extrapolation.padding` — field, line 61.
- `Extrapolation.__init__(self, form: rk.extrapolation.Form, sequence: pd.PeriodIndex, bounds: Tuple[pd.Period, pd.Period]=None, padding: Tuple[Padding, Padding]=None)` — callable, line 63.
- `Extrapolation.terms(self)` — callable, line 87.
- `Distribution` — class, line 114.
- `Distribution.form` — field, line 115.
- `Distribution.__init__(self, form: rk.distribution.Form, sequence: pd.PeriodIndex, bounds: Tuple[pd.Period, pd.Period]=None)` — callable, line 117.
- `Distribution._seq_to_params(self)` — callable, line 147.
- `Distribution.interval_density(self)` — callable, line 156.
- `Distribution.cumulative_density(self)` — callable, line 168.

## `src/rangekeeper/formula/__init__.py`

Review group: `numerical`.

No classes or functions; inspect imports, re-exports or commented residue.

## `src/rangekeeper/formula/financial.py`

Review group: `numerical`.

- `Account` — class, line 14.
- `Account.startings` — field, line 15.
- `Account.endings` — field, line 16.
- `Account.overdraft` — field, line 17.
- `Account.interest` — field, line 18.
- `Account._calculate(starting: float, transactions: numba.typed.List, rates: numba.typed.List, type: str, arrears: bool=False)` — callable, line 22.
- `Account.Type` — class, line 90.
- `Account.Type.SIMPLE` — class-attribute, line 91.
- `Account.Type.COMPOUND` — class-attribute, line 92.
- `Account.Type.CAPITALIZED` — class-attribute, line 93.
- `Account.__init__(self, transactions: rk.flux.Flow, frequency: rk.duration.Type, starting: Union[float, pint.Quantity]=0.0, rate: Union[float, rk.flux.Flow]=0.0, type: Type=Type.SIMPLE, arrears: bool=False, name: str='')` — callable, line 95.
- `Account.diff(self, name: str=None)` — callable, line 182.

## `src/rangekeeper/dynamics/__init__.py`

Review group: `scenarios`.

No classes or functions; inspect imports, re-exports or commented residue.

## `src/rangekeeper/dynamics/black_swan.py`

Review group: `scenarios`.

- `BlackSwan` — class, line 10.
- `BlackSwan.__init__(self, sequence: pd.PeriodIndex, likelihood: float, dissipation_rate: float, probability: rk.distribution.Form, impact: float)` — callable, line 11.
- `BlackSwan.generate(self)` — callable, line 39.
- `BlackSwan.calculate_black_swan_effects(likelihood: float, dissipation_rate: float, events: [float])` — callable, line 51.

## `src/rangekeeper/dynamics/cyclicality.py`

Review group: `scenarios`.

- `Enumerate` — class, line 14.
- `Enumerate.sine(period: float, phase: float, amplitude: float, num_periods: int)` — callable, line 17.
- `Enumerate.asymmetric_sine(period: float, phase: float, amplitude: float, parameter: float, num_periods: int, precision: float, bound: float)` — callable, line 38.
- `Cycle` — class, line 79.
- `Cycle.__init__(self, period: float, phase: float, amplitude: float)` — callable, line 80.
- `Cycle.__str__(self)` — callable, line 92.
- `Cycle.sine(self, sequence: pd.PeriodIndex, name: str='sine_cycle')` — callable, line 99.
- `Cycle.asymmetric_sine(self, parameter: float, sequence: pd.PeriodIndex, precision: float=1e-08, bound: float=0.1, name: str='asymmetric_sine_cycle')` — callable, line 114.
- `Cyclicality` — class, line 137.
- `Cyclicality.space_waveform` — field, line 138.
- `Cyclicality.asset_waveform` — field, line 139.
- `Cyclicality.__init__(self, sequence: pd.PeriodIndex, space_cycle: Cycle, asset_cycle: Cycle, space_cycle_asymmetric_parameter: float=None, asset_cycle_asymmetric_parameter: float=None)` — callable, line 141.
- `Cyclicality.from_params(cls, space_cycle_period: float, space_cycle_phase: float, space_cycle_amplitude: float, asset_cycle_period: float, asset_cycle_phase: float, asset_cycle_amplitude: float, space_cycle_asymmetric_parameter: float, asset_cycle_asymmetric_parameter: float, sequence: pd.PeriodIndex)` — callable, line 184.
- `Cyclicality.from_estimates(cls, space_cycle_phase_prop: float, space_cycle_period: float, space_cycle_height: float, asset_cycle_period_diff: float, asset_cycle_phase_diff_prop: float, asset_cycle_amplitude: float, space_cycle_asymmetric_parameter: float, asset_cycle_asymmetric_parameter: float, sequence: pd.PeriodIndex)` — callable, line 245.
- `Cyclicality._from_args(cls, args: tuple)` — callable, line 305.
- `Cyclicality.from_likelihoods(cls, space_cycle_phase_prop_dist: rk.distribution.Form, space_cycle_period_dist: rk.distribution.Form, space_cycle_height_dist: rk.distribution.Form, asset_cycle_phase_diff_prop_dist: rk.distribution.Form, asset_cycle_period_diff_dist: rk.distribution.Form, asset_cycle_amplitude_dist: rk.distribution.Form, space_cycle_asymmetric_parameter_dist: rk.distribution.Form, asset_cycle_asymmetric_parameter_dist: rk.distribution.Form, sequence: pd.PeriodIndex, iterations: int=1)` — callable, line 330.

## `src/rangekeeper/dynamics/market.py`

Review group: `scenarios`.

- `Market` — class, line 15.
- `Market.__init__(self, sequence: pd.PeriodIndex, trend: rk.dynamics.trend.Trend, volatility: rk.dynamics.volatility.Volatility, cyclicality: rk.dynamics.cyclicality.Cyclicality, noise: rk.dynamics.noise.Noise, black_swan: rk.dynamics.black_swan.BlackSwan)` — callable, line 16.
- `Market._from_args(cls, args: tuple)` — callable, line 122.
- `Market.from_likelihoods(cls, sequence: pd.PeriodIndex, trends: [rk.dynamics.trend.Trend], volatilities: [rk.dynamics.volatility.Volatility], cyclicalities: [rk.dynamics.cyclicality.Cyclicality], noise: rk.dynamics.noise.Noise, black_swan: rk.dynamics.black_swan.BlackSwan)` — callable, line 135.

## `src/rangekeeper/dynamics/noise.py`

Review group: `scenarios`.

- `Noise` — class, line 8.
- `Noise.__init__(self, sequence: pd.PeriodIndex, noise_dist: rk.distribution.Form)` — callable, line 9.
- `Noise.generate(self)` — callable, line 29.

## `src/rangekeeper/dynamics/trend.py`

Review group: `scenarios`.

- `Trend` — class, line 12.
- `Trend.growth_rate` — field, line 13.
- `Trend.cap_rate` — field, line 14.
- `Trend.initial_value` — field, line 15.
- `Trend.initial_price_factor` — field, line 16.
- `Trend.__init__(self, sequence: pd.PeriodIndex, growth_rate: float, cap_rate: float, initial_value: Optional[float]=None, initial_price_factor: float=1.0)` — callable, line 18.
- `Trend._from_args(cls, args: tuple)` — callable, line 40.
- `Trend.from_likelihoods(cls, sequence: pd.PeriodIndex, cap_rate: float, growth_rate_dist: rk.distribution, initial_value_dist: rk.distribution, initial_price_factor: float=1.0, iterations: int=1)` — callable, line 51.

## `src/rangekeeper/dynamics/volatility.py`

Review group: `scenarios`.

- `Volatility` — class, line 14.
- `Volatility.__init__(self, trend: rk.dynamics.trend.Trend, volatility_per_period: float, autoregression_param: float, mean_reversion_param: float, sequence: pd.PeriodIndex)` — callable, line 15.
- `Volatility._from_args(cls, args: tuple)` — callable, line 75.
- `Volatility.from_trends(cls, trends: [rk.dynamics.trend.Trend], volatility_per_period: float, autoregression_param: float, mean_reversion_param: float, sequence: pd.PeriodIndex)` — callable, line 87.
- `Volatility.calculate_autoregression(parameter: float, volatility: numba.typed.List)` — callable, line 109.
- `Volatility.calculate_volatility_accumulation(trend_rate: float, trend_values: numba.typed.List, mr_parameter: float, ar_returns: numba.typed.List)` — callable, line 122.

## `src/rangekeeper/policies/replay.py`

Review group: `policy`.

- `Policy` — class, line 7.
- `Policy.__init__(self, condition: Callable[[rk.flux.Flow], List[bool]], action: Callable[[object, List[bool]], object])` — callable, line 8.
- `Policy.execute(self, args: tuple)` — callable, line 15.

## `src/rangekeeper/segmentation.py`

Review group: `segmentation`.

- `Characteristic` — class, line 13.
- `Characteristic.use` — class-attribute, line 16.
- `Characteristic.tenure` — class-attribute, line 17.
- `Characteristic.span` — class-attribute, line 18.
- `Characteristic.type` — class-attribute, line 19.
- `Type` — class, line 22.
- `Type.name` — field, line 23.
- `Type.code` — field, line 24.
- `Type.supertype` — field, line 25.
- `Type.subtypes` — field, line 26.
- `Type.__init__(self, name: str, code: str=None, supertype: Type=None)` — callable, line 28.
- `Type.__str__(self)` — callable, line 41.
- `Type.add_subtypes(self, subtypes: [Type])` — callable, line 45.
- `Type.ancestors(self)` — callable, line 52.
- `Type.primogenitor(self)` — callable, line 60.
- `Type.display(self)` — callable, line 63.
- `Interval` — class, line 67.
- `Interval.__init__(self, right: float, left: float=0.0)` — callable, line 68.
- `Interval.__str__(self)` — callable, line 76.
- `Interval.split(self, proportion: float)` — callable, line 79.
- `Interval.subdivide(self, values: Union[int, List[float]])` — callable, line 94.
- `Interval.interval_value(self)` — callable, line 119.
- `Segment` — class, line 123.
- `Segment.name` — field, line 124.
- `Segment.bounds` — field, line 125.
- `Segment.parent` — field, line 126.
- `Segment.children` — field, line 127.
- `Segment.characteristics` — field, line 128.
- `Segment.__init__(self, bounds: Interval, characteristics: Dict[Characteristic, str]=None, parent: Segment=None, children: List[Segment]=None, name: str=None)` — callable, line 130.
- `Segment.to_frame(self)` — callable, line 150.
- `Segment.display(self)` — callable, line 162.
- `Segment.display_children(self, pivot: Characteristic=None, decimals: int=2)` — callable, line 169.
- `Segment.split(self, proportion: float)` — callable, line 199.
- `Segment.subdivide(self, divisions: List[Tuple[str, Dict[Characteristic, str], float]])` — callable, line 209.

## `src/rangekeeper/api.py`

Review group: `integration`.

- `Speckle` — class, line 11.
- `Speckle.__init__(self, token: str, host: str=None)` — callable, line 12.
- `Speckle.parse(base: objects.Base, parsed: dict[str, objects.Base]=None)` — callable, line 51.
- `Speckle.to_rk(bases: list[objects.Base], name: str, type: str)` — callable, line 113.

## `src/rangekeeper/format.py`

Review group: `presentation`.

- `to_decimal(value, places: int=2, mode: str='ROUND_HALF_EVEN')` — callable, line 11.
- `to_decimals(series: pd.Series, places: int=2, mode: str='ROUND_HALF_EVEN')` — callable, line 34.
- `to_thousands(value)` — callable, line 56.
- `to_thousandss(series: pd.Series)` — callable, line 67.
- `to_currency(value, currency: str='USD', locale: str='en_US', decimals: bool=True, compact: bool=False)` — callable, line 78.
- `to_currencys(series: pd.Series, currency: str='USD', locale: str='en_US', decimals: bool=True, compact: bool=False)` — callable, line 113.
- `to_percentage(value, decimal_places: int=2)` — callable, line 142.
- `to_percentages(series: pd.Series, decimal_places: int=2)` — callable, line 163.
- `to_locale(value, locale: Optional[Union[str, babel.core.Locale]]='en_US', decimal_places: int=2)` — callable, line 182.
- `to_locales(series: pd.Series, locale: str='en_US', decimal_places: int=2)` — callable, line 198.
- `_to_color(value: float, cmap, range: Tuple[float, float]=(0, 1), missing: str='#ffffff')` — callable, line 213.
- `to_color(value: float, cmap: str='RdYlGn', range: Tuple[float, float]=(0, 1), missing: str='#ffffff')` — callable, line 227.
- `to_scaled_colors(series: pd.Series, range: Tuple[float, float]=None, cmap: str='RdYlGn', diverging: bool=False, missing: str='#ffffff')` — callable, line 245.
- `distinct_colors(count: int, cmap: str='RdYlGn')` — callable, line 261.
- `to_distinct_colors(series: pd.Series, cmap: str='RdYlGn', name: str='color')` — callable, line 270.
- `na_to_empty(df: pd.DataFrame)` — callable, line 282.
- `_to_nonnullable(series: pd.Series)` — callable, line 295.
- `to_nonnullables(data, verbose: bool=True)` — callable, line 306.
- `to_timestampstrings(series: pd.Series, format: str='short', locale: str='en_US')` — callable, line 333.
- `to_datestrings(series: pd.Series, format: str='medium', locale: str='en_US')` — callable, line 352.
- `column_names(df: pd.DataFrame, option: Optional[str], add_prefix: Optional[str]=None, add_suffix: Optional[str]=None)` — callable, line 371.

## `src/rangekeeper/__init__.py`

Review group: `root-cleanup`.

- `__getattr__(name: str)` — callable, line 73.
- `__dir__()` — callable, line 81.
- `update_class(main_class=None, exclude=('__module__', '__name__', '__dict__', '__weakref__'))` — callable, line 85.
- `rgba_from_cmap(cmap_name, start_val, stop_val, val)` — callable, line 106.

## `src/rangekeeper/space.py`

Review group: `root-cleanup`.

No classes or functions; inspect imports, re-exports or commented residue.
