-- # Class: Model Description: A self-contained snapshot of a system's declarations, mathematical formulations, and recorded content, identified by its Metadata.
--     * Slot: id
--     * Slot: metadata_id Description: Required identity, schema contract version, and optional descriptive/history fields.
--     * Slot: definitions_id Description: Canonical Taxonomy, Measure, and Function definitions referenced by this snapshot.
--     * Slot: system_id Description: The domain objects and explicit mathematical formulations represented by this Model.
--     * Slot: provenance_id Description: Evidence and reasoning supporting recorded domain and Value content in this snapshot.
-- # Class: System Description: The Entities, Relationships, Assemblies, and mathematical formulations of a Model.
--     * Slot: id
-- # Class: Classification Description: A named definition node in a taxonomy hierarchy.
--     * Slot: id Description: Stable identity across code changes and Model revisions.
--     * Slot: code Description: Case-sensitive code unique within its Taxonomy; descriptive metadata, not reference identity.
--     * Slot: name Description: Nonblank human-readable name.
--     * Slot: definition Description: Optional explanatory text; an empty string is permitted.
--     * Slot: parent Description: Parent Classification in the same Taxonomy, referenced by UUID. An absent or null parent denotes a root candidate.
--     * Slot: Taxonomy_id Description: Autocreated FK slot
-- # Class: Taxonomy Description: A named, single-root hierarchy of Classifications.
--     * Slot: id
--     * Slot: code Description: Case-sensitive code unique in the Model's taxonomy catalogue.
--     * Slot: name
--     * Slot: definition
--     * Slot: Definitions_id Description: Autocreated FK slot
-- # Class: Quantity Description: Numerical content consisting of a finite magnitude and explicit units.
--     * Slot: id
--     * Slot: magnitude Description: Finite numerical magnitude expressed in the accompanying units.
--     * Slot: units Description: Explicit units for this magnitude, such as m^2, AUD/year, or dimensionless.
-- # Class: Measure Description: An identified definition of a measurable characteristic and its canonical units.
--     * Slot: id Description: Stable identity of this Measure definition.
--     * Slot: code Description: Case-sensitive code unique within the Model’s Measure collection; not reference identity.
--     * Slot: name Description: Nonblank human-readable name of the measured characteristic.
--     * Slot: units Description: Nonblank expression specifying the canonical units for quantities interpreted through this Measure, such as m^2 or AUD/year. Unitless quantities must have an explicit dimensionless convention.
--     * Slot: definition Description: Optional explanatory text describing the measurement convention.
--     * Slot: Definitions_id Description: Autocreated FK slot
-- # Class: Measurement Description: An identified measurable property with a Measure and an optional Quantity.
--     * Slot: measure Description: Measure defining meaning and canonical units, referenced by its stable UUID.
--     * Slot: id Description: Stable identity of the Measurement, used by provenance Facts.
--     * Slot: quantity_id Description: Optional recorded numerical content. Its units must be compatible with the Measure's canonical units. Omission or null denotes unresolved content.
-- # Class: Domain Description: The permitted content of an argument or result, including its kind, compatible units, measurement meaning, and collection elements where applicable.
--     * Slot: id
--     * Slot: kind Description: The category of content permitted by this Domain.
--     * Slot: units Description: Optional compatible units required for Quantity content. Omission leaves units unconstrained by the signature; a concrete Quantity still requires explicit units.
--     * Slot: measure Description: Optional exact measurement meaning required for a measurement or Flow.
--     * Slot: collection_kind Description: Optional collection shape required by this signature.
--     * Slot: item_domain_id Description: Domain of each collection element.
-- # Class: Parameter Description: A named argument in a Function signature. List order determines positional argument order.
--     * Slot: id
--     * Slot: name
--     * Slot: kind Description: How a call may supply this parameter.
--     * Slot: required Description: Whether a call must supply this argument.
--     * Slot: Function_id Description: Autocreated FK slot
--     * Slot: domain_id Description: Content permitted for this argument.
-- # Class: Function Description: An identified, versioned contract for a pure mathematical or domain function, independent of a particular runtime implementation.
--     * Slot: id
--     * Slot: code
--     * Slot: name Description: Human-readable function name.
--     * Slot: version
--     * Slot: semantics Description: Mathematical meaning, argument conventions, domain restrictions, and exceptional cases.
--     * Slot: unit_rule Description: How result units follow from the arguments, or why units do not apply. This rule requires semantic implementation; prose is not an executable unit checker.
--     * Slot: empty_collection Description: Required for functions with collection arguments. Zero is permitted only when the result domain and units can be established without reading a member.
--     * Slot: Definitions_id Description: Autocreated FK slot
--     * Slot: result_id Description: Domain of the result.
-- # Class: Definitions Description: Reusable Taxonomies, Measures, and Functions identified by stable UUIDs within a Model.
--     * Slot: id
-- # Class: Assembly Description: An Entity identifying a collection of Entities and Relationships. Members are referenced by identity and may belong to more than one Assembly. Membership does not imply spatial containment or duplicate its members.
--     * Slot: classification Description: Classification describing the object, referenced by its stable UUID.
--     * Slot: id Description: Stable identity of the Entity, distinct from a Model revision.
--     * Slot: code Description: Optional case-sensitive code unique among all Entities and Assemblies in the Model. Renaming it preserves UUID identity and references.
--     * Slot: name Description: Human-readable display name; not used as identity.
--     * Slot: System_id Description: Autocreated FK slot
--     * Slot: characteristics_id Description: The Entity's labels and named values.
-- # Class: Traversal Description: One traversal step over domain Relationships or Assembly membership.
--     * Slot: id
--     * Slot: kind
--     * Slot: depth
--     * Slot: classification Description: Exact Classification of Relationships to follow.
--     * Slot: direction
--     * Slot: Query_id Description: Autocreated FK slot
-- # Class: Criterion Description: Require an Entity Label with this owner-local key to include the exact Classification.
--     * Slot: id
--     * Slot: key Description: Owner-local Label key.
--     * Slot: classification
--     * Slot: Filter_id Description: Autocreated FK slot
-- # Class: Filter Description: Conjunctive filters over fixed Entity metadata. No numerical expression or solved amount determines membership.
--     * Slot: id
--     * Slot: classification
-- # Class: Projection Description: Select Entity identities or Values belonging to each matching Entity.
--     * Slot: id
--     * Slot: kind
--     * Slot: key Description: Exact owner-local Value key.
--     * Slot: measure Description: Select Values with this exact Measure.
--     * Slot: cardinality
--     * Slot: missing
-- # Class: Query Description: A non-executing query specification returning Entity or Value identities from the containing Model revision.
--     * Slot: id
--     * Slot: starting_at
--     * Slot: duplicates
--     * Slot: filter_id
--     * Slot: projection_id
-- # Class: Reference Description: A Value or Movement UUID resolved in the containing Model or composed Specification. Execution diagnostic references resolve in the Run's input Model. Names, matching keys and positions are never identities.
--     * Slot: id
--     * Slot: target Description: UUID of a Value or Movement declaration in the applicable scope.
-- # Class: Assignment Description: An explicit scalar or Movement target and finite supplied Quantity; its collection determines assignment or estimate semantics.
--     * Slot: id
--     * Slot: target_id
--     * Slot: quantity_id Description: Explicit finite magnitude and compatible units; omission or null is not a supplied amount.
-- # Class: Expression Description: An identified mathematical expression. Its kind determines its content; nested expressions retain order and UUID references resolve in the applicable Model or composed Specification scope.
--     * Slot: id Description: Stable identity of this Expression across Model revisions.
--     * Slot: kind
--     * Slot: boolean Description: Boolean literal; false is a literal, not absence.
--     * Slot: operator
--     * Slot: Expression_id Description: Autocreated FK slot
--     * Slot: Call_id Description: Autocreated FK slot
--     * Slot: Formulation_id Description: Autocreated FK slot
--     * Slot: quantity_id Description: Numerical literal with an explicit magnitude and units, independent of any Measure. Use dimensionless for unitless content. Zero is a literal, not absence.
--     * Slot: target_id Description: Explicit Value or Movement symbol; never implicit recorded content.
--     * Slot: operand_id Description: Operand of unary negation or Boolean negation.
--     * Slot: call_id
--     * Slot: selection_id
--     * Slot: query_id
-- # Class: Call Description: Application of an identified Function to positional and named expression arguments.
--     * Slot: id
--     * Slot: function
-- # Class: Argument Description: One named expression argument in a Function call.
--     * Slot: id
--     * Slot: name
--     * Slot: Call_id Description: Autocreated FK slot
--     * Slot: expression_id
-- # Class: Selection Description: Read a declared member or indexed element from structured expression content.
--     * Slot: id
--     * Slot: kind
--     * Slot: member Description: Declared member name.
--     * Slot: base_id
--     * Slot: index_id Description: Index expression.
-- # Class: Constraint Description: An identified requirement that a referenced Boolean Expression be true in the context where the Constraint is imposed.
--     * Slot: id Description: Stable identity of the Constraint across Model revisions.
--     * Slot: code Description: Optional case-sensitive code unique within its Constraint collection; not reference identity. Renaming it preserves UUID references.
--     * Slot: name Description: Human-readable display name; not used as identity.
--     * Slot: description Description: Explanation of the requirement and its purpose.
--     * Slot: predicate Description: UUID reference to the Expression required to be true. Reference existence and a Boolean result domain require semantic validation beyond record shape.
--     * Slot: Formulation_id Description: Autocreated FK slot
-- # Class: Binding Description: A local interface name that refers to an existing canonical Value by UUID.
--     * Slot: id
--     * Slot: name Description: Case-sensitive local interface name; not reference identity.
--     * Slot: value Description: UUID of the shared Value. Its declaration supplies its kind, Measure, and content.
--     * Slot: Formulation_id Description: Autocreated FK slot
--     * Slot: ScenarioRealization_id Description: Autocreated FK slot
-- # Class: Formulation Description: An identified mathematical container with explicit local declarations, expressions, and asserted constraints. Formulations may contain child Formulations and bind names to shared Values.
--     * Slot: id Description: Stable identity of this Formulation across Model revisions.
--     * Slot: code Description: Optional case-sensitive code unique among sibling Formulations; not reference identity.
--     * Slot: name Description: Human-readable display name.
--     * Slot: description Description: Explanation of the mathematical purpose of this Formulation.
--     * Slot: System_id Description: Autocreated FK slot
--     * Slot: Formulation_id Description: Autocreated FK slot
-- # Class: Characteristics Description: A collection of Labels and Values belonging to an Entity or Relationship. Each Label or Value has a stable UUID and a key unique within its collection.
--     * Slot: id
-- # Class: Label Description: A named set of Classifications describing an aspect of an Entity or Relationship.
--     * Slot: id Description: Stable identity of the Label, used by provenance Facts.
--     * Slot: key Description: Name unique within the owner's characteristics.labels collection.
--     * Slot: Characteristics_id Description: Autocreated FK slot
-- # Class: Value Description: An identified, typed Value belonging to an Entity or Relationship's Characteristics, or declared locally within a mathematical Formulation. Its key provides a name within the owner's values collection; its UUID identifies the symbol independently of that name.
--     * Slot: measure Description: Measure defining meaning and canonical units, referenced by its stable UUID.
--     * Slot: id Description: Stable identity of the Value, used by provenance Facts.
--     * Slot: key Description: Nonblank name unique within the owner's values collection; not reference identity.
--     * Slot: kind Description: The kind of content represented by this characteristic.
--     * Slot: description Description: Explanation of the meaning of this Value within its owner.
--     * Slot: Formulation_id Description: Autocreated FK slot
--     * Slot: Characteristics_id Description: Autocreated FK slot
--     * Slot: quantity_id Description: Optional recorded numerical content. Its units must be compatible with the Measure's canonical units. Omission or null denotes unresolved content.
--     * Slot: flow_id
--     * Slot: content_id
-- # Class: Entity Description: An identifiable domain object, such as an apartment, building, or actor. Its identity persists across immutable Model revisions. Loading its definition does not execute calculations.
--     * Slot: classification Description: Classification describing the object, referenced by its stable UUID.
--     * Slot: id Description: Stable identity of the Entity, distinct from a Model revision.
--     * Slot: code Description: Optional case-sensitive code unique among all Entities and Assemblies in the Model. Renaming it preserves UUID identity and references.
--     * Slot: name Description: Human-readable display name; not used as identity.
--     * Slot: System_id Description: Autocreated FK slot
--     * Slot: characteristics_id Description: The Entity's labels and named values.
-- # Class: Relationship Description: An identified, directed connection from one Entity to another. Its classification describes the connection; its characteristics describe properties of the connection itself.
--     * Slot: classification Description: Classification describing the object, referenced by its stable UUID.
--     * Slot: id Description: Stable identity of the Relationship across Model revisions.
--     * Slot: source Description: UUID of the source Entity.
--     * Slot: target Description: UUID of the target Entity.
--     * Slot: System_id Description: Autocreated FK slot
--     * Slot: characteristics_id Description: Labels and Values describing this connection.
-- # Class: Flow Description: Ordered temporal quantities owned by one Value. Dates are coordinates, not units. Empty, unresolved and zero movements are distinct. The overall model logic defines the meaning of the quantities and selects their calculations; a Flow carries no semantic kind or basis.
--     * Slot: id
--     * Slot: units
-- # Class: Movement Description: One numerical entry in a Flow, associated with a date or period. The overall model logic determines its meaning. At least one of date or period is required. With a period, date records an independent payment or observation date and need not lie inside the period. Derived boundary dates are calculated, not stored. UUID identifies the Movement independently of dates and optional matching keys. Repeated event dates require distinct nonblank keys; keys are not reference identity. Magnitude omission/null means unresolved. Claims retain source or derivation evidence.
--     * Slot: id Description: Stable Movement identity across Model revisions. Derived numerical results receive fresh identities.
--     * Slot: key Description: Optional event matching key and readable label; never reference identity.
--     * Slot: date
--     * Slot: magnitude
--     * Slot: Flow_id Description: Autocreated FK slot
--     * Slot: period_id
-- # Class: Metadata Description: Identity, description, and optional lineage of one immutable document revision.
--     * Slot: id Description: UUID identifying the enclosing immutable document revision.
--     * Slot: schema_version Description: Version of the enclosing document's schema contract.
--     * Slot: name Description: Optional human-readable name of this revision.
--     * Slot: description Description: Optional explanation of this revision and its purpose.
--     * Slot: previous Description: UUID of the preceding revision of the same document kind, referencing its Metadata.
-- # Class: Period Description: Half-open interval [start_inclusive, end_exclusive). Date boundaries use the Gregorian calendar; start must precede end.
--     * Slot: id
--     * Slot: start_inclusive
--     * Slot: end_exclusive
--     * Slot: ScenarioPlan_id Description: Autocreated FK slot
-- # Class: Span Description: Named extent, using the same half-open boundary convention as Period.
--     * Slot: id
--     * Slot: name
--     * Slot: start_inclusive
--     * Slot: end_exclusive
-- # Class: PropertyContent Description: Tagged inert content. Scalar text preserves exact type and representation, including negative zero. Containers never instantiate arbitrary Python classes. Conditional shape and canonical scalar grammar are checked semantically.
--     * Slot: id
--     * Slot: kind
--     * Slot: text
--     * Slot: zone
--     * Slot: fold
--     * Slot: PropertyContent_id Description: Autocreated FK slot
-- # Class: ContentEntry
--     * Slot: id
--     * Slot: PropertyContent_id Description: Autocreated FK slot
--     * Slot: key_id
--     * Slot: value_id
-- # Class: Distribution Description: Serializable distribution parameters, with explicit units; no live random generator.
--     * Slot: id
--     * Slot: kind
--     * Slot: lower
--     * Slot: upper
--     * Slot: mode
--     * Slot: weighting
--     * Slot: units
-- # Class: ScenarioParameter Description: One named constant or sampled parameter; exactly one input is required by semantic validation.
--     * Slot: id
--     * Slot: name
--     * Slot: ScenarioPlan_id Description: Autocreated FK slot
--     * Slot: quantity_id
--     * Slot: distribution_id
-- # Class: ScenarioPlan Description: Finite market generation plan. This is input-generation provenance, not governing mathematics.
--     * Slot: id
--     * Slot: method
--     * Slot: seed
-- # Class: RandomStream Description: Stable component stream identity derived from seed, scenario key and component name.
--     * Slot: id
--     * Slot: name
--     * Slot: identifier
--     * Slot: ScenarioRealization_id Description: Autocreated FK slot
-- # Class: LibraryVersion Description: Recorded implementation dependency version.
--     * Slot: id
--     * Slot: name
--     * Slot: version
--     * Slot: CalculationProvenance_id Description: Autocreated FK slot
--     * Slot: ScenarioRealization_id Description: Autocreated FK slot
-- # Class: ObservationAvailability Description: Earliest date a recorded Value or Movement may be supplied to a policy.
--     * Slot: id
--     * Slot: available_at
--     * Slot: ScenarioRealization_id Description: Autocreated FK slot
--     * Slot: target_id
-- # Class: CalculationProvenance Description: Calculation implementation identity, separate from captured sampling provenance.
--     * Slot: id
--     * Slot: name
--     * Slot: fingerprint
-- # Class: ScenarioRealization Description: Captured scenario inputs and paths. Stored draws permit replay without random sampling.
--     * Slot: id
--     * Slot: key
--     * Slot: generator
--     * Slot: Provenance_id Description: Autocreated FK slot
--     * Slot: plan_id
--     * Slot: calculation_id
-- # Class: Provenance Description: Facts connecting graph objects to supporting Claims, with the Sources and upstream Claims needed to follow their lineage.
--     * Slot: id
-- # Class: Source Description: An identifiable edition of an external evidence artifact.
--     * Slot: id
--     * Slot: name
--     * Slot: checksum Description: Content checksum identifying the evidence edition.
--     * Slot: author
--     * Slot: Provenance_id Description: Autocreated FK slot
--     * Slot: issued_at_id
--     * Slot: received_at_id
-- # Class: Location Description: An address within a specific Source edition.
--     * Slot: id
--     * Slot: source
-- # Class: Entry Description: A named text component of a source address.
--     * Slot: key
--     * Slot: value
--     * Slot: Location_id Description: Autocreated FK slot
-- # Class: Method Description: The named process used to assert, derive, or reconcile evidence.
--     * Slot: id
--     * Slot: code
--     * Slot: version
--     * Slot: description
-- # Class: Content Description: Candidate content whose structure and meaning depend on the supported target. Content must be validated against that target before a Fact is accepted; this generic envelope does not make arbitrary content executable.
--     * Slot: id
-- # Class: Claim Description: Sourced, asserted, or derived candidate content and its supporting lineage.
--     * Slot: id
--     * Slot: kind
--     * Slot: Provenance_id Description: Autocreated FK slot
--     * Slot: content_id
--     * Slot: method_id
-- # Class: Fact Description: Supporting Claims for the recorded state of one graph object or characteristic.
--     * Slot: id
--     * Slot: Provenance_id Description: Autocreated FK slot
--     * Slot: target_id Description: The actual graph object or characteristic being supported, referenced by its stable UUID.
--     * Slot: reconciliation_id
-- # Class: Reconciliation Description: Explicit selection of one supporting Claim when evidence conflicts.
--     * Slot: id
--     * Slot: selected Description: UUID of a Claim included in the Fact's claims.
--     * Slot: status
--     * Slot: method_id
-- # Class: Measure_tags
--     * Slot: Measure_id Description: Autocreated FK slot
--     * Slot: tags Description: Unordered, nonblank descriptive terms, with no duplicates.
-- # Class: Assembly_entities
--     * Slot: Assembly_id Description: Autocreated FK slot
--     * Slot: entities_id Description: Unordered, unique UUIDs of member Entities, including nested Assemblies.
-- # Class: Assembly_relationships
--     * Slot: Assembly_id Description: Autocreated FK slot
--     * Slot: relationships_id Description: Unordered, unique UUIDs of member Relationships.
-- # Class: Label_classifications
--     * Slot: Label_id Description: Autocreated FK slot
--     * Slot: classifications_id Description: Unique UUID references to Classifications describing this aspect.
-- # Class: Movement_claims
--     * Slot: Movement_id Description: Autocreated FK slot
--     * Slot: claims
-- # Class: Claim_sources
--     * Slot: Claim_id Description: Autocreated FK slot
--     * Slot: sources_id Description: Source Locations or UUID references to upstream Claims.
-- # Class: Fact_claims
--     * Slot: Fact_id Description: Autocreated FK slot
--     * Slot: claims_id Description: Unique UUIDs of supporting Claims; at least one is required.

CREATE TABLE "System" (
	id INTEGER NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX "ix_System_id" ON "System" (id);

CREATE TABLE "Quantity" (
	id INTEGER NOT NULL,
	magnitude NUMERIC NOT NULL,
	units TEXT NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX "ix_Quantity_id" ON "Quantity" (id);

CREATE TABLE "Definitions" (
	id INTEGER NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX "ix_Definitions_id" ON "Definitions" (id);

CREATE TABLE "Reference" (
	id INTEGER NOT NULL,
	target TEXT NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX "ix_Reference_id" ON "Reference" (id);

CREATE TABLE "Expression" (
	id TEXT NOT NULL,
	kind VARCHAR(9) NOT NULL,
	boolean BOOLEAN,
	operator VARCHAR(21),
	"Expression_id" TEXT,
	"Call_id" INTEGER,
	"Formulation_id" TEXT,
	quantity_id INTEGER,
	target_id INTEGER,
	operand_id TEXT,
	call_id INTEGER,
	selection_id INTEGER,
	query_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY("Expression_id") REFERENCES "Expression" (id),
	FOREIGN KEY("Call_id") REFERENCES "Call" (id),
	FOREIGN KEY("Formulation_id") REFERENCES "Formulation" (id),
	FOREIGN KEY(quantity_id) REFERENCES "Quantity" (id),
	FOREIGN KEY(target_id) REFERENCES "Reference" (id),
	FOREIGN KEY(operand_id) REFERENCES "Expression" (id),
	FOREIGN KEY(call_id) REFERENCES "Call" (id),
	FOREIGN KEY(selection_id) REFERENCES "Selection" (id),
	FOREIGN KEY(query_id) REFERENCES "Query" (id)
);
CREATE INDEX "ix_Expression_id" ON "Expression" (id);

CREATE TABLE "Selection" (
	id INTEGER NOT NULL,
	kind VARCHAR(6) NOT NULL,
	member TEXT,
	base_id TEXT NOT NULL,
	index_id TEXT,
	PRIMARY KEY (id),
	FOREIGN KEY(base_id) REFERENCES "Expression" (id),
	FOREIGN KEY(index_id) REFERENCES "Expression" (id)
);
CREATE INDEX "ix_Selection_id" ON "Selection" (id);

CREATE TABLE "Characteristics" (
	id INTEGER NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX "ix_Characteristics_id" ON "Characteristics" (id);

CREATE TABLE "Flow" (
	id INTEGER NOT NULL,
	units TEXT NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX "ix_Flow_id" ON "Flow" (id);

CREATE TABLE "Metadata" (
	id TEXT NOT NULL,
	schema_version TEXT NOT NULL,
	name TEXT,
	description TEXT,
	previous TEXT,
	PRIMARY KEY (id),
	FOREIGN KEY(previous) REFERENCES "Metadata" (id)
);
CREATE INDEX "ix_Metadata_id" ON "Metadata" (id);

CREATE TABLE "Span" (
	id INTEGER NOT NULL,
	name TEXT,
	start_inclusive DATE NOT NULL,
	end_exclusive DATE NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX "ix_Span_id" ON "Span" (id);

CREATE TABLE "PropertyContent" (
	id INTEGER NOT NULL,
	kind VARCHAR(13) NOT NULL,
	text TEXT,
	zone TEXT,
	fold INTEGER,
	"PropertyContent_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY("PropertyContent_id") REFERENCES "PropertyContent" (id)
);
CREATE INDEX "ix_PropertyContent_id" ON "PropertyContent" (id);

CREATE TABLE "Distribution" (
	id INTEGER NOT NULL,
	kind VARCHAR(10) NOT NULL,
	lower FLOAT NOT NULL,
	upper FLOAT NOT NULL,
	mode FLOAT,
	weighting FLOAT,
	units TEXT NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX "ix_Distribution_id" ON "Distribution" (id);

CREATE TABLE "ScenarioPlan" (
	id TEXT NOT NULL,
	method TEXT NOT NULL,
	seed INTEGER NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX "ix_ScenarioPlan_id" ON "ScenarioPlan" (id);

CREATE TABLE "CalculationProvenance" (
	id INTEGER NOT NULL,
	name TEXT NOT NULL,
	fingerprint TEXT NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX "ix_CalculationProvenance_id" ON "CalculationProvenance" (id);

CREATE TABLE "Provenance" (
	id INTEGER NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX "ix_Provenance_id" ON "Provenance" (id);

CREATE TABLE "Method" (
	id INTEGER NOT NULL,
	code TEXT NOT NULL,
	version TEXT,
	description TEXT,
	PRIMARY KEY (id)
);
CREATE INDEX "ix_Method_id" ON "Method" (id);

CREATE TABLE "Content" (
	id INTEGER NOT NULL,
	PRIMARY KEY (id)
);
CREATE INDEX "ix_Content_id" ON "Content" (id);

CREATE TABLE "Model" (
	id INTEGER NOT NULL,
	metadata_id TEXT NOT NULL,
	definitions_id INTEGER,
	system_id INTEGER,
	provenance_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(metadata_id) REFERENCES "Metadata" (id),
	FOREIGN KEY(definitions_id) REFERENCES "Definitions" (id),
	FOREIGN KEY(system_id) REFERENCES "System" (id),
	FOREIGN KEY(provenance_id) REFERENCES "Provenance" (id)
);
CREATE INDEX "ix_Model_id" ON "Model" (id);

CREATE TABLE "Taxonomy" (
	id TEXT NOT NULL,
	code TEXT NOT NULL,
	name TEXT NOT NULL,
	definition TEXT,
	"Definitions_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY("Definitions_id") REFERENCES "Definitions" (id)
);
CREATE INDEX "ix_Taxonomy_id" ON "Taxonomy" (id);

CREATE TABLE "Measure" (
	id TEXT NOT NULL,
	code TEXT NOT NULL,
	name TEXT NOT NULL,
	units TEXT NOT NULL,
	definition TEXT,
	"Definitions_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY("Definitions_id") REFERENCES "Definitions" (id)
);
CREATE INDEX "ix_Measure_id" ON "Measure" (id);

CREATE TABLE "Assignment" (
	id INTEGER NOT NULL,
	target_id INTEGER NOT NULL,
	quantity_id INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(target_id) REFERENCES "Reference" (id),
	FOREIGN KEY(quantity_id) REFERENCES "Quantity" (id)
);
CREATE INDEX "ix_Assignment_id" ON "Assignment" (id);

CREATE TABLE "Formulation" (
	id TEXT NOT NULL,
	code TEXT,
	name TEXT,
	description TEXT,
	"System_id" INTEGER,
	"Formulation_id" TEXT,
	PRIMARY KEY (id),
	FOREIGN KEY("System_id") REFERENCES "System" (id),
	FOREIGN KEY("Formulation_id") REFERENCES "Formulation" (id)
);
CREATE INDEX "ix_Formulation_id" ON "Formulation" (id);

CREATE TABLE "Label" (
	id TEXT NOT NULL,
	"key" TEXT NOT NULL,
	"Characteristics_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY("Characteristics_id") REFERENCES "Characteristics" (id)
);
CREATE INDEX "ix_Label_id" ON "Label" (id);

CREATE TABLE "Period" (
	id INTEGER NOT NULL,
	start_inclusive DATE NOT NULL,
	end_exclusive DATE NOT NULL,
	"ScenarioPlan_id" TEXT,
	PRIMARY KEY (id),
	FOREIGN KEY("ScenarioPlan_id") REFERENCES "ScenarioPlan" (id)
);
CREATE INDEX "ix_Period_id" ON "Period" (id);

CREATE TABLE "ContentEntry" (
	id INTEGER NOT NULL,
	"PropertyContent_id" INTEGER,
	key_id INTEGER NOT NULL,
	value_id INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY("PropertyContent_id") REFERENCES "PropertyContent" (id),
	FOREIGN KEY(key_id) REFERENCES "PropertyContent" (id),
	FOREIGN KEY(value_id) REFERENCES "PropertyContent" (id)
);
CREATE INDEX "ix_ContentEntry_id" ON "ContentEntry" (id);

CREATE TABLE "ScenarioParameter" (
	id INTEGER NOT NULL,
	name TEXT NOT NULL,
	"ScenarioPlan_id" TEXT,
	quantity_id INTEGER,
	distribution_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY("ScenarioPlan_id") REFERENCES "ScenarioPlan" (id),
	FOREIGN KEY(quantity_id) REFERENCES "Quantity" (id),
	FOREIGN KEY(distribution_id) REFERENCES "Distribution" (id)
);
CREATE INDEX "ix_ScenarioParameter_id" ON "ScenarioParameter" (id);

CREATE TABLE "ScenarioRealization" (
	id TEXT NOT NULL,
	"key" TEXT NOT NULL,
	generator TEXT NOT NULL,
	"Provenance_id" INTEGER,
	plan_id TEXT NOT NULL,
	calculation_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY("Provenance_id") REFERENCES "Provenance" (id),
	FOREIGN KEY(plan_id) REFERENCES "ScenarioPlan" (id),
	FOREIGN KEY(calculation_id) REFERENCES "CalculationProvenance" (id)
);
CREATE INDEX "ix_ScenarioRealization_id" ON "ScenarioRealization" (id);

CREATE TABLE "Source" (
	id TEXT NOT NULL,
	name TEXT NOT NULL,
	checksum TEXT NOT NULL,
	author TEXT,
	"Provenance_id" INTEGER,
	issued_at_id INTEGER,
	received_at_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY("Provenance_id") REFERENCES "Provenance" (id),
	FOREIGN KEY(issued_at_id) REFERENCES "Content" (id),
	FOREIGN KEY(received_at_id) REFERENCES "Content" (id)
);
CREATE INDEX "ix_Source_id" ON "Source" (id);

CREATE TABLE "Claim" (
	id TEXT NOT NULL,
	kind VARCHAR(8) NOT NULL,
	"Provenance_id" INTEGER,
	content_id INTEGER NOT NULL,
	method_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY("Provenance_id") REFERENCES "Provenance" (id),
	FOREIGN KEY(content_id) REFERENCES "Content" (id),
	FOREIGN KEY(method_id) REFERENCES "Method" (id)
);
CREATE INDEX "ix_Claim_id" ON "Claim" (id);

CREATE TABLE "Classification" (
	id TEXT NOT NULL,
	code TEXT NOT NULL,
	name TEXT NOT NULL,
	definition TEXT,
	parent TEXT,
	"Taxonomy_id" TEXT,
	PRIMARY KEY (id),
	FOREIGN KEY(parent) REFERENCES "Classification" (id),
	FOREIGN KEY("Taxonomy_id") REFERENCES "Taxonomy" (id)
);
CREATE INDEX "ix_Classification_id" ON "Classification" (id);

CREATE TABLE "Measurement" (
	measure TEXT NOT NULL,
	id TEXT NOT NULL,
	quantity_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(measure) REFERENCES "Measure" (id),
	FOREIGN KEY(quantity_id) REFERENCES "Quantity" (id)
);
CREATE INDEX "ix_Measurement_id" ON "Measurement" (id);

CREATE TABLE "Domain" (
	id INTEGER NOT NULL,
	kind VARCHAR(11) NOT NULL,
	units TEXT,
	measure TEXT,
	collection_kind VARCHAR(8),
	item_domain_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(measure) REFERENCES "Measure" (id),
	FOREIGN KEY(item_domain_id) REFERENCES "Domain" (id)
);
CREATE INDEX "ix_Domain_id" ON "Domain" (id);

CREATE TABLE "Projection" (
	id INTEGER NOT NULL,
	kind VARCHAR(6) NOT NULL,
	"key" TEXT,
	measure TEXT,
	cardinality VARCHAR(4),
	missing VARCHAR(5),
	PRIMARY KEY (id),
	FOREIGN KEY(measure) REFERENCES "Measure" (id)
);
CREATE INDEX "ix_Projection_id" ON "Projection" (id);

CREATE TABLE "Constraint" (
	id TEXT NOT NULL,
	code TEXT,
	name TEXT,
	description TEXT,
	predicate TEXT NOT NULL,
	"Formulation_id" TEXT,
	PRIMARY KEY (id),
	FOREIGN KEY(predicate) REFERENCES "Expression" (id),
	FOREIGN KEY("Formulation_id") REFERENCES "Formulation" (id)
);
CREATE INDEX "ix_Constraint_id" ON "Constraint" (id);

CREATE TABLE "Value" (
	measure TEXT,
	id TEXT NOT NULL,
	"key" TEXT NOT NULL,
	kind VARCHAR(11) NOT NULL,
	description TEXT,
	"Formulation_id" TEXT,
	"Characteristics_id" INTEGER,
	quantity_id INTEGER,
	flow_id INTEGER,
	content_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(measure) REFERENCES "Measure" (id),
	FOREIGN KEY("Formulation_id") REFERENCES "Formulation" (id),
	FOREIGN KEY("Characteristics_id") REFERENCES "Characteristics" (id),
	FOREIGN KEY(quantity_id) REFERENCES "Quantity" (id),
	FOREIGN KEY(flow_id) REFERENCES "Flow" (id),
	FOREIGN KEY(content_id) REFERENCES "PropertyContent" (id)
);
CREATE INDEX "ix_Value_id" ON "Value" (id);

CREATE TABLE "Movement" (
	id TEXT NOT NULL,
	"key" TEXT,
	date DATE,
	magnitude NUMERIC,
	"Flow_id" INTEGER,
	period_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY("Flow_id") REFERENCES "Flow" (id),
	FOREIGN KEY(period_id) REFERENCES "Period" (id)
);
CREATE INDEX "ix_Movement_id" ON "Movement" (id);

CREATE TABLE "RandomStream" (
	id INTEGER NOT NULL,
	name TEXT NOT NULL,
	identifier TEXT NOT NULL,
	"ScenarioRealization_id" TEXT,
	PRIMARY KEY (id),
	FOREIGN KEY("ScenarioRealization_id") REFERENCES "ScenarioRealization" (id)
);
CREATE INDEX "ix_RandomStream_id" ON "RandomStream" (id);

CREATE TABLE "LibraryVersion" (
	id INTEGER NOT NULL,
	name TEXT NOT NULL,
	version TEXT NOT NULL,
	"CalculationProvenance_id" INTEGER,
	"ScenarioRealization_id" TEXT,
	PRIMARY KEY (id),
	FOREIGN KEY("CalculationProvenance_id") REFERENCES "CalculationProvenance" (id),
	FOREIGN KEY("ScenarioRealization_id") REFERENCES "ScenarioRealization" (id)
);
CREATE INDEX "ix_LibraryVersion_id" ON "LibraryVersion" (id);

CREATE TABLE "ObservationAvailability" (
	id INTEGER NOT NULL,
	available_at DATE NOT NULL,
	"ScenarioRealization_id" TEXT,
	target_id INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY("ScenarioRealization_id") REFERENCES "ScenarioRealization" (id),
	FOREIGN KEY(target_id) REFERENCES "Reference" (id)
);
CREATE INDEX "ix_ObservationAvailability_id" ON "ObservationAvailability" (id);

CREATE TABLE "Location" (
	id INTEGER NOT NULL,
	source TEXT NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(source) REFERENCES "Source" (id)
);
CREATE INDEX "ix_Location_id" ON "Location" (id);

CREATE TABLE "Reconciliation" (
	id INTEGER NOT NULL,
	selected TEXT NOT NULL,
	status VARCHAR(11) NOT NULL,
	method_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(selected) REFERENCES "Claim" (id),
	FOREIGN KEY(method_id) REFERENCES "Method" (id)
);
CREATE INDEX "ix_Reconciliation_id" ON "Reconciliation" (id);

CREATE TABLE "Measure_tags" (
	"Measure_id" TEXT,
	tags TEXT,
	PRIMARY KEY ("Measure_id", tags),
	FOREIGN KEY("Measure_id") REFERENCES "Measure" (id)
);
CREATE INDEX "ix_Measure_tags_tags" ON "Measure_tags" (tags);
CREATE INDEX "ix_Measure_tags_Measure_id" ON "Measure_tags" ("Measure_id");

CREATE TABLE "Claim_sources" (
	"Claim_id" TEXT,
	sources_id INTEGER,
	PRIMARY KEY ("Claim_id", sources_id),
	FOREIGN KEY("Claim_id") REFERENCES "Claim" (id),
	FOREIGN KEY(sources_id) REFERENCES "Content" (id)
);
CREATE INDEX "ix_Claim_sources_Claim_id" ON "Claim_sources" ("Claim_id");
CREATE INDEX "ix_Claim_sources_sources_id" ON "Claim_sources" (sources_id);

CREATE TABLE "Function" (
	id TEXT NOT NULL,
	code TEXT NOT NULL,
	name TEXT NOT NULL,
	version TEXT NOT NULL,
	semantics TEXT NOT NULL,
	unit_rule TEXT NOT NULL,
	empty_collection VARCHAR(5),
	"Definitions_id" INTEGER,
	result_id INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY("Definitions_id") REFERENCES "Definitions" (id),
	FOREIGN KEY(result_id) REFERENCES "Domain" (id)
);
CREATE INDEX "ix_Function_id" ON "Function" (id);

CREATE TABLE "Assembly" (
	classification TEXT,
	id TEXT NOT NULL,
	code TEXT,
	name TEXT,
	"System_id" INTEGER,
	characteristics_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(classification) REFERENCES "Classification" (id),
	FOREIGN KEY("System_id") REFERENCES "System" (id),
	FOREIGN KEY(characteristics_id) REFERENCES "Characteristics" (id)
);
CREATE INDEX "ix_Assembly_id" ON "Assembly" (id);

CREATE TABLE "Filter" (
	id INTEGER NOT NULL,
	classification TEXT,
	PRIMARY KEY (id),
	FOREIGN KEY(classification) REFERENCES "Classification" (id)
);
CREATE INDEX "ix_Filter_id" ON "Filter" (id);

CREATE TABLE "Binding" (
	id INTEGER NOT NULL,
	name TEXT NOT NULL,
	value TEXT NOT NULL,
	"Formulation_id" TEXT,
	"ScenarioRealization_id" TEXT,
	PRIMARY KEY (id),
	FOREIGN KEY(value) REFERENCES "Value" (id),
	FOREIGN KEY("Formulation_id") REFERENCES "Formulation" (id),
	FOREIGN KEY("ScenarioRealization_id") REFERENCES "ScenarioRealization" (id)
);
CREATE INDEX "ix_Binding_id" ON "Binding" (id);

CREATE TABLE "Entity" (
	classification TEXT,
	id TEXT NOT NULL,
	code TEXT,
	name TEXT,
	"System_id" INTEGER,
	characteristics_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(classification) REFERENCES "Classification" (id),
	FOREIGN KEY("System_id") REFERENCES "System" (id),
	FOREIGN KEY(characteristics_id) REFERENCES "Characteristics" (id)
);
CREATE INDEX "ix_Entity_id" ON "Entity" (id);

CREATE TABLE "Entry" (
	"key" TEXT NOT NULL,
	value TEXT NOT NULL,
	"Location_id" INTEGER,
	PRIMARY KEY ("key", value, "Location_id"),
	FOREIGN KEY("Location_id") REFERENCES "Location" (id)
);
CREATE INDEX "ix_Entry_Location_id" ON "Entry" ("Location_id");
CREATE INDEX "ix_Entry_key" ON "Entry" ("key");
CREATE INDEX "ix_Entry_value" ON "Entry" (value);

CREATE TABLE "Fact" (
	id INTEGER NOT NULL,
	"Provenance_id" INTEGER,
	target_id INTEGER NOT NULL,
	reconciliation_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY("Provenance_id") REFERENCES "Provenance" (id),
	FOREIGN KEY(target_id) REFERENCES "Content" (id),
	FOREIGN KEY(reconciliation_id) REFERENCES "Reconciliation" (id)
);
CREATE INDEX "ix_Fact_id" ON "Fact" (id);

CREATE TABLE "Label_classifications" (
	"Label_id" TEXT,
	classifications_id TEXT,
	PRIMARY KEY ("Label_id", classifications_id),
	FOREIGN KEY("Label_id") REFERENCES "Label" (id),
	FOREIGN KEY(classifications_id) REFERENCES "Classification" (id)
);
CREATE INDEX "ix_Label_classifications_classifications_id" ON "Label_classifications" (classifications_id);
CREATE INDEX "ix_Label_classifications_Label_id" ON "Label_classifications" ("Label_id");

CREATE TABLE "Movement_claims" (
	"Movement_id" TEXT,
	claims TEXT,
	PRIMARY KEY ("Movement_id", claims),
	FOREIGN KEY("Movement_id") REFERENCES "Movement" (id)
);
CREATE INDEX "ix_Movement_claims_Movement_id" ON "Movement_claims" ("Movement_id");
CREATE INDEX "ix_Movement_claims_claims" ON "Movement_claims" (claims);

CREATE TABLE "Parameter" (
	id INTEGER NOT NULL,
	name TEXT NOT NULL,
	kind VARCHAR(19) NOT NULL,
	required BOOLEAN NOT NULL,
	"Function_id" TEXT,
	domain_id INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY("Function_id") REFERENCES "Function" (id),
	FOREIGN KEY(domain_id) REFERENCES "Domain" (id)
);
CREATE INDEX "ix_Parameter_id" ON "Parameter" (id);

CREATE TABLE "Criterion" (
	id INTEGER NOT NULL,
	"key" TEXT NOT NULL,
	classification TEXT NOT NULL,
	"Filter_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(classification) REFERENCES "Classification" (id),
	FOREIGN KEY("Filter_id") REFERENCES "Filter" (id)
);
CREATE INDEX "ix_Criterion_id" ON "Criterion" (id);

CREATE TABLE "Query" (
	id INTEGER NOT NULL,
	starting_at TEXT NOT NULL,
	duplicates VARCHAR(8) NOT NULL,
	filter_id INTEGER,
	projection_id INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(starting_at) REFERENCES "Entity" (id),
	FOREIGN KEY(filter_id) REFERENCES "Filter" (id),
	FOREIGN KEY(projection_id) REFERENCES "Projection" (id)
);
CREATE INDEX "ix_Query_id" ON "Query" (id);

CREATE TABLE "Call" (
	id INTEGER NOT NULL,
	function TEXT NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(function) REFERENCES "Function" (id)
);
CREATE INDEX "ix_Call_id" ON "Call" (id);

CREATE TABLE "Relationship" (
	classification TEXT NOT NULL,
	id TEXT NOT NULL,
	source TEXT NOT NULL,
	target TEXT NOT NULL,
	"System_id" INTEGER,
	characteristics_id INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(classification) REFERENCES "Classification" (id),
	FOREIGN KEY(source) REFERENCES "Entity" (id),
	FOREIGN KEY(target) REFERENCES "Entity" (id),
	FOREIGN KEY("System_id") REFERENCES "System" (id),
	FOREIGN KEY(characteristics_id) REFERENCES "Characteristics" (id)
);
CREATE INDEX "ix_Relationship_id" ON "Relationship" (id);

CREATE TABLE "Assembly_entities" (
	"Assembly_id" TEXT,
	entities_id TEXT,
	PRIMARY KEY ("Assembly_id", entities_id),
	FOREIGN KEY("Assembly_id") REFERENCES "Assembly" (id),
	FOREIGN KEY(entities_id) REFERENCES "Entity" (id)
);
CREATE INDEX "ix_Assembly_entities_entities_id" ON "Assembly_entities" (entities_id);
CREATE INDEX "ix_Assembly_entities_Assembly_id" ON "Assembly_entities" ("Assembly_id");

CREATE TABLE "Fact_claims" (
	"Fact_id" INTEGER,
	claims_id TEXT NOT NULL,
	PRIMARY KEY ("Fact_id", claims_id),
	FOREIGN KEY("Fact_id") REFERENCES "Fact" (id),
	FOREIGN KEY(claims_id) REFERENCES "Claim" (id)
);
CREATE INDEX "ix_Fact_claims_Fact_id" ON "Fact_claims" ("Fact_id");
CREATE INDEX "ix_Fact_claims_claims_id" ON "Fact_claims" (claims_id);

CREATE TABLE "Traversal" (
	id INTEGER NOT NULL,
	kind VARCHAR(12) NOT NULL,
	depth VARCHAR(10) NOT NULL,
	classification TEXT,
	direction VARCHAR(8),
	"Query_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(classification) REFERENCES "Classification" (id),
	FOREIGN KEY("Query_id") REFERENCES "Query" (id)
);
CREATE INDEX "ix_Traversal_id" ON "Traversal" (id);

CREATE TABLE "Argument" (
	id INTEGER NOT NULL,
	name TEXT NOT NULL,
	"Call_id" INTEGER,
	expression_id TEXT NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY("Call_id") REFERENCES "Call" (id),
	FOREIGN KEY(expression_id) REFERENCES "Expression" (id)
);
CREATE INDEX "ix_Argument_id" ON "Argument" (id);

CREATE TABLE "Assembly_relationships" (
	"Assembly_id" TEXT,
	relationships_id TEXT,
	PRIMARY KEY ("Assembly_id", relationships_id),
	FOREIGN KEY("Assembly_id") REFERENCES "Assembly" (id),
	FOREIGN KEY(relationships_id) REFERENCES "Relationship" (id)
);
CREATE INDEX "ix_Assembly_relationships_Assembly_id" ON "Assembly_relationships" ("Assembly_id");
CREATE INDEX "ix_Assembly_relationships_relationships_id" ON "Assembly_relationships" (relationships_id);
