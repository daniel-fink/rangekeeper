# Expression, Function, Query, and Constraint contract

This guide specifies representations and meaning. Structural and bounded semantic
checks enforce this contract. The [executor](execution.md) implements the
documented affine subset; representation alone does not promise execution support.

Use `rangekeeper.model.expression.authoring` for passive literal, reference and
operator constructors. `rangekeeper.model.formulation` owns equation builders;
these builders return declarations and do not read recorded amounts or solve them.

## Composition and identity

An Expression is passive mathematical syntax. Each node has a stable UUID and
exactly one content variant. Nested nodes retain their own identities. References
identify Values within the applicable Model or composed Specification scope, independently of display
names and recorded amounts. Fixed and unknown roles belong to a Specification.
`ExpressionKind` distinguishes syntax forms and `Operator` names their
operators. Helper records use `Call`, `Parameter`, `Filter`, `Criterion`, and
`Projection`; their fields refer to the relevant classes and categorical enums.

| Form | Serialized kind and content |
| --- | --- |
| Numerical literal | `quantity`: embedded Quantity with magnitude and explicit units |
| Boolean literal | `boolean`: true or false |
| Value reference | `reference`: target Reference (Value or Movement UUID) |
| Unary operation | `unary`: operator and one `operand` |
| Binary operation | `binary`: operator and two ordered `operands` |
| Function call | `call`: Function UUID, positional arguments, named arguments |
| Member or index selection | `selection`: base Expression and a typed selector |
| Graph query | `query`: scope, traversal, filter, projection, duplicate handling |

Arity follows the operation form. Negation and Boolean negation are unary;
arithmetic, comparisons, conjunction, and disjunction are binary. Longer operator
chains nest. Functions have their own signatures; aggregations accept collections
rather than an implicit variable number of scalar arguments.

Numerical literals embed the shared `Quantity` type from `measure.yaml`. Their
units are explicit, including `dimensionless` for unitless content. They do not
carry a Measure reference. A Measure defines domain meaning and canonical units;
a Quantity supplies magnitude and units. The containing Expression owns identity.
Zero and false are meaningful content. Missing or
null literal content is invalid. A reference to an unresolved Value is valid.
Optional list fields may be absent, null, or empty to denote no entries; canonical codecs preserve those distinctions. Required operation content cannot be null or empty.

Date and string literal nodes are deferred until a concrete operation requires
them. Policy guards or action arguments may provide such requirements; their
comparison, typing, and execution semantics will need to be specified together.
This does not remove date or string result domains: a reference, selection, or call
can return such content under its declared contract. For example, selecting a
Span endpoint can return a date without a date literal node. Selector names and
characteristic keys are schema fields, not string literal expressions.

Comparisons produce Boolean expressions. A Constraint asserts that one must
hold. Equality is not assignment. Boolean operators require Booleans, without
numeric coercion. Conjunction and disjunction short-circuit during evaluation;
both operands remain in symbolic dependency analysis and must be well typed.

## Functions and domains

`function.yaml` describes Function identity, code, version, signature, result
domain, mathematical semantics, and unit rules. Function codes are unique within
the Model's Function collection. A call uses the UUID; the Model revision pins
the exact definition and version.

Positional arguments bind in signature order. Named arguments bind by name.
Duplicate bindings, unknown names, excess positional arguments, and absent
required parameters are errors. Optional arguments have explicitly documented
omission semantics; omission is not an unresolved argument. Named-only arguments
follow positional arguments, and optional positional arguments follow required
ones. Parameter names must be unique.

Functions are pure: no Model mutation or ambient session reads. All model inputs
are explicit arguments. The contract does not store Python import paths or grant
access to arbitrary runtime methods. Implementations and backend support belong
to a separate registry/compiler and execution record.

`Domain` describes permitted argument or result content. Its `kind` distinguishes
scalar, structured, and collection categories. `Parameter.domain` and
`Function.result` each contain a Domain; `Parameter.kind` separately determines
whether an argument can be supplied positionally or only by name.
`quantity` accepts numerical content with optional compatible-unit requirements;
`number` requires dimensionless content. `measurement` additionally requires
measurement meaning, optionally an exact Measure. A bare Quantity does not gain
that meaning solely by having compatible units. Arithmetic derives quantities;
it does not automatically assign a Measure to an intermediate result.
Collections specify one recursive `item_domain` and may require a set, bag, or sequence.
Units and function semantics are explicit prose contracts at this stage, not
executable unit formulas. A structured Domain describes a Function contract; it does not itself define
serialized Value content or executable members. Canonical Flow payloads exist;
general Stream and Account member contracts remain separate requirements.

Member selection reads a declared public member of the base content. Index selection
uses the content's index convention. Sequences use zero-based nonnegative integer
indices; temporal indices need the temporal content contract. Sets and bags have no
positional indices. Missing members and out-of-range indices are errors. If an
Entity characteristic already has a Value UUID, reference it directly.

## Analysis and uncertainty

`model.scope` owns UUID-keyed declaration lookup. `model.formulation` collects
owner-local declarations with original paths. `model.expression.validation`
checks signatures, binds arguments and analyzes each expression once; its immutable
ExpressionAnalysis contains node, domain and path maps. Constraints and objectives
consume those results. `domains.py` contains local rules; numerical evaluation and
policy truth remain separate.

Domain comparison is directional and returns compatible, incompatible or unproven.
Missing units do not prove dimensionless content. A required Function argument,
predicate or objective cannot rely on an unproven domain. Passive reporting queries
may remain unproven, with normal structural and reference checks still applied.

Static query inference filters the permitted Value declaration inventory by key
and Measure without following graph edges. A nonempty homogeneous candidate set
can establish an item domain. Measurement, property and Flow candidates retain
their different kinds. Mixed or empty candidates do not prove a measurement type;
a Measure filter alone is insufficient because Flows also carry Measures. The
runtime result count and membership remain unknown to static validation.

## Queries and aggregations

A Query starts at an Entity UUID in the containing Model revision. It cannot
read a live CRM or external database. Apply these stages in order:

1. Traverse each listed step, in sequence. With no steps, start with the root.
2. Filter the resulting Entities using fixed classification and Label metadata.
3. Project Entity identities or matching Value identities.
4. Apply duplicate handling to the projected UUIDs.

Relationship steps identify an exact Relationship `classification` and direction.
Membership steps follow `Assembly.entities`. Neither implies the other.
Direct traversal follows one edge. Transitive traversal follows one or more
edges along simple paths: an Entity cannot repeat within a path for that step.
The starting Entity is excluded from that step's results. Different paths can
reach the same Entity; the duplicate policy handles the resulting occurrences.

Filters match exact Classifications; there is no implicit taxonomy expansion.
Label filters require the given owner-local key and an included Classification.
Filters are conjunctive and act after traversal, so a nonmatching intermediate
Entity does not prevent traversal to a matching descendant. Unknown numerical
values cannot determine query membership in this revision.

Value projection selects by either an owner-local key or an exact Measure UUID.
`cardinality: one` rejects multiple matches per Entity; `many` retains them.
No match follows the explicit `missing: error` or `omit` policy. An unresolved
Value is still a match; absence of its Quantity is never a reason to omit it.

`duplicates: distinct` produces a set of UUIDs. `preserve` produces a bag with
one occurrence per traversal path and projected match. Neither promises order.
A query matching no Entities produces an empty collection, independently of
missing-characteristic handling.

Aggregation is a Function call over that collection. Sum preserves unknown
members as symbols rather than substituting stored amounts. If any collection
argument is empty, the Function's `empty_collection` behaviour applies: reject
it, or return zero when a numerical result and its units can be established.
Unresolved members are neither dropped nor interpreted as zero. Multiplicity
affects the result when the Query deliberately retains it.

For example, the [graph aggregation fixture](../../examples/schema/query-aggregation.yaml)
expresses the sum of apartment rent within Building A. Apartment A is reachable
directly and via a floor. `distinct` retains its rent Value once; Workspace A
is excluded. All rent amounts are unresolved. The expected symbolic sum contains
Apartment A's and Apartment B's rent, not a numerical total. A separate Assembly
membership query demonstrates counting, without inferring containment.

## Constraints

`constraint.yaml` defines an identified assertion with a required Expression UUID
in `predicate`. Optional `code`, `name`, and `description` identify and explain the
requirement. A code is unique within its Constraint collection when supplied.
The referenced Expression can be a root or nested node; multiple Constraints can
reference the same node. The two valuation Constraints assert the existing NOI
and capitalization equations without duplicating their Expression trees.

An eligible predicate has a Boolean result domain. This is a semantic requirement,
not a restriction to one `Expression.kind`: comparisons, logical expressions, and
Boolean-returning calls qualify. Resolving an Expression UUID and establishing its
domain are separate from checking its serialized reference shape. A numerical
predicate is invalid; a Boolean `false` predicate is valid syntax but cannot satisfy
an assertion requiring it to be true.

All Constraints in Model and Specification Formulations are imposed together. Specification
additions cannot override or deactivate Model requirements. Fixed
and unknown Values, numerical settings, and Run diagnostics remain separate from
the Constraint. Equality does not specify an assignment direction. Constraint
validation neither evaluates its predicate nor proves feasibility or backend support.

## Validation and execution boundary

The schemas and checks establish:

- Variant structure, operator form, typed UUID syntax, and nested operand order.
- Function signatures, collection domains, traversal and projection options.
- Generated Python round trips, including false, zero, and date-valued selections.
- Rejection of deferred date and string literal nodes.
- Bounded reference, argument-binding, coarse domain, and identity checks.
- Constraint predicate references and Boolean result domains, including nested
  and reused predicates, Boolean calls, and literal false predicates.

The [structured-expression fixture](../../examples/schema/function-expressions.yaml) includes
Flow total, annual IRR, a Span endpoint, Account transactions, and indexed balances.
Its `input_domains` entries describe fixture-only domains, not serialized Value
records. The checker supplies illustrative member domains for these examples.
Canonical Flow Values already have a serialized payload. These fixtures do not
establish general executable member or Function contracts for Flow, Stream or
Account content.

The checker does not evaluate Constraint satisfaction, traverse the graph, establish
query result cardinalities, validate dimensions, find IRR roots, or solve equations.
Function unit rules and mathematical behaviour still require implementations and
independent tests.
At signature boundaries, the bounded checker recognizes identical unit spellings
and the explicit `dimensionless` convention; it conservatively rejects other unit
matches. This is not a complete compatibility or conversion algorithm. The separate
graph fixture exercises compatible-unit conversion through the existing runtime.
Generated constructors enforce structure. Owning validators establish references,
content rules and complete mathematical roles before execution. A function being evaluable does not establish that a backend
can solve through it for the unknowns selected by a Specification.

Readable formula text can be parsed into these records and retained as authoring
or provenance material. It is not a second independently editable mathematical
authority. Loading any of these records does not execute code.

## Subsequent work

The scalar execution subset and its independent acceptance checks are described
in [scalar execution](execution.md). General symbolic graph-query execution
and aggregation with symbolic members require further adapters. Flow Value
payloads already exist. Define the missing structured Function/member
contracts and backend support before claiming general Flow/Account expression
execution.
Conditionals, slicing, grouping, unknown-dependent query membership, unrestricted
graph query languages, and general-purpose code execution are outside this draft.

## Passive Flow and hierarchy builders

Builders use mathematical roles, not permanent calculation direction. A
Specification can fix a total and solve a summand. The signatures use:

| Builder | Quantity parameters |
| --- | --- |
| `expression.sum` | `summands` |
| `flow.sum` | `summands`, `total` |
| `flow.scale` | `multiplicand`, `multiplier`, `product` |
| `flow.accumulate` | `increments`, `initial`, `accumulation` |
| `growth.compound` | `initial`, `rate`, `series` |
| `growth.linear` | `initial`, `increment`, `series` |
| `financial.discount` | `series`, `rate`, `discounted` |
| `financial.pv` | `sequence`, `value` |
| `account.interest` | `principal`, `rate`, `interest` |
| `account.schedule` | `transactions`, `initial`, `rate`, `balances`, `interest` |
| `flow.aligned` | `members`, `reference` |
| `flow.resample` | `sequence`, `resampled` |

Binary expressions retain `left` and `right`. `flow.sum` accepts ordered Value IDs
or an original `Stream.from_values` selection from the exact Model revision.
Structural trims are supported; calculated Stream transformations require declared
intermediate Flow Values and relationships. `flow.aligned` uses the reference
Flow's order without reading its amounts.

`flow.resample` uses the resampled Flow's bounded periods. It supports SUM, MEAN
with fixed observation/day weights, and FIRST/LAST. All declared symbols participate,
including unknown amounts. SKIP and PROPAGATE policies are rejected for passive
authoring. Explicit ZERO permits an empty target group; it never replaces an unknown
symbol. MIN/MAX require solver capabilities outside the current affine slice.

`financial.pv` sums an already discounted sequence. Its saved operation name remains
`present_value`, so existing declaration identity fixtures do not change. Other
keyword renames also preserve expression order, binding order and declaration IDs.

There is no dedicated `financial.reversion` helper. Compose a capitalisation
relationship with ordinary expressions and an explicit Movement mapping:

```python
from rangekeeper.model.expression.authoring import equal, divide, reference
from rangekeeper.model.formulation import declare
from rangekeeper.model import Reference

capitalisation = declare(
    relation_id,
    "capitalisation",
    [(str(value_movement.id), equal(
        reference(Reference(target=value_movement.id)),
        divide(reference(Reference(target=income_movement.id)), reference(rate)),
    ))],
    [value_id, income_id, rate_value_id],
)
```

Select income timing explicitly, such as the following period's income supporting
a value at this period's end. Declare any sale event separately. With an explicit
nonzero-rate domain, a product equation can permit solving the rate when the value
is fixed. Do not rewrite saved quotient equations; an unknown divisor is outside
the current executor's supported slice.

`Reduction.flows(...).formulate(hierarchy, id=..., aggregates=...)` declares SUM
relationships from the same original contributors used by numerical reduction.
Aggregate Flow Values must already exist on their named entities. Use explicit
intermediate Flow equations when those intermediate quantities need individual
roles. See [system reductions](system.md#flow-hierarchy-reduction) and the
[executable example](../../examples/rangekeeper_examples/flux.py).
