# Rangekeeper schema: purpose, object model, and current draft

**Movement naming, 2026-10-06:** `flow.yaml` defines `Movement` and ordered
`Flow.movements`. They replace the unreleased `FlowSample`/`samples` names without
aliases. Entry fields and behavior remain unchanged. See the
[contract](../docs/FULL_MIGRATION_TURN1.md#movement-naming) and
[verification](../docs/research/full-migration/movement-naming/README.md).

**Flow semantics, 2026-10-06:** Flow contains units and ordered movements, without
a semantic kind/basis. The overall model logic defines interpretation and selects
calculations. Unit, coordinate, missing-value and reference checks remain. This
corrects the unreleased 0.4.0 draft; it does not change `Value.kind="flow"`.
See the [contract](../docs/FULL_MIGRATION_TURN1.md#flow-semantics-and-explicit-operations)
and [verification](../docs/research/full-migration/flow-semantics/README.md).

**Date-only Flow contract, 2026-10-04:** `duration.yaml` defines Period/Span
boundaries as dates. `flow.yaml` requires a date or Period per Movement through
semantic validation. An optional date on a period movement is an independent
payment/observation fact; it need not lie within the Period. There is no TimePoint
or intraday Flow coordinate. See the [contract](../docs/FULL_MIGRATION_TURN1.md)
and [verification](../docs/research/full-migration/date-only/README.md).

**Current extension (2026-10-04):** Model 0.4.0 imports `duration.yaml`,
`flow.yaml` and `content.yaml` through Characteristics. Values now support
measurement, flow and property content. See [Turn 1 contracts](../docs/FULL_MIGRATION_TURN1.md)
and the [upgrade guide](../docs/LEGACY_UPGRADE_GUIDE.md). The original scalar
contract discussion below remains useful; numerical kernels do not add Flow solve roles.


This directory defines the kinds of information a Rangekeeper model can express:
Entities, Classifications, Measures, characteristics, relationships, and evidence.
The LinkML schema supplies the shared object contract. A document-interpretation
workflow supplies the particular definitions and objects for a project.

**Current status:** stable UUIDs are the designated LinkML identifiers for
identified records. Object references use typed class ranges and serialize the
UUID directly. Taxonomies, Classifications, Measures, Labels, and Values are
serialized as lists with explicit codes/local keys. The custom taxonomy/code
reference parser has been removed. Both examples pass generated record validation
and generated Python round trips; the runtime conformance fixture checks their
graph meaning. Canonical Model/Specification/Run codecs and immutable revision stores
are now implemented: see [Run and storage](../docs/RUN_AND_STORAGE.md).
[Affine scalar execution](../docs/SCALAR_EXECUTION.md) is also implemented.
Legacy consumer format migration and richer calculation capabilities remain pending.

## Schema, project definitions, and project objects

| Level | Example | Responsibility |
| --- | --- | --- |
| Rangekeeper schema | A Classification may have a parent; a Measurement references a Measure. | Define the permitted classes, fields, relationships, and constraints in LinkML. |
| Project-specific definitions | A uses Taxonomy contains residential; net lettable area is measured in square metres. | An interpretation workflow proposes or reuses these definitions based on source material and modelling decisions. |
| Project objects and content | Apartment A is residential and has 85.5 square metres of net lettable area. | The workflow creates identified objects, connects them to definitions, and records their content and evidence. |

Both project-specific definitions and project objects are **instances of the
Rangekeeper schema**. A particular Measure is a definition within a project and
an instance of the LinkML class `Measure`:

```text
Schema class: Measure
    ↓ instantiated as
Project definition: Net lettable area, with canonical units m²
    ↓ referenced by
Project measurement: Apartment A has 85.5 m²
```

Discovering “serviced apartment” creates another Classification record. It does
not require a new LinkML class. Schema evolution is needed when the required
kind of information cannot be represented by the existing contract—for example,
adding a supported Flow Value kind—not whenever a project introduces a new code.

In this document, **schema** means the shared LinkML class/field contract.
**Project definitions** means records such as Taxonomies, Classifications, and
Measures. Their names and codes are not prescribed by the shared schema.

## From documents to a graph/model

```text
Input documents and existing project context
    ↓ interpretation by an LLM, a person, or another implementation
Proposed project definitions, objects, relationships, content, and evidence
    ↓ structural validation and domain validation
Graph / Model instance
```

Definitions and objects can emerge together and be revised during interpretation.
The workflow can reuse existing definitions or propose new ones. It must distinguish
what the sources say from assumptions and derived content, preserve unresolved
values, and retain the supporting evidence and decisions.

Schema validation checks whether records conform to the contract. Domain validation
checks such matters as reference existence, units, hierarchy, membership, and
provenance agreement. Neither proves that an LLM interpreted a document correctly.
The interpretation workflow must make that reasoning and evidence reviewable.

Constructing or loading a graph is distinct from running a calculation. The initial
Expression, Constraint, Formulation, Model, Specification, and Run schemas are drafted.
Run records cover finalized attempts and accepted output references; execution remains
a separate implementation task.
Fixed, unknown, target, and optimized roles belong to a Specification; a recorded amount
does not silently become a permanent constraint.

## Core object contract

The agreed outer Entity structure is:

```text
Entity
  id
  code
  name
  classification
  characteristics
    labels
    values
```

An Entity has stable identity, an optional human-facing code and name, an optional
Classification, and optional Characteristics. Labels and Values belong within
Characteristics. Each characteristic has its own identity and a local name, so
provenance can identify it independently of the owner's display name or a rename.

| Concept | Meaning |
| --- | --- |
| Taxonomy | An identified collection of Classifications with a single-root hierarchy. |
| Classification | A named definition within a Taxonomy, with an optional parent in that Taxonomy. |
| Measure | The meaning and canonical units of a numerical measurement; it contains no amount. |
| Label | An identified, locally named set of Classifications describing an aspect of its owner. |
| Value | An identified, locally named declaration with typed content, owned by Characteristics or a mathematical Formulation. Measurement is the first supported kind. |
| Quantity | Embedded numerical content: a finite magnitude and explicit units, with no identity or Measure reference. |
| Measurement | An identified property with a Measure and an optional Quantity. Absence is unresolved; zero magnitude is resolved content. |
| Relationship | An identified, classified, directed connection between Entities, with optional Characteristics. |
| Assembly | An Entity identifying a collection of Entities and Relationships. Membership does not itself assert spatial containment. |
| Formulation | A mathematical container owning local Values, Expressions, Constraints, and child Formulations; it can reference shared domain Values. |

Values unify the intended measurements/features collection. Date, Span, Flow,
Stream, and Account are candidate Value kinds; their schemas remain to be defined.
Measure has no quantity-kind category or aggregation rule. Expressions will define
aggregation, selection, and weighting, including how overlapping membership is
handled.

Identity persists across immutable Model revisions. A resolved copy can retain a
characteristic's identity without mutating the input snapshot. Names and codes are
not identity. Each identified record designates `id` as its LinkML identifier,
with UUID as its range. References retain that UUID across code/name changes.

The agreed code scopes are:

| Record | Code uniqueness scope |
| --- | --- |
| Entity, including Assembly | All Entities in one Model, when a code is supplied. |
| Taxonomy | The Model's taxonomy catalogue. |
| Classification | Its Taxonomy. |
| Measure | The Model's measure catalogue. |

Characteristic local names are unique within their owner's labels or values
collection. Assemblies may overlap; they do not introduce new naming scopes.
The runtime Graph currently enforces the Entity scope for its own collection.
Formulation-local Value keys, Binding names, Constraint codes, and child Formulation codes
are each unique within their respective owning collections. Formulations do not limit
UUID reference visibility or establish a calculation order.

## Relationships the schema must express

These are relationships between record types, independent of how their references
are written in YAML, JSON, a database, or a Python API:

| Field or association | Target |
| --- | --- |
| Entity classification | Classification |
| Label classifications | Classifications |
| Classification parent | Classification within the same Taxonomy |
| Measurement measure | Measure |
| Relationship source and target | Entities, including Assemblies |
| Assembly members | Entities and Relationships |
| Fact target | An eligible Entity, Assembly, Relationship, Label, or Value |
| Fact support | Claims |
| Claim support | Source Locations or upstream Claims, as appropriate to its kind |

Object references use LinkML class ranges and `inlined: false`. Their values
are the target records' stable UUID identifiers, not names assembled from a
Taxonomy and code. This applies equally to an Entity's Classification, a Label's
Classifications, a parent Classification, and a Measurement's Measure. See LinkML's
[keys and identifiers](https://linkml.io/linkml/schemas/slots.html#keys-identifiers)
and [object references and inlining](https://linkml.io/linkml/schemas/inlining.html).

No project Taxonomy names or Measure codes are built into the shared schema.
Codes and local characteristic keys are ordinary explicit fields. They retain
their uniqueness scopes but do not determine reference serialization. Dots in
codes are literal characters; no namespace splitting or hierarchy traversal is
performed. Renaming a code or local key does not require changing UUID references.

Graph invariants remain necessary: targets must exist and have the right type;
taxonomies have one root and no parent cycles; Assemblies cannot contain themselves
or form membership cycles. Each member Relationship connects direct members or
the Assembly itself. Loading typed records alone does not establish these rules.

## Evidence and interpretation

| Record | Purpose |
| --- | --- |
| Source | Identifies an edition of an evidence artifact, including its checksum. |
| Location | An address within a Source, such as sheet/cell or line. |
| Method | Names the process used to assert, derive, or reconcile content. |
| Claim | Candidate content obtained from a Source, asserted through a Method, or derived from other Claims. |
| Fact | Connects a graph object or characteristic to Claims supporting its recorded content. |
| Reconciliation | Selects a supporting Claim when evidence conflicts. |
| Provenance | Holds shared Source, Claim, and Fact records. |

Facts identify the characteristic itself, not merely its local name. For example,
two apartments may both have `net_lettable_area`; their distinct characteristic
identities let evidence support exactly one of them. Renaming the local property
does not change that identity or its provenance association.

A sourced Claim requires a Location. A derived Claim requires upstream Claims and
a Method; an asserted Claim requires a Method. Claim dependencies must be acyclic.
An accepted Fact's agreed or selected Claim must match the target's content;
conflicts require reconciliation. Missing provenance does not imply unresolved
content, and a supplied amount does not prove that it came from an observation.

`Claim.content` is currently a generic content boundary. Supported payloads still
need content-specific checks. The conformance example handles measurement content
and Label classifications; it does not define every whole-object or future Value
payload. Run linkage remains pending.

## Schema files and implementation boundary

| File | Responsibility |
| --- | --- |
| [common.yaml](common.yaml) | Shared primitive types and document revision Metadata. |
| [classification.yaml](classification.yaml) | Identified Classification and Taxonomy records, with typed UUID references. |
| [definitions.yaml](definitions.yaml) | Collection of project Taxonomies, Measures, and versioned Functions. |
| [measure.yaml](measure.yaml) | Quantity, Measure, Measurement, and shared measure/quantity fields. |
| [characteristics.yaml](characteristics.yaml) | Characteristics, Labels, and typed Values. |
| [entity.yaml](entity.yaml) | Entity's identity and descriptive structure. |
| [relationship.yaml](relationship.yaml) | Classified directed Entity relationships. |
| [assembly.yaml](assembly.yaml) | Assembly specialization and membership. |
| [provenance.yaml](provenance.yaml) | Sources, Locations, Methods, Claims, Facts, and reconciliation. |
| [function.yaml](function.yaml) | Versioned function signatures, argument/result domains, and collection contracts. |
| [query.yaml](query.yaml) | Graph traversal, fixed metadata filters, projection, and duplicate handling. |
| [expression.yaml](expression.yaml) | Typed literals, symbolic Value references, operators, calls, selections, and queries. |
| [constraint.yaml](constraint.yaml) | Identified assertions referencing Boolean Expressions by UUID. |
| [formulation.yaml](formulation.yaml) | Explicit mathematical containers, owned local Values, shared Value bindings, and nested Formulations. |
| [model.yaml](model.yaml) | Immutable Model envelope, revision Metadata, and a System containing domain objects and formulations. |
| [specification.yaml](specification.yaml) | Pinned input Model, assignments, unknowns, estimates, additional Formulations, ordered objectives, and numerical settings. |

The schema is the intended authority; Python is implementation and migration
context. Schema URIs identify drafts and do not imply published endpoints.
Classification, Taxonomy, Measure, Label, and Value now designate their UUIDs
as native identifiers. Their collections use `inlined_as_list: true`; codes and
local keys are explicitly supplied and no longer marked `key: true`. Location
address parts remain simple key/value data, rather than independently identified
graph records.

The Python runtime still separates measurements and features. Measurement permits
`quantity=None`; reductions and workflow lookup treat unresolved amounts as
missing. Existing graph JSON retains its own UUID reference encoding. The shared
schema fixture is a bounded conformance adapter, not a production importer, an
LLM interpretation pipeline, or a Model executor.

The Quantity draft replaces serialized Measurement/Value `amount` with an optional
`quantity: {magnitude, units}`. Numerical Expressions now use `kind: quantity` and
the same embedded content; the former `kind: number` and literal `measure` field
are no longer accepted. `number` remains a dimensionless function argument/result
type. The fixture adapter constructs Pint quantities from the supplied units.

## Naming and draft migration

Class and enum names are shared across schema imports. Categorical enums retain
the concept they describe: `ValueKind`, `ExpressionKind`, `DomainKind`,
`ParameterKind`, `SelectionKind`, `TraversalKind`, `ProjectionKind`, `ClaimKind`,
and `CollectionKind`. Their fields use `kind` where the containing record supplies
context; `collection_kind` distinguishes collection shape from the Domain's kind.

`Domain` describes permitted content, including units, measurement meaning, and
nested collection elements where applicable. It does not contain a recorded value
or decide whether a Value is fixed or unknown in a Specification. There is no general
`Type` class or enum in this vocabulary. LinkML's own `types` and `typeof` schema
keywords retain their native meanings.

| Field | Range | Meaning |
| --- | --- | --- |
| `Value.kind` | `ValueKind` | Serialized Value variant; currently `measurement`. |
| `Expression.kind` | `ExpressionKind` | Expression form, such as `call` or `reference`. |
| `Parameter.kind` | `ParameterKind` | Calling convention: `positional_or_named` or `named_only`. |
| `Parameter.domain` | `Domain` | Permitted argument content, such as a quantity in AUD. |
| `Function.result` | `Domain` | Permitted result content. |
| `Domain.kind` | `DomainKind` | Content category, such as `quantity` or `collection`. |
| `Domain.item_domain` | `Domain` | Permitted content of each collection element. |

`ValueKind` and `DomainKind` are separate vocabularies. Domains can describe
expression results and arguments whose full Value serialization is not yet
defined. A `call` Expression can produce content in a `quantity` Domain without
being a serialized measurement Value.

Other concepts use concise names such as `Operator`, `Depth`, `Direction`,
`Cardinality`, `Content`, `Argument`, `Criterion`, and `Entry`. `Argument` still
requires a name within `Call.named_arguments`; positional arguments are ordered
Expressions. `EmptyHandling`, `MissingHandling`, `DuplicateHandling`, and
`ReconciliationStatus` retain qualifiers because their situations and choices
differ. Collection fields are plural; each `item_domain` is one Domain.

The current draft applies these class and enum renames:

| Previous | Current |
| --- | --- |
| Enum `Type` | `ValueKind` |
| `ExpressionType` | `Domain` |
| `ExpressionTypeKind` | `DomainKind` |
| `ParameterBinding` | `ParameterKind` |
| `ExpressionOperator` | `Operator` |
| `TraversalDepth` | `Depth` |
| `TraversalDirection` | `Direction` |
| `ProjectionCardinality` | `Cardinality` |
| `EvidenceContent` | `Content` |
| `NamedArgument` | `Argument` |
| `LabelFilter`, earlier `QueryLabelFilter` | `Criterion` |
| `AddressPart` | `Entry` |
| `FunctionCall` | `Call` |
| `FunctionParameter` | `Parameter` |
| `QueryFilter` | `Filter` |
| `QueryProjection` | `Projection` |
| `EmptyCollectionHandling`, earlier `EmptyCollectionBehaviour` | `EmptyHandling` |
| `MissingProjectionHandling`, earlier `MissingProjectionBehaviour` | `MissingHandling` |

The instance field and kind changes are:

| Previous | Current |
| --- | --- |
| `Value.type` | `Value.kind` |
| `Parameter.type` | `Parameter.domain` |
| `Parameter.binding` | `Parameter.kind` |
| `ExpressionType.item_type`, earlier `ExpressionType.items` | `Domain.item_domain` |
| `Traversal.relationship` | `Traversal.classification` |
| `Relationship.source_id`, `target_id` | `Relationship.source`, `target` |
| `Assembly.entity_ids`, `relationship_ids` | `Assembly.entities`, `relationships` |
| `Claim.value` | `Claim.content` |
| `Location.reference` | `Location.address` |
| Expression `kind: operation` | Expression `kind: binary` |

These are name changes, preserving identities, reference targets, cardinality,
operand order, and meaning. The old instance names are not aliases. Relationship
endpoints and Assembly members still serialize as UUID references. Claim content
and Location addresses remain embedded content. The bounded fixture maps these
schema fields to the existing Python runtime API; its separate JSON format is
unchanged.

## Current instance-serialization example

The following is **project instance data, not a LinkML schema definition**. Its
Taxonomies, Classifications, Measures, and apartment are illustrative choices an
interpretation workflow could produce. They are not a universal property taxonomy
or a required catalogue of measures.

A Building Assembly and one Apartment demonstrate the current structural modules:
definitions, characteristics, a Relationship, membership, and provenance. The area
is explicitly an asserted assumption; no source-document interpretation is claimed.

This example uses the UUID-reference encoding checked by the current schema and
generated classes. The outer keys group the records and do not yet constitute a
defined Model/file envelope. All referenced definitions are included; names and
codes beside their UUIDs make the records inspectable.

```yaml
definitions:
  taxonomies:
  - id: c09123c4-bec7-49d6-aeac-ed0c95ad5f39
    name: Spaces
    classifications:
    - id: 6c0b1999-b082-48a6-97e2-bf8c8507ef5a
      name: Space
      code: space
    - id: 162ac1c3-d899-4eec-ad80-0eae9a17ded5
      name: Building
      parent: 6c0b1999-b082-48a6-97e2-bf8c8507ef5a
      code: building
    - id: 49d5b8f1-35b4-4ba0-ad5b-7ba98ae310cf
      name: Apartment
      parent: 6c0b1999-b082-48a6-97e2-bf8c8507ef5a
      code: apartment
    code: spaces
  - id: cf4ae394-3e25-4809-adfb-2b78b725cbe4
    name: Uses
    classifications:
    - id: 53461fba-9b63-462c-ae4b-9a3128cb4da8
      name: Residential
      code: residential
    code: uses
  - id: e1343c47-195e-4a78-a4d9-4d6ae5396267
    name: Connections
    classifications:
    - id: ed787dad-2611-4f5a-87b2-9bc04b0f9faa
      name: Contains
      code: contains
    code: connections
  measures:
  - id: b2f45f00-3e75-4ce7-bbc0-49f4531fab45
    name: Net lettable area
    units: m^2
    code: area.net_lettable
  - id: dd025d51-e24a-4baf-bbe9-ff4be3c92b56
    name: Ceiling height
    units: m
    code: height.ceiling
entities:
- id: 55e9ce96-4f6a-4e72-af5e-91eec87c9d51
  code: APT-101
  name: Apartment A
  classification: 49d5b8f1-35b4-4ba0-ad5b-7ba98ae310cf
  characteristics:
    labels:
    - id: 7a0b1867-a5c9-5fcb-8cb3-bacf6cfb1cf4
      classifications:
      - 53461fba-9b63-462c-ae4b-9a3128cb4da8
      key: use
    values:
    - id: 8b1e8b41-54d5-4924-8904-8208e68c81ab
      kind: measurement
      measure: b2f45f00-3e75-4ce7-bbc0-49f4531fab45
      quantity:
        magnitude: 85.5
        units: m^2
      key: net_lettable_area
    - id: 01d14db9-9280-4688-b521-ed5c4a42988c
      kind: measurement
      measure: dd025d51-e24a-4baf-bbe9-ff4be3c92b56
      key: ceiling_height
relationships:
- id: 2ca16dca-8dd0-5414-9b90-4a84e43a179a
  source: 1536e7d7-80f9-5597-8bcb-9cda9db5eb63
  target: 55e9ce96-4f6a-4e72-af5e-91eec87c9d51
  classification: ed787dad-2611-4f5a-87b2-9bc04b0f9faa
assemblies:
- id: 1536e7d7-80f9-5597-8bcb-9cda9db5eb63
  code: BLDG-A
  name: Building A
  classification: 162ac1c3-d899-4eec-ad80-0eae9a17ded5
  entities:
  - 55e9ce96-4f6a-4e72-af5e-91eec87c9d51
  relationships:
  - 2ca16dca-8dd0-5414-9b90-4a84e43a179a
provenance:
  sources: []
  claims:
  - id: 42c83e7b-df05-5ac2-81de-6cdf1c8e95f6
    kind: asserted
    content:
      measure: b2f45f00-3e75-4ce7-bbc0-49f4531fab45
      quantity:
        magnitude: 85.5
        units: m^2
    method:
      code: manual.entry
      version: '1'
      description: Area entered as a modelling assumption.
  facts:
  - target: 8b1e8b41-54d5-4924-8904-8208e68c81ab
    claims:
    - 42c83e7b-df05-5ac2-81de-6cdf1c8e95f6
```

The area records 85.5 square metres; ceiling height is unresolved. The use Label
classifies an aspect of the Apartment. The contains Relationship expresses physical
containment, while the Assembly lists group the Apartment and the Relationship.
The Building is itself an Entity, so it can be a Relationship endpoint without a
second Building record. The Fact targets the area Value, not the Apartment as a whole.

The [larger structural example](examples/structural-graph.json) adds sourced and
derived Claims, Label provenance, and overlapping Assemblies. It includes an
unresolved Measurement and a resolved 85.5 square metres, derived from sourced
80.5 plus an asserted adjustment of 5. Its Source checksum matches
[structural-evidence.txt](examples/structural-evidence.txt).

### UUID identity and instance encoding

| Concern | Current encoding |
| --- | --- |
| Identity | An explicit UUID `id`, designated as LinkML `identifier: true`, on each identified record. |
| Definitions | Lists of Taxonomies and Measures; each Taxonomy holds a list of Classifications. |
| Characteristics | Lists of Labels and Values, each with an explicit UUID and owner-local `key`. |
| Codes and local keys | Descriptive fields with scoped uniqueness; not serialized reference identifiers. |
| Classification references | The target Classification's UUID, including Entity classification and Label classifications. |
| Classification parent | UUID of a Classification in the same Taxonomy. |
| Measure references | The target Measure's UUID. |
| Endpoints, membership, provenance targets | Typed references carrying the target UUID. |

`spaces.apartment`, a bare code, and `{taxonomy: spaces, code: apartment}` are no
longer accepted as serialized Classification references. Likewise, a Measure code
is not a serialized Measure reference. Even when a code happens to look like a
UUID, a reference resolves the target's `id`, not its code.

Codes remain case-sensitive and reject surrounding whitespace. Dots are permitted
as literal code characters now that qualification parsing is gone. Parent changes
remain separate from identity changes. Renaming Taxonomies, Classifications,
Measures, or characteristic keys preserves references and Fact targeting.

The choice of lists is the current serialization contract, not a requirement that
Python or database implementations use lists for lookup. Internal code-keyed indexes
remain useful. They do not introduce alternate reference spellings in model files.
Address dictionaries in Source Locations are unaffected.

`Claim.content` remains a generic payload boundary. In the bounded example profile,
measurement content uses `{measure: <Measure UUID>, quantity: {magnitude: ..., units: ...}}` and Label content
uses Classification UUIDs. Full typed content schemas remain future work; the
semantic fixture validates these supported payloads explicitly.

A Quantity requires a finite magnitude and explicit units. Omission or null of the
whole Quantity denotes an unresolved Measurement; zero magnitude is resolved.
Negative magnitudes are structurally allowed, with applicable constraints governing
their meaning. Quantity units must be compatible with the Measure's canonical units,
but may use another scale, such as cm^2 for a Measure in m^2. Conversion changes
magnitude and units together. Use `dimensionless` explicitly for unitless quantities.
Units are currently nonblank text; structural validation does not prove compatibility.
A shared unit convention, currency handling, numerical precision, and rounding
remain to be specified. These semantic matters are separate from reference syntax.

## Expressions

An Expression represents mathematical syntax. It does not store a calculated
result or decide whether a referenced Value is fixed or unknown. Each Expression
has a stable UUID and exactly one content variant. The
[Expression contract](EXPRESSION_CONTRACT.md) records composition, query, and
function semantics and the implementation boundary.

| Kind | Content | Meaning |
| --- | --- | --- |
| `quantity` | `quantity: {magnitude, units}` | A finite numerical literal with explicit units and no Measure reference. |
| `boolean` | `boolean` | A literal `true` or `false`. |
| `reference` | `target` Value UUID | A mathematical symbol in the applicable Model or composed Specification scope. |
| `unary` | `operator`, one `operand` | Numerical or Boolean negation. |
| `binary` | `operator`, ordered `operands` | A binary operation on two nested Expressions. |
| `call` | Function UUID and arguments | Apply a declared function, including aggregation over a collection. |
| `selection` | Base expression and member/index | Select content under the base content's public contract. |
| `query` | Scope, traversal, filter, projection | Return Entity or Value identities from this Model revision. |

Only fields belonging to the selected kind are allowed. Literal content cannot be
null; an unresolved Quantity belongs to a Value, which an Expression can reference.
Operations support arithmetic including power and negation, comparisons, and
Boolean logic. Calls use ordered positional and explicitly named arguments;
their arity and domains follow the referenced Function signature. Each operand has its own Expression
identity; separate operands can reference the same Value. Their order is preserved.

Date and string literal nodes are deferred until required by a concrete operation,
potentially in Policies. Date and string remain result domain kinds; a selection such as
`Span.end_date` can return a date without a date literal node.

For example, this predicate asks whether the capital value in the
[valuation example](examples/valuation-expressions.yaml) equals AUD 10 million:

```yaml
id: 23ba69a0-556a-4793-a0b6-5e329af0d66c
kind: binary
operator: equal
operands:
- id: c989e7fa-e363-48c0-907c-e4cc8b5a6935
  kind: reference
  target: a947d40b-d9b0-54cb-a2a4-f8f598405ac2
- id: 8a82e02f-9fdd-4ff7-a68e-387a6279ed32
  kind: quantity
  quantity:
    magnitude: 10000000
    units: AUD
```

This is a Boolean expression, not an assignment or an asserted condition. A
Constraint specifies that a predicate must hold. Whether a Value is fixed or
unknown belongs to the Specification; referencing it does not freeze its recorded amount.

The valuation example declares six measurement Values and expresses both
`NOI = homes * annual_rent_per_home - annual_operating_cost` and
`capital_value * capitalization_rate = NOI`. Two Constraints reference and assert
these predicates. Its outer collections group records for review, not a completed
Model schema. Annual capitalization rate explicitly
has units `1/year`, so capital value times that rate has annual-income units.

Expression nesting forms finite trees; shared Value references can nevertheless
participate in simultaneous equations. Dependencies are derived from operands and
references. There is no second editable list of calculation edges.

The [graph aggregation example](examples/query-aggregation.yaml) selects apartment
rent Values through contains Relationships and passes them to a sum Function.
It explicitly removes repeated Value identities and rejects missing characteristics.
Its rent amounts remain unresolved. A second query counts Assembly members;
membership is separate from the contains Relationships.

The [structured-expression examples](examples/function-expressions.yaml) cover
Flow functions, a Span endpoint, an Account member, indexing, and unary operators.
Their `input_domains` entries describe fixture-only domains, not serialized
domain Values: rich Value content and member schemas still need definition.

Operand domains, dimensional compatibility, reference existence, unique identities,
and finite numbers need semantic validation. The draft describes function calls,
selection, queries, and aggregation, but does not implement their execution.
There is no evaluator, query engine, solver, or general-purpose code execution.

Recorded results remain on Values in output Model revisions, supported by
provenance and Run diagnostics. No separate `resolution.yaml` is planned. Queries
over the output Model serve reporting; `requested_results` is not a Specification field.
The Specification vocabulary is `assignments`, `unknowns`, `estimates`, additional
`formulations`, ordered `objectives`, and `settings`. Conditions specific to
an investigation are Constraints within its Formulations.

## Constraints

A Constraint requires an existing Boolean Expression to hold. Its required fields
are `id` and `predicate`; `code`, `name`, and `description` are optional. Codes are
case-sensitive and unique within their Constraint collection when supplied.
The predicate is a native LinkML reference to an Expression's stable UUID, with
the same reference scope as the containing definition. It may identify a root or
nested Expression. Several Constraints may refer to the same Expression.

For example, this record in the [valuation example](examples/valuation-expressions.yaml)
asserts `NOI = homes * annual_rent_per_home - annual_operating_cost`:

```yaml
id: d526182d-2216-5862-88b9-b5bdd5e804a5
code: net_operating_income
name: Net operating income
description: Net operating income equals annual rent less annual operating cost.
predicate: 8c9b169a-c9ee-51f6-ab09-ee9fb24f0dda
```

The formula remains in its Expression record. Constraint has no equality/inequality
discriminator: the referenced Expression already specifies that operation. Any
supported expression with a Boolean result domain can be a predicate, including
a comparison, logical combination, or Boolean-returning Function call.

Structural validation checks the UUID reference's shape. Semantic validation must
resolve it to an Expression and establish a Boolean result domain. Numerical
content is never implicitly converted to a truth value. A literal `false` is a
valid predicate, although a Constraint requiring it is unsatisfiable when imposed.
Passing these checks does not establish satisfaction, feasibility, compatible
units, or solver support.

Assertions do not assign a calculation direction or fix referenced Values. The Model
imposes the Constraints in its System's formulations and their descendants. Specification
owns fixed/unknown choices and numerical settings, and Run records diagnostics;
those two root schemas remain to be defined. Loading a Constraint does not execute it.

## Formulations

[formulation.yaml](formulation.yaml) adds a mathematical container using the existing Value,
Expression, and Constraint records:

```text
Formulation
  id, code?, name?, description?
  bindings[]       Binding { name, value: Value UUID }
  values[]         owned local Values
  expressions[]    owned Expression trees
  constraints[]    owned Constraints referencing Boolean Expressions
  formulations[]   owned child Formulations
```

Only `id` is required on a Formulation. An empty Formulation or a parent containing only children
is valid. Collections have no execution order; operand and argument order inside
Expressions retains its existing meaning. Including a Formulation's mathematics imposes
its Constraints and its descendants' Constraints together. Loading records does
not execute them; alternatives and conditional activation remain future work.

A Binding gives a Value a local interface name. It does not copy that Value, fix its
content, assert equality with another symbol, or provide a new expression lookup
syntax. Expressions still reference Value UUIDs directly. Bindings need not list
every dependency, and different names may refer to the same Value. Binding names
and local Value keys occupy separate collections and can coincide.

Every identified record has one canonical owner in its document. Local Values
belong in `Formulation.values`; Entity and Relationship Values stay in their Characteristics.
Child Formulations are owned records rather than membership references, and containment
must be finite and acyclic. UUID references resolve across the applicable Model or composed Specification scope,
including between siblings and to nested Expressions. Mathematical dependencies
can therefore form simultaneous systems even though ownership is a tree.

The [valuation Formulation example](examples/valuation-formulations.yaml) arranges the existing
two equations into `income` and `capitalization` children. Five Values remain owned
by the Entity; one unresolved `NOI` Value is owned by the parent Formulation and referenced
by both children. Each child uses the Constraint code `equation`: codes are local,
while UUID identities remain unique across the complete fixture. The older expression
example and this example are separate scopes, not collections to merge together.
The fixture envelope is not a Model schema and specifies no fixed/unknown roles.

A Flow's recorded content remains a Value; a Formulation can describe the mathematics
relating that Flow to other Values. For a projected cash flow, the eventual interface
would relate an amount, timing/profile assumptions, and dated movements. For a basic
account, it would relate opening balance, movements, interest, and closing balance.
Those richer payloads and indexed equations remain later extensions; neither example
requires turning every RK implementation class into a schema class.

`Function` continues to describe a pure operation used in an Expression. A Formulation
can contain many related expressions and assertions without a designated return
value. The System collection is named `formulations` and contains Formulation instances.
Reusable templates, instantiation, and backend capability registration are deferred.
Formulation names the explicit mathematical container; it does not mean a reusable
template and does not itself guarantee solver support.

Draft `0.2.0` consistently uses `Formulation` and `formulations`, replacing the
earlier `Block` class and nested `blocks` field. The schema and fixture files are
now `formulation.yaml` and `examples/valuation-formulations.yaml`. Declaration UUIDs
and mathematical meaning are unchanged; there are no legacy class or field aliases.
Changing an existing Model document requires the new schema version and a new
snapshot UUID, as illustrated by the complete example's `metadata.previous` link.
Draft `0.3.0` also permits Specification-owned Formulations. Their root codes have a
separate collection scope from Model root codes; UUIDs cannot duplicate Model records.

## Models

[model.yaml](model.yaml) groups the existing records into one snapshot:

```text
Model
  metadata: Metadata
    id: UUID
    schema_version: Code
    name?: string
    description?: string
    previous?: Metadata UUID
  definitions?: Definitions
    taxonomies[]
    measures[]
    functions[]
  system?: System
    entities[]
    relationships[]
    assemblies[]
    formulations[]: Formulation
  provenance?: Provenance
    sources[]
    claims[]
    facts[]
```

Metadata, its UUID, and its schema version are required. The remaining containers
and collections may be absent when empty. System has no separate identity or
reference scope. An Assembly is stored only in `system.assemblies` and remains an
eligible Entity reference target. Root Formulation codes are scoped to `system.formulations`;
owned child Formulations continue to use `Formulation.formulations`.

The snapshot's identity is `metadata.id`. A content change requires a new snapshot
UUID; retained declarations keep their UUIDs across revisions. `schema_version`
identifies the Model contract and its imported bundle, separately from snapshot,
Function, and runtime versions. The current contract is `0.3.0`; an implementation
must reject an unsupported contract version instead of guessing its meaning.
Schema validation alone cannot enforce storage immutability.

Nesting identity has an explicit LinkML consequence: `Metadata.id` is the native
identifier and Model is an enclosing document without another identifier slot.
`previous` therefore uses `range: Metadata`, `inlined: false`, and serializes the
preceding Model revision's UUID. It does not duplicate the ID or require dotted-path
parsing. This follows LinkML's [identifier/reference semantics](https://linkml.io/linkml/schemas/slots.html#keys-identifiers).
History is external to the current snapshot; it is not automatically imported or
required to interpret current content. Self-predecessors and cycles in available
history are invalid. Metadata now lives in `common.yaml` and also identifies Specification
revisions. Its shape is unchanged; its meaning follows the enclosing document.
Revision resolvers must verify the expected document kind. `Specification.model` uses
this same native reference convention; Run references follow it as well.

Each identified record has one canonical occurrence within a Model. Domain and
mathematical references must resolve inside it, including Function calls into
`definitions.functions` and cross-Formulation references. Previous-revision links and
external evidence artifacts are explicit exceptions. Unresolved Values are valid;
recorded amounts do not assign fixed/unknown roles. All Constraints under
`system.formulations` form the Model's governing mathematics. Specification-specific
targets, objectives, and policies remain in the Specification.

The [complete Model example](examples/model.yaml) combines the structural graph and
its provenance with the two valuation equations. It also declares a Function in
Definitions and uses it in a floor-area aggregation expression. Recorded and
unresolved Measurements coexist; no calculation or query has been executed. Earlier
example envelopes remain isolated component fixtures, not alternative Model formats.

## Specifications

[specification.yaml](specification.yaml), draft `0.4.0`, defines immutable investigation
requirements, their additive composition, and explicit batches:

`Specification` replaces the former `Problem` name. It declares the question and
conditions supplied to a Model; it is instance data, not the LinkML schema itself.
Study describes the broader modelling, execution, and analysis process, rather
than another schema container. Draft `0.3.0` renames the root class and schema
namespace without changing field semantics. The four examples have new revision
UUIDs and retained their preceding `0.2.0` revision references. Draft `0.4.0` adds
composition; the current standalone examples have new UUIDs with their `0.3.0`
revisions as predecessors.

```text
Specification
  metadata: Metadata
  model?: Metadata UUID                input Model assertion; required after composition
  includes[]: Metadata UUID            Specification contributions to one investigation
  cases[]: Metadata UUID               separate Specifications in a batch
  assignments[]: Assignment            amounts to enforce
  unknowns[]: Value UUID               amounts that may vary
  estimates[]: Assignment              starting estimates for unknowns
  formulations[]: Formulation          additional mathematics for this investigation
  objectives[]: Objective              decreasing order of preference
    expression: Expression UUID
    sense: minimize | maximize
  settings?: Settings
    relative_tolerance?: decimal
    iteration_limit?: integer
    time_limit?: decimal               seconds

Assignment
  value: Value UUID
  quantity: Quantity
```

Only `metadata` is structurally required. A partial contribution may omit its Model
and solve roles. A concrete composition must resolve exactly one Model revision.
Every Value needed by
imposed Constraints or any objective must nevertheless have an explicit assignment
or unknown role. This includes intermediate quantities; unrelated Values need no
role. Unknowns may be underdetermined: role completeness is not a uniqueness test.
An effective composition with no objectives requests an equation/feasibility investigation. Forward and
inverse investigations differ in their roles, not in a mode flag or rewritten equations.

### Additive composition and batches

`includes` accumulates requirements for **one** investigation. `cases` lists
**separate** investigations. Both use native Metadata UUID references, resolved
specifically to Specification revisions. Neither is a classification hierarchy or
revision lineage: `metadata.previous` never imports requirements.

Composition has no override precedence:

- One contributor supplies each assignment target, unknown role, estimate target,
  and individual setting. Independently repeated requirements are errors, even if
  identical. Assignment and unknown roles cannot overlap. Estimates and their
  unknown roles may come from different contributors.
- One contributor supplies the whole nonempty ordered objectives list. Omission
  and empty collections contribute nothing; `objectives: []` cannot cancel an
  included objective. Empty-container omission by native serializers is harmless.
- Each exact included revision contributes once, including in a diamond. Direct
  reference lists must be unique; all include/case edges together must be acyclic.
  Includes/cases list order gives no override precedence, execution order, or objective priority.
- Repeated Model pins must agree. Model pins assert scope; they are not independent
  value assignments. An absent pin remains unspecified until composition.
- All Formulations and Constraints accumulate. Declarations have one canonical
  owner across contributors; the composed Specification's root Formulation codes
  are unique. References can cross contributors. Jointly infeasible mathematics
  can still be a valid composition; checking does not prove satisfiability.
- Metadata stays with each revision. An effective view retains contributor and
  requirement-source information for validation; it is not modified content saved
  under an existing UUID or an additional contributor to its own source graph.

A batch has nonempty `cases` and may contain only `metadata`, `model`, and `cases`
with content. It cannot provide or include solve requirements. A batch cannot be
included as a contribution. Each case explicitly supplies or includes its own
requirements; a batch Model pin only checks that every leaf uses that Model, and
cannot supply a missing case pin. Cases can themselves be batches. Different case
paths to the same leaf describe separate planned occurrences; include deduplication
is local to each occurrence. There is no implicit Cartesian product or winner.

The additional files are ordinary Specifications, not Scenario/Evaluation classes:

| Example | Purpose |
| --- | --- |
| [Shared valuation requirements](examples/specification-common.yaml) | Partial contribution with the Model, homes, costs, cap rate, and NOI unknown. |
| [Composed forward valuation](examples/specification-composed-forward.yaml) | Includes shared requirements; supplies rent and declares capital value unknown. |
| [Composed inverse valuation](examples/specification-composed-inverse.yaml) | Includes the same requirements; supplies capital value and declares rent unknown, with an estimate. |
| [Valuation batch](examples/specification-batch.yaml) | Lists both complete compositions as cases, without passing requirements to them. |

The checks reconstruct the independently authored standalone forward/inverse
requirements exactly (ignoring order in unordered collections). They reject
executing the incomplete shared contribution, conflicting or repeated requirements,
cycles, unavailable references, and malformed batches. They also exercise diamonds,
nested batches, cross-contributor mathematics, and native Python round trips.

### Numerical investigation requirements

`Assignment` has no identity of its own. The target Value supplies its Measure and
meaning, while the supplied Quantity has finite magnitude and compatible units.
Zero is valid. Each collection permits at most one assignment per target, and
assignment targets and unknowns cannot overlap. Each estimate must target an unknown.
An estimate may differ from the solution and imposes no equality. `Binding` remains
the Formulation's name-to-symbol alias; it does not supply an amount.

Stored quantities are never implicit assignments or estimates. Using recorded
content in either role requires an explicit Assignment. An existing capital value
of $11 million can coexist with a new Specification assigning $10 million; this changes
the investigation without mutating the input snapshot. It is not a contradiction
unless the Model's actual governing mathematics independently requires $11 million.

Specification Formulations own additional Values, Expressions, Constraints, and children.
They can reference the pinned Model and each other. All Model and Specification Constraints
are imposed together; additions cannot override or deactivate Model mathematics.
The Model must remain valid by itself. All identities in the composed scope are
unique; Model and Specification root Formulation codes have separate collection scopes.
Specification-only requirements do not automatically become permanent output Model
constraints. Their retention and traceability will be specified with Run publication.

Each objective references a scalar numerical Expression owned by a Model or Specification
Formulation, including a nested node. Boolean or collection objectives are invalid.
An exact target for an existing Value uses an assignment; an inequality or composite
target uses a Constraint within a Formulation. Policies, scenarios, structural
interventions, and rich Value/member assignments remain deferred.

`objectives` is a list in decreasing order of preference, with
`list_elements_ordered: true`. Implementations may use that order for automatic
selection, or present candidates for user choice. Candidate generation, Pareto
filtering, and final selection are implementation responsibilities. Order does not
require every selected solution to be a strict lexicographic optimum, and no
`handling` field mandates a workflow. A weighted combination remains one objective
whose Expression contains the explicit weights and compatible scaling.

The Run must record the selected solution and the basis for selection, including
whether selection was automatic or a user's choice, the method applied, and limits
on any optimality or completeness claims. Run traces now provide a minimal record
for this evidence; selection algorithms remain future work. Schema validation checks
the criteria and evidence references, not which candidate wins.

Draft `0.2.0` replaces the singular `objective` record with the ordered `objectives`
list; the old field is rejected. Updated examples have new revision UUIDs and
`metadata.previous` references. Reordering preferences also changes a Specification revision.

[Settings](settings.yaml) is shared by Specification requests and Runtime effective
settings. Its fields are unchanged by extraction into the shared schema. Settings
have no schema defaults. Present limits are positive and finite;
`relative_tolerance` lies strictly between zero and one. It is a dimensionless
convergence request, not an absolute tolerance across mixed units. A backend must
document its convergence criterion, scaling, and setting mapping, report unsupported
requests, and record effective settings and diagnostics in the Run. No universal
residual normalization or solver capability is implied by these fields.

Four inspectable examples reference the [same Model](examples/model.yaml):

| Example | Assignments | Unknowns | Additional mathematics |
| --- | --- | --- | --- |
| [Forward valuation](examples/specification-forward.yaml) | 20 homes; rent 30,000 AUD/dwelling/year; costs 50,000 AUD/year; cap rate 0.05/year. | NOI, capital value. | None. |
| [Inverse valuation](examples/specification-inverse.yaml) | 20 homes; costs 50,000 AUD/year; cap rate 0.05/year; capital value 10 million AUD. | Rent, NOI. | None; rent has an estimate of 30,000 AUD/dwelling/year. |
| [Bounded optimization](examples/specification-optimization.yaml) | 20 homes; costs 50,000 AUD/year; cap rate 0.05/year. | Rent, NOI, capital value. | Rent at most 32,000 AUD/dwelling/year; maximize capital value. |
| [Ordered objectives](examples/specification-objectives.yaml) | Same as bounded optimization. | Rent, NOI, capital value. | Same rent ceiling; prefer higher capital value, then lower rent per dwelling. |

The first two equations imply respectively NOI 550,000 AUD/year and capital value
11 million AUD, then rent 27,500 AUD/dwelling/year and NOI 500,000 AUD/year. These
are expected arithmetic, not solver output. The checks additionally use a hand-authored,
separately identified snapshot with recorded amounts to verify that the inverse
Specification does not inherit previous solve roles. These Specification checks do not
execute a solver. The separate Run fixtures below are explicitly synthetic expected
records, not evidence that execution occurred.

## Runs

[run.yaml](run.yaml), draft `0.1.0`, records a finalized execution attempt:

```text
Run
  metadata: Metadata
  specification: Metadata UUID        exact attempted Specification
  spawns[]: Metadata UUID             direct subordinate Run records
  outputs[]: Metadata UUID            accepted output Model revisions
  report: Report
    status: Status
      completion: CompletionStatus
      solution: SolutionStatus
    runtime?: Runtime
      started_at?: datetime
      finished_at?: datetime
      implementations[]: Implementation
        kind: evaluator | compiler | solver
        name: string
        version: string
      settings?: Settings
    diagnostics[]: Diagnostic
      severity: info | warning | error
      code: Code
      message: string
      document?: Metadata UUID
      target?: UUID
      residual?: Quantity
      tolerance?: Quantity
    trace[]: Step                       ordered
      kind: validation | formulation | solve | publication | selection
      at?: datetime
      message: string
      document?: Metadata UUID
      target?: UUID
```

Metadata, Specification reference, Report, and both Status fields are required.
Document references use Metadata UUIDs with resolved kind checks. Inputs come from
the exact Specification and its includes; no copied effective Specification or
second authoritative input Model field is introduced. Each referenced revision must
remain available. A new execution has its own Run identity; metadata.previous records
revision lineage, never execution containment or retry scheduling.

`spawns` is the chosen field name. It records direct subordinate executions,
including unsuccessful or skipped cases; it is unordered, acyclic, and has one
spawning parent per non-root Run within an execution tree. A leaf omits it or uses
an empty list. Neither parallel execution nor separate processes are implied.
A batch has one direct spawned Run for each direct case, matched by Specification
UUID. Nested batches recurse. Repeated case paths require distinct Run records.
Extra unpaired batch spawns and retry coordination are outside this initial contract.
Non-batch Runs can retain subsidiary executions without treating their outputs as
their own publications.

Only finalized records are serialized. Live progress remains runtime state.
Non-batch completion/solution combinations are:

| Completion | Permitted solution |
| --- | --- |
| completed | feasible, infeasible, unknown |
| limited | feasible, unknown |
| failed, cancelled | unknown, not_assessed |
| skipped | not_assessed |

A feasible conclusion requires accepted outputs. Other non-batch conclusions have
none. A limited execution can retain a feasible candidate with its limitations
reported; `feasible` never implies optimality. Failed numerical execution does not
establish infeasibility. Non-completed outcomes and unknown/infeasible conclusions
require diagnostics. Completed feasible/infeasible non-batch attempts and limited
attempts require runtime evidence; skipped attempts have no Runtime.

Batch solution is `not_applicable`. Its completion summarizes direct cases: all
completed gives completed; a mixture of completed and other cases gives partial;
otherwise use failed if any failed/partial, then limited, then cancelled, otherwise
skipped. Batch outputs are exactly the unique union of spawned outputs. A skipped
batch retains skipped case records. Failed cases never disappear from the population.

Accepted non-batch outputs are new Model revisions with one producing Run. Scalar
publication preserves input definitions and declaration identities, records all
assigned/unknown amounts, and points metadata.previous to the input Model. Recorded
amounts do not become future assignments. Temporary Specification mathematics and
objectives are not silently promoted into permanent output constraints. Broader
structural publication and Specification-local Value retention require explicit
adapters; the current bounded check reports these limitations.

Runtime identifies actual implementations and effective settings; it does not select
a backend. Times are timezone-qualified and recorded only when observed. Changed or
unapplied numerical requests require a `settings_adjusted` diagnostic explaining each
setting. Backend-specific options and full environment/RNG manifests remain extensions.

Diagnostics qualify targets by document revision. Residuals require a scoped target;
tolerances require residuals, must be nonnegative, and use compatible units. Messages
state the residual definition, scaling, and acceptance convention. Trace order and
observed timestamps agree. Publication/selection steps reference accepted outputs;
each accepted optimization output has selection evidence describing automatic or
user choice, method, basis, and limitations. This initial narrative trace is not a
complete policy/action language or machine-checked mathematical proof.

The examples are **synthetic hypothetical records**, not observed executions:

| Record | Purpose |
| --- | --- |
| [Forward Run](examples/run-forward.yaml) | Expected scalar resolution with illustrative diagnostics and trace. |
| [Inverse Run](examples/run-inverse.yaml) | Expected inverse resolution on the same input Model. |
| [Batch Run](examples/run-batch.yaml) | Explicit spawns and the union of their accepted outputs. |
| [Failed Run](examples/run-failed.yaml) | Pre-execution failure with no outputs. |
| [Skipped Run](examples/run-skipped.yaml) | Accounted-for case with no runtime or outputs. |
| [Forward output](examples/model-forward-output.yaml), [inverse output](examples/model-inverse-output.yaml) | Complete expected Model snapshots, separately identified and labelled synthetic. |

The Run schema imports shared Settings and Measure content, keeping one tree root.
Generated structural schemas, bounded conformance checks, and native Python round
trips establish the record contract. They neither perform nor certify execution.

## Validation and known limits

There are three distinct questions:

1. **Structural conformance:** are required fields, types, and encodings valid?
2. **Domain consistency:** do identities and references resolve, do units and
   memberships agree, and does evidence support the recorded content?
3. **Interpretation quality:** is the representation faithful to the documents,
   with assumptions and unresolved issues made explicit?

Generated schema validation addresses the first question. The current Python
conformance fixture checks a bounded part of the second. Neither implements or
certifies the third.

Run from the repository root:

```sh
# Environment with LinkML 1.11.1 and jsonschema 4.26.0:
python schema/checks/validate.py
python schema/checks/native_roundtrip.py
python schema/checks/expressions.py
python schema/checks/formulations.py
python schema/checks/models.py
python schema/checks/specifications.py
python schema/checks/runs.py

# Rangekeeper development environment:
PYTHONPATH=src python -m pytest src/tests/test_schema_graph_contract.py src/tests/test_scoped_codes.py -q
```

The schema check generates validators and checks both the README example and the
shared JSON fixture, including rejection of old code-reference and dictionary forms.
The native round-trip check generates Python classes in a temporary directory,
checks identifier/range declarations, and loads/dumps both examples. Optional empty
collections may be omitted by the generated dumper; meaningful content is preserved.
Its temporary wrapper groups test records and is not a new Model schema.

The expression check validates valuation, query/aggregation, function, and Constraint examples.
It rejects malformed kinds, mixed content, null literals, invalid reference syntax,
wrong operator forms, and invalid query projections. Bounded semantic checks in
`src/rangekeeper/model/_expression.py` reject dangling references, argument-binding
errors, coarse domain mismatches, and duplicate identities. These are conformance
fixtures, not a production compiler, query executor, or unit checker.
Generated Python round trips preserve operand and argument order, repeated Value
references, zero, false, and typed literals. The README predicate and Constraint
are also checked. Constraint cases cover Boolean result domains, nested/shared
predicate references, dangling or wrong-kind targets, and duplicate identities/codes.
They accept a literal false predicate without claiming its assertion is satisfiable.
JSON dumping uses `inject_type=False` for plain instance JSON. Generated Python
construction alone does not enforce all conditional schema rules.

The Formulation check validates the valuation fixture and generated Python round trips.
Bounded checks in `src/rangekeeper/model/_formulation.py` reject repeated ownership, containment
cycles, duplicate local names/codes, dangling or wrong-kind references, and non-Boolean
Constraint predicates. They accept sibling references, aliases to shared Values,
repeated local codes in different Formulations, zero content, and unresolved Values.
The existing expression checks are reused for the combined UUID scope. These checks
do not compile Formulations, infer units, evaluate Constraints, or prove solvability.

The Model check generates validators for Model, Metadata, and System, and checks a
complete document and native Python round trips. Bounded checks in
`src/rangekeeper/model/_validation.py` reuse Formulation checks and add catalogue/name scopes, domain
and evidence references, Assembly/Classification/Claim cycles, and available revision
history. Previous content is not imported for reference resolution. Arbitrary Claim
content stays opaque; generic Fact/content agreement and full unit inference are
outside this check. Optional empty containers can be omitted by the native dumper.

The Specification check generates structural validators and native Python records, then
checks the standalone examples, composed examples, batch, and variants.
`src/rangekeeper/specification/_composition.py` checks additive accumulation and batch references;
`src/rangekeeper/specification/_validation.py` validates pinned
revision references, composed ownership, additional mathematics, role completeness,
estimate eligibility, every scalar objective, finite content, and numerical request bounds.
Round trips preserve objective preference order in both directions; a secondary
objective cannot bypass reference, result-domain, or dependency-role checks.
It preserves input documents and accepts underdetermined or unsatisfiable mathematics
without claiming a solution. Duplicate unknowns require semantic checking because the
pinned JSON Schema generator does not emit that uniqueness rule.

This bounded checker accepts identical canonical unit spellings, or an explicitly
supplied unit-compatibility adapter. Different spellings require that adapter, even
when conversion would be valid. It does not infer expression units. Query dependencies
in imposed mathematics require a graph adapter and are reported as unsupported;
unused reporting queries do not require solve roles. Persistence, solver execution,
actual numerical settings, and output publication are not implemented by these checks.

The Run check generates validators for Run and its embedded records, then exercises
synthetic scalar outcomes, nested batches, limited/failed/skipped cases, selected
candidates, and inverse roles on a previously recorded snapshot. It checks scoped
references, spawn ownership/cycles, direct-case accounting, aggregate outputs/status,
settings, timing, and scalar publication. Native round trips preserve UUID references,
trace order, and time instants (equivalent timezone spellings are normalized).
The bounded publication checker compares fixture definitions without reordering
collections; more general semantic equivalence requires an adapter. It accepts exact
canonical units and checks supplied quantities, but does not evaluate equations,
verify claimed residuals, prove optimality, or establish full provenance agreement.

Runtime checks construct canonical objects from the shared fixture, validate
references/membership/provenance, and round-trip existing graph JSON. They cover
UUID references, wrong-kind/dangling targets, duplicate identities and scoped codes,
renames without reference changes, and parent references independent of list order.
They also check compatible units at different scales, incompatible units in both
Measurements and Claims, and unresolved content versus a zero magnitude.

Known limits of this checkpoint:

- The pinned JSON Schema generator omits some set-uniqueness constraints,
  address-dictionary key checks, and conditional minimum Claim support counts.
  Generated JSON Schema also accepts dangling UUIDs; native reference declarations
  do not by themselves prove referential integrity.
- Reference existence, cycles, unit compatibility, finite amounts, and Fact/target
  agreement require validation beyond record shapes.
- The fixture maps local Value names to Python's Measure-code dictionary. Multiple
  Values using the same Measure cannot yet be represented in that runtime collection.
- These are limits of the legacy graph fixture bridge. The canonical Model supports
  multiple owner-local Values using one Measure and has schema-based JSON/YAML codecs.
  Generic Claim/Fact-content agreement, richer executable Value semantics, legacy
  consumer migration and richer calculation execution remain incomplete. The bounded
  affine scalar adapter now produces genuine accepted output Models.

## Next work

Work units 2A/2B are implemented: see the [record boundary](../docs/RECORD_BOUNDARY.md)
and [verification](../docs/research/domain-migration/turn1/README.md). Structural suites
now load packaged schemas; run `python tools/schema/generate.py --check` from the
repository root to verify freshness, or regenerate after intentional schema changes.
Standalone checks reject stale schema-source fingerprints. Semantic checks live in
the library, and the conformance scripts call them. The canonical domain APIs,
codecs, revision stores and affine scalar execution are implemented.


The [library architecture and migration plan](../docs/LIBRARY_ARCHITECTURE.md)
records the [2026-10-02 decision](../docs/research/current-schema-comparison/DECISION.md)
to retain LinkML and close the CUE comparison for this stage. The
[domain replacement map](../docs/DOMAIN_MIGRATION_MAP.md) and
[baseline](../docs/research/domain-migration/BASELINE.md) complete Step 1. The immutable record boundary and [Model/Specification core](../docs/DOMAIN_CORE.md)
are implemented, together with [Run, codecs and revision persistence](../docs/RUN_AND_STORAGE.md).
The [Turn 3 evidence](../docs/research/domain-migration/turn3/README.md) verifies these
public APIs in an isolated installed wheel. [Step 5 evidence](../docs/research/scalar-execution/README.md)
also verifies `rangekeeper.execution` with Pyomo 6.10.1 and HiGHS 1.15.1 outside
the checkout. The temporary `schema/execution/` and later promotion plan is
superseded. [Model-backed views and reductions](../docs/GRAPH_MODEL.md) now implement Step 6A/6B.
Table/projection and source-workflow migration remain next.

1. **Migrate graph operations and consumers.** The scalar checkpoint now executes
   forward/inverse valuation, reuses genuine outputs with new roles, independently
   checks candidates and publishes immutable Models and authentic Runs. Adapt
   graph views, traversal/reduction, tables and source workflows to that canonical
   core under the [consumer map](../docs/DOMAIN_MIGRATION_MAP.md).
2. **Extend publication and provenance as required.** The scalar adapter preserves
   previous Claims and records new method-labelled quantity evidence. Specification-local
   Value publication and typed derived evidence remain bounded extensions; temporary
   constraints must not become permanent. Extend settings and diagnostics only
   when the selected adapter supports them.
3. **Extend in stages.** Start with deterministic valuation on fixed calendars and
   supplied scenarios. Add temporal and financial Value kinds, evaluate many saved
   futures, then introduce committed choices and adaptive policies. Numerical market
   generation can be used before any algebraic inversion of the generator.

The [Formulation design direction](../docs/MODEL_SPECIFICATION_RUN.md#36-mathematical-formulations)
and [execution priorities](../docs/MODEL_SPECIFICATION_RUN.md#51-execution-priorities-and-capability-boundary)
record the 2026-10-01 discussion and the first explicit Formulation draft. They distinguish
schema contracts from proposed extensions and unimplemented capabilities. Values, mathematical Formulations, and Mark8 editor
components have separate responsibilities. Numerical and symbolic implementations
must be checked for agreement; a Formulation does not confer general inverse solvability.

Legacy import/export conversion, Characteristics/Value consumer migration, remaining
typed Claim payloads, and document interpretation remain separate work. They do
not need to be completed before scalar execution. New project
vocabulary should continue to require records rather than schema edits.

The [Model–Specification–Run specification](../docs/MODEL_SPECIFICATION_RUN.md)
and [policy example](../docs/PROJECT_DEFINITION_AND_POLICY_EXAMPLE.md) provide wider
context. This README clarifies the immediate schema/instance boundary; it does not
claim completion of those broader designs.
