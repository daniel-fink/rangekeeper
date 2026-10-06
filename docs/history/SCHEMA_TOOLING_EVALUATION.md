# Schema tooling for the proposed RK object model

> Historical design or implementation record. Names, commands and status below describe that checkpoint. Use the [current documentation](../README.md) for supported APIs.

**Historical research, with current decision:** Daniel selected LinkML on
2026-10-02; see the [decision record](../research/current-schema-comparison/DECISION.md)
and [library architecture](../LIBRARY_ARCHITECTURE.md). Recommendations and open
choices below describe the 2026-09-24 study, not the current work queue. Its
measured observations remain unchanged.

Research date: 2026-09-24. Status: recommendation for discussion, not an adopted
schema or a change to the RK runtime.

## Recommendation

**LinkML remains my preferred tool for the next, documentation-first object-model
specification. It is not established as the best foundation for the entire RK
modelling language.** The earlier recommendation was too broad if it implied
that generating several representations would preserve all their semantics.

The strongest alternatives are CUE for executable document invariants, TypeSpec
for a concise typed interchange contract, and direct Pydantic for a Python-first
prototype. Protobuf with Buf and Protovalidate deserves more consideration than
bare Protobuf. Language workbenches and SysML v2/KerML address parts of the
longer-term ambition that a record schema does not.

For this project I would use a small LinkML profile to describe records,
identities, reference ranges, and documentation; generate a pinned JSON Schema
for structural validation; and implement RK reference/type/unit checks alongside
the compiler. I would not add CUE, CEL, or a second independently maintained
schema source at the same time. This choice is justified by the immediate need
to review a domain object model, not by a need to adopt RDF or an ontology stack.

Confidence is moderate. The local probes below establish useful capabilities and
specific differences, not an end-to-end victory for any framework. In particular,
generated documentation and generated Python validators need acceptance checks.

## 1. What we are choosing

The agreed architecture is `Model₀ + Specification → Run → Model₁`. A Model is an
immutable graph of declarations, expressions, and relations, including resolution
properties. A recorded resolution does not become a governing equation or a fixed
binding in the next Specification. Specification-specific policies can generate definitions;
generated content requires explicit validation and execution.

There are several distinct contracts:

| Layer | Example question | Suitable responsibility |
| --- | --- | --- |
| Record structure | Does a reference have a target ID? Is an operator tag valid? | Schema and structural validator |
| Graph meaning | Does that ID resolve, in the pinned scope, to a value declaration? | Reference resolver and semantic validator |
| Expression meaning | Is the operand numeric? Are units compatible? Is this a predicate? | RK type system and operator specification |
| Specification meaning | Which quantities are fixed or unknown? What information can a policy observe? | Specification formation and capability checks |
| Execution | Can this system be solved, with which status and tolerances? | Compiler, solver, and policy runtime |
| Persistence | Which revision produced a resolution? What survives export/import? | Snapshot, provenance, and migration contracts |

A schema may describe all these records without implementing their behaviour.
Likewise, a validation expression that checks a completed document is not the same
thing as an equation that a solver must satisfy for unknown quantities.

For example, `capital_value * capitalization_rate == NOI` can be stored as a
Boolean expression, required by a constraint, evaluated against known values, or
lowered to an equation for inverse solving. Those are different uses of the same
symbolic structure. Selecting a schema language does not select that lowering.

The current requirements favour readable files, explicit identities and
references, recursive expression variants, clear missing-value semantics,
reviewable documentation, and Python/TypeScript interoperability. They do not yet
require an RDF database, RPC protocol, or visual language workbench. Importing a
project as a new CRM project removes merge reconciliation, but not schema
migrations, reference preservation, or execution-version tracking.

## 2. What was actually tested

Sources, fixtures, results, and reproduction instructions are retained in
[the research bundle](../research/schema-tooling/README.md). These are synthetic
schema probes, not the proposed RK schema and not tests of the numerical engine.

Tested on Python 3.11.16 with LinkML/linkml-runtime 1.11.1, Pydantic 2.13.5,
jsonschema 4.26.0, CUE 0.17.1, and TypeSpec compiler/JSON Schema emitter 1.16.0.
Installations were confined to a temporary environment; project dependencies
were not changed.

The same 20 JSON fixtures were applied to a deliberately small model containing
entity/value declarations, numeric/Boolean literals, references, comparisons,
and asserted predicates. Two fixtures were valid: the baseline and an empty
constraint collection. Thirteen had structural defects. Five had valid shapes
but invalid graph meaning: a dangling reference, a target of the wrong kind,
a numeric expression used as a constraint predicate, a unit mismatch, or a
duplicate declaration ID.

### Structural validation

All four generated JSON Schema routes—LinkML, Pydantic, CUE, and TypeSpec—agreed
on the 20 fixtures. They accepted the two valid documents and five semantic
errors, and rejected the thirteen structural errors. The comparison used closed
records and explicit tagged variants. It was not a comparison of unconfigured
defaults.

This demonstrates that all four can represent this small interchange structure.
It does not demonstrate identical handling of every numeric value, recursive
reference pattern, schema feature, or future extension.

### Generated Python is not automatically equivalent to generated JSON Schema

LinkML-generated Pydantic models accepted numeric strings and Booleans as numbers
under the tested default validation mode. Strict validation fixed that coercion,
but the generated models still supplied missing type tags and accepted a base
`Expression` record that the generated JSON Schema rejected.

These are observations about the tested generator/profile, not a claim that
LinkML cannot enforce the desired contract. A structural validation boundary,
generator configuration/customization, or a different schema formulation can
address differences. The implication is that “generated from one source” does
not establish behavioural equivalence. LinkML's own
[generator feature dashboard](https://linkml.io/linkml/generators/dashboard.html)
explicitly distinguishes support across targets.

### Graph checks need an implementation

An explicitly written Python semantic validator rejected all five semantic errors.
An explicitly written CUE semantic schema did so too. The unit check in this
probe only compared unit strings; it did not implement dimensional analysis or
conversion. The identity check was local to each declaration/expression collection.

Exporting the Python semantic validator or CUE semantic schema to JSON Schema
did not preserve these graph checks. The exported validators again accepted the
five semantic errors. A schema export therefore cannot be assumed to carry
custom validation logic. JSON Schema's `$ref` references another schema; it is
not an instance-level foreign-key constraint.
[JSON Schema reference semantics](https://json-schema.org/understanding-json-schema/structuring)

### CUE recursion and inverse solving

CUE and TypeSpec both handled a separate recursive, nested expression-tree
example. Rejecting CUE on the grounds that it cannot describe recursive
expressions would have been wrong.

CUE did not infer `x = 5` from this separate probe:

```cue
x: number
y: x * 2
y: 10
```

Export failed because `x` remained incomplete. CUE unification can resolve some
constraints, including direct value equalities; this result is specifically
evidence against treating general arithmetic expressions as an inverse solver.

### Documentation also needs verification

LinkML generated class Markdown and Mermaid diagrams. For a required collection,
the documentation displayed `1..*` while the JSON Schema accepted an empty list.
Adding `minimum_cardinality: 0` made the JSON Schema explicit but left the
displayed cardinality at `1..*`; specifying `1` rejected the empty list. In the
tested top-level diagram invocation, the index contained a Mermaid block with
`None`, although individual class diagrams were generated.

These are narrow, reproducible documentation discrepancies in this release/profile.
They matter because documentation fidelity is a reason to choose LinkML. They do
not justify treating all LinkML documentation as incorrect. Before publishing
our schema reference, cardinalities and diagrams must be checked against examples.

### What remains untested

No complete Model–Specification–Run serialization, immutable resolution handling,
Python-to-TypeScript round trip, solver compilation, database mapping, migration,
large graph performance, source-location diagnostics, or policy generation was
tested. Protobuf/CEL, SHACL, language workbenches, and SysML were assessed from
primary documentation, not executed. No framework-wide pass rate is claimed.

## 3. The serious alternatives

### LinkML: a domain object-model description

LinkML has an unusually direct vocabulary for classes, slots, identifiers,
reference ranges, inheritance, descriptions, mappings, and generated reference
documentation. That is a good match for discussing what `Declaration`, `Model`,
and `Run` mean before building the engine. References can be described by their
logical class while serialized as IDs. Linked-data mappings are available without
making an RDF store mandatory.
[LinkML overview](https://linkml.io/linkml/),
[inlining and references](https://linkml.io/linkml/schemas/inlining.html)

The important qualification is that a declared reference range does not guarantee
that every generated validator resolves and checks its target. LinkML documents
that ID references lose class information in JSON Schema, and its default
validation workflow uses generated JSON Schema. Extra checks or validation
plugins are therefore material, not an optional refinement.
[JSON Schema generator](https://linkml.io/linkml/generators/json-schema.html),
[validation architecture](https://linkml.io/linkml/data/validating-data.html)

Its expression language is a separate evaluation/inference facility; adopting
LinkML need not adopt that expression syntax for RK. RK needs its own specified
operator meanings and solver translation.
[LinkML expressions](https://linkml.io/linkml/schemas/expression-language.html)

**Choose it when:** the first deliverable is a reviewable semantic vocabulary with
field-level documentation and several derived structural artifacts.

**Cost for RK:** a supported feature profile, generator version pinning,
documentation checks, and semantic validation beyond generated classes.

### CUE: the strongest alternative for declarative validation

CUE is more capable than “a configuration format.” It composes constraints and
can express rules involving several fields or collections in the same document.
The probe demonstrated reference-kind, predicate-kind, uniqueness, and simple
unit checks without a separate Python implementation.
[CUE validation](https://cuelang.org/docs/concept/how-cue-enables-data-validation/)

Its treatment of types and values within one constraint system does not force us
to conflate model definitions and resolutions. An unresolved RK declaration can
be represented by a completely concrete data record; it need not be an incomplete
CUE value. Separate Model and Run schemas remain possible.
[The logic of CUE](https://cuelang.org/docs/concept/the-logic-of-cue/)

The portability qualification is substantial: the official CLI documentation
marks JSON Schema output experimental, and our exported schema did not retain
the whole-document checks. Choosing CUE for those checks means invoking CUE as
part of authoritative validation, or deliberately reimplementing them. It also
adds a Go/CLI integration boundary to the current Python/TypeScript environment.
[CUE file types](https://cuelang.org/docs/reference/command/cue-help-filetypes/),
[CUE integrations](https://cuelang.org/docs/integration/)

**Choose it when:** expressing and executing graph/document invariants in a
declarative language is more important than generating a domain reference manual.

**Why not first here:** the mathematical type system and solver lowering still
need RK implementation, while sharing CUE checks through JSON Schema is not
lossless. It could move validation logic into another language without removing
the hardest compiler work. This is a tradeoff, not a claim of incapability.

### TypeSpec: the strongest overlooked typed-schema authoring option

TypeSpec offers concise records, unions, templates, documentation annotations,
and an official JSON Schema emitter. It describes the probe's tagged expression
variants cleanly, including recursive expressions. It is a credible independent
schema source for a Python/TypeScript system, not merely another JSON serializer.
[Models](https://typespec.io/docs/language-basics/models/),
[unions](https://typespec.io/docs/language-basics/unions/),
[JSON Schema emitter](https://typespec.io/docs/emitters/json-schema/reference/emitter/)

Our test enabled `seal-object-schemas`; an emitter's default openness should not
silently become RK's extension policy. TypeSpec's types also do not automatically
give an ID field referential integrity, a declared unit dimensional meaning, or
an equation inverse semantics. Those require conventions, custom tooling, or
runtime checks. Python/TypeScript application code generation and documentation
publication were not tested here.

**Choose it when:** the main artifact is a typed language-independent contract,
especially with many expression variants and a TypeScript-oriented toolchain.

**Why LinkML currently edges it:** domain identifiers, reference ranges, and
semantic documentation are more central to the immediate discussion than service
interfaces. TypeSpec becomes more attractive if the schema evolves primarily as
a compiler's intermediate representation rather than a domain data dictionary.

### Pydantic or Zod: fewer moving parts, with a language owner

A strict Pydantic implementation can describe records, validate data, attach
custom graph checks, and emit JSON Schema. For the first Python solver prototype
it may be the shortest practical route. Tagged unions worked well in the probe.
The tradeoff is making Python the schema-authoring environment and ensuring
browser/server consumers do not mistake the exported shape for every Python rule.
[Pydantic unions](https://pydantic.dev/docs/validation/latest/concepts/unions/),
[strict mode](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/)

Zod provides a corresponding TypeScript-first choice. Some Zod types and
transformations cannot be represented in JSON Schema. Neither route makes arbitrary
language-level validators portable merely by exporting a schema.
[Pydantic JSON Schema](https://pydantic.dev/docs/validation/latest/concepts/json_schema/),
[Zod JSON Schema](https://zod.dev/json-schema)

**Choose it when:** a runtime prototype is the immediate product and one language
can own the contract. Direct JSON Schema plus ordinary runtime code is also a
credible baseline if avoiding another authoring framework matters more than
conciseness. JSON Schema can describe recursive data; it need not describe the
entire mathematical meaning of that data.

### Protobuf + Buf + Protovalidate: more than a binary format

The combination supplies an interface definition language, generated messages,
compatibility checks, and declarative validation using CEL. `oneof` messages can
represent expression variants. Protobuf also has a JSON representation, so
rejecting it simply because users want text files would be mistaken.
[Protobuf language guide](https://protobuf.dev/programming-guides/proto3/),
[Buf breaking-change detection](https://buf.build/docs/breaking/),
[Protovalidate custom rules](https://protovalidate.com/schemas/custom-rules/)

For RK, presence must be explicit: an unknown value must not silently become zero
through scalar defaults. Protobuf's JSON evolution rules differ from binary
compatibility, and JSON does not preserve unknown fields in the same way. A
compatibility checker cannot establish unchanged financial/operator semantics or
perform a domain migration by itself.
[Field presence](https://protobuf.dev/programming-guides/field_presence/),
[ProtoJSON compatibility](https://protobuf.dev/programming-guides/json/)

**Choose it when:** independently deployed services, SDKs, and managed protocol
evolution are the main concern. The current file-first model review and CRM-viewer
workflow give less reason to make that protocol machinery the initial centre.

## 4. Alternatives at a different level

### CEL: an expression-language candidate, not an object-schema replacement

CEL defines a typed expression language and portable AST, with evaluation against
an environment. It is designed to be side-effect-free and terminating. This makes
it relevant for policy guards, eligibility checks, and cross-field validation.
It does not provide our Model/Specification/Run object schema or an algebraic optimizer.
[CEL specification](https://github.com/cel-expr/cel-spec),
[language definition](https://github.com/cel-expr/cel-spec/blob/master/doc/langdef.md)

For example, a CEL-like guard could decide whether conversion is admissible from
currently observed market conditions. It should not itself mutate the project.
The action, generated definitions, validation, and subsequent solve remain
explicit parts of the Run.

An unknown in CEL evaluation is not automatically a solver variable. Partial
evaluation may retain unresolved expressions; finding assignments satisfying
equations requires additional machinery. CEL could supply a parser/frontend for
a deliberately supported RK subset, but that requires checking numeric semantics,
unit support, reference binding, and exact translation of each operator. Its
built-in integer/double choices are not a ready-made money/quantity type system.
[CEL evaluation APIs](https://cel.dev/reference/api-reference)

Even a terminating guard language cannot guarantee that an enclosing policy loop,
host extension, solver, or repeated graph-generation process terminates. Such
bounds belong in RK's execution contract.

### Langium, Xtext, and Ecore/OCL: actual language engineering

These were underrepresented in the earlier comparison. Language workbenches
address grammars, ASTs, name resolution, scope, validation, and editor support.
Langium explicitly supports linking cross-references; Xtext integrates with
Ecore metamodels. Ecore distinguishes ownership/containment from other references,
which is highly relevant to overlapping Assemblies and stable entity identity.
[Langium cross-references](https://langium.org/docs/learn/workflow/resolve_cross_references/),
[Xtext and EMF](https://eclipse.dev/Xtext/documentation/308_emf_integration.html),
[OCL standard](https://www.omg.org/spec/OCL/2.4/About-OCL)

If we next want users to write a real algebraic language with completion and
precise source errors, this family is more directly relevant than adding more
schema generators. It is a larger language/toolchain undertaking. I would first
stabilize the small serialized object model and its operator semantics, then
let a textual frontend compile into it. An AST alone still supplies no solver.

### SysML v2/KerML: a particularly relevant missed precedent

Our ambition overlaps systems modelling: physical composition, properties,
constraints, behaviour, quantities, and alternative configurations. SysML v2 is
therefore a serious precedent, not merely a diagram format. Its published
artifacts include a textual notation, abstract syntax, JSON schema, and libraries
covering quantities/units, geometry, and analysis. KerML provides an underlying
modelling foundation.
[OMG SysML v2 artifacts](https://www.omg.org/spec/SysML/2.0)

The official release project also provides example models and editor/Jupyter
installation material. This demonstrates an established effort toward textual
and graphical access to a common model, close to the user's parallel-interface
ambition.
[SysML v2 reference release](https://github.com/Systems-Modeling/SysML-v2-Release)

I would study its distinctions before inventing a broad RK metamodel. I would not
adopt the complete language without testing a small RK example: the mapping of
Specification-specific solve roles, money/calendar conventions, immutable resolution
snapshots, and policy execution has not been established here. Standardized model
representation is not evidence that the reference tools solve our financial or
stochastic optimization problems. This option was researched, not executed.

### SHACL/JSON-LD, Dhall, and Alloy

SHACL validates RDF graphs; JSON-LD provides a JSON-compatible linked-data
representation. They deserve priority if RDF identifiers, shared ontologies,
SPARQL, or semantic-web interchange become concrete requirements. An RK graph
or a possible PostgreSQL/AGE property graph does not by itself imply RDF semantics.
That mapping is a design choice.
[SHACL](https://www.w3.org/TR/shacl/),
[JSON-LD](https://www.w3.org/TR/json-ld11/)

Dhall is relevant to typed, programmable configuration and reproducible imports,
but it does not remove the need for the RK graph/type/compiler contract. Alloy
is relevant to finding counterexamples to relational invariants and bounded
transition rules; it is not a replacement for financial numerical solving.
[Dhall](https://dhall-lang.org/), [Alloy](https://alloytools.org/about.html)

Smithy is another substantial IDL with traits, model validation, and transformations.
Its service/interface orientation makes it less directly compelling for this
phase than the shortlisted record-schema options. This is a prioritization,
not a claim that it cannot describe the records.
[Smithy specification](https://smithy.io/2.0/spec/index.html),
[model validation](https://smithy.io/2.0/spec/model-validation.html)

## 5. Implications for the RK design

Regardless of framework, the following decisions remain ours:

1. **Identity and reference scope.** Distinguish a persistent entity/declaration
   identity from a Model revision and a record's identity within that revision.
   A reference must resolve deterministically in a pinned scope. Reimporting as a
   new CRM project needs a documented mapping of internal IDs and provenance.
2. **Predicate versus assertion.** A comparison is an expression; requiring it to
   hold is contextual. The schema can use a constraint record or a collection of
   asserted expression references without duplicating expression syntax.
3. **Unknown and resolution states.** Missing, unknown, null, error, partial,
   stale, and numerical zero must not collapse. A previous resolution does not
   set the fixed/unknown role for a later Specification.
4. **Mathematical types.** Units, dimensions, temporal indices, currencies,
   numeric precision, calendars, and stock/flow conventions require semantics.
   A string called `unit` does not provide them.
5. **Ordering.** Division operands, function arguments, cashflow periods, and
   policy decisions have meaningful order. A target representation must preserve
   order explicitly; a generic graph edge set is insufficient.
6. **Permitted cycles.** A cycle of equations can represent a simultaneous solve.
   It must not be rejected simply because an evaluator expects a DAG. Reference
   recursion, containment cycles, and equation cycles need different rules.
7. **Extensions and execution bounds.** Closed core variants should have explicit
   extension points. Operator and policy capabilities need versioned meaning;
   arbitrary executable escape hatches undermine portability and termination.
8. **Versions and migration.** File schema revision, Model revision,
   operator/compiler version, and solver/runtime identity are separate. A change
   can preserve its JSON shape while changing its mathematical answer.

No schema framework automatically makes mappings to Twenty records, a property
graph, RDF, Python runtime objects, and algebraic solver objects lossless.
Specify the intended information preserved by each adapter and test that claim.

## 6. How I would proceed

Use LinkML for the first reviewable schema draft, with a deliberately restricted
and pinned generation profile. Keep the portable Model/Specification/Run records
independent of generated Python object behaviour. A structural validator checks
their shape; the RK semantic compiler owns scope resolution, expression typing,
unit rules, and backend capability checks. These are complementary contracts,
not several independently authored versions of the same schema.

Before treating that draft as an accepted interchange contract:

1. Specify just IDs/revisions/references, entity/value declarations, literal/ref/
   arithmetic/comparison expressions, contextual constraints, bindings,
   resolutions, and minimal Model/Specification/Run records.
2. Encode the already documented forward/inverse valuation example, including
   the second Specification operating on a previously resolved Model.
3. Verify the same structural fixtures in the actual Python and TypeScript
   consumers, then check graph semantics in the authoritative RK validator.
   Test serialization as well as acceptance: defaults and normalization can
   change data even when both validators accept it.
4. Check generated documentation against those fixtures. Explicitly decide
   collection presence/cardinality, extra fields, numeric representation, and
   whether abstract types can appear in serialized data.
5. Implement the scalar solve only after the symbolic and resolution records are
   reviewable. Then progress to simultaneous equations, time, alternatives,
   generated structure, and policies using the existing staged plan.

Switch to CUE if shared declarative document invariants become the primary
deliverable and invoking its validator is acceptable. Prefer TypeSpec if compact
typed-contract authoring and expression variants outweigh LinkML's semantic
catalogue. Prefer Pydantic if we consciously prioritize a Python-owned runtime
prototype. Consider a language workbench when authoring equations as source code
becomes an actual next-stage requirement.

This research supports a bounded LinkML choice for the next document. It does not
support committing RK's equation language, execution engine, or database design
to LinkML.
