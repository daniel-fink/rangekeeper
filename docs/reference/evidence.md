# Source Evidence and table transformations

`rangekeeper.workflow.evidence` keeps source observations, support chains, output
cells and their explanations together. Source Evidence supports interpretation
before a Model exists. It is distinct from finalized solver evidence in a
[Run](run-and-storage.md).

## Source support and canonical provenance

Import `Source`, `Location`, `Method`, `Claim`, `ClaimKind`, `Evidence`, `Issue`,
`Severity`, `tabular`, `validate` and `fingerprint` from
`rangekeeper.workflow.evidence`. `ClaimKind` and `Severity` re-export the generated
enums, but these source Claim/Source/Location/Method objects are transient workflow
types. They can retain native immutable observations; they are not generated Model
records or a persistence format.

A `Source` identifies an evidence edition by UUID, name and checksum, with optional
issued/received dates and author. A `Location` binds that Source to a structured
native reference. A `Method` gives a code, optional version and description.

A sourced Claim requires a Location. A derived Claim requires an upstream Claim
and Method. An asserted Claim requires a Method. `Claim.sourced`, `.derived` and
`.asserted` create these forms. Factories default to random UUIDs: supply explicit,
stable IDs when independently created artifacts must reproduce their identities.
`locations(claim)` traverses support once per Claim and returns distinct Locations.

Within a support graph, a UUID must identify the same canonical Claim/Source object.
A second instance with the same UUID raises `IdentityConflictError`; dependency
cycles are invalid. Composition explicitly converts source support to schema
provenance through `workflow.provenance`, including typed native-value encoding.
Facts bind that evidence to canonical targets. See [workflow](workflow.md) and
[Model](model.md) for publication contracts.

## Container and addressing

`Evidence(name=..., data=..., claims=..., issues=())` is frozen and generic in its
type parameter. Production validation currently accepts the exact
[`Table`](tables.md#row-and-table) type, not subclasses or arbitrary CAD/GIS content.
Other content raises `EvidenceValidationError` with `unsupported_content`.
There is no profile registry or runtime registration mechanism.

`name` describes the dataset; it is not its identity. `claims` maps output addresses
to exactly one terminal Claim per cell. Upstream Claims retain the observations
and interpretation behind that value. `issues` explain missing, invalid,
conflicting or qualified outputs. Container-owned mappings and sequences are
copied and frozen.

| Address | Meaning |
| --- | --- |
| `("rows", "<canonical row UUID>", "area")` | Cell Claim or Issue scope. |
| `("rows", "<canonical row UUID>")` | Row Issue scope. |
| `()` | Whole-artifact Issue scope. |

Address segments are literal strings, not dot/slash paths. Every scope must resolve
to real output. Report an unmatched target against its actual input row and put the
attempted key in Issue details; do not fabricate an output address. An output
address is distinct from its source Locations: a derived total can trace to many
source cells.

Every Evidence row needs a UUID; an empty Table is valid. Ordinary Tables may have
unidentified rows. IDs travel with Rows, not a parallel `row_ids` field. Reordering
and filtering retain surviving identities and Claim associations. Row IDs from a
source edition are not business identities.

## Construct and inspect table Evidence

| API | Contract |
| --- | --- |
| `tabular.from_claims(*, name, columns, row_ids, claims, issues=())` | Builds cells from terminal Claim values in the declared row/column order, then validates the complete artifact. |
| `tabular.row(evidence, row_id)` | Returns the complete Row by UUID, never by position. |
| `tabular.claim(evidence, row_id, column)` | Returns the terminal Claim for a cell. |
| `tabular.issues_for(evidence, row_id, column=None)` | Includes applicable row/cell and ancestor scopes in Issue order. |
| `validate(evidence)` | Rechecks structural agreement; returns `None`. It does not apply a business usability policy. |
| `fingerprint(evidence)` | Returns a versioned SHA-256 digest of supported content, Claims/Sources and Issues. |

Read cells through `row.values[column]`. Unsupported arguments and invalid Evidence
are errors, not empty results. `EvidenceValidationError` supplies a code and optional
key. Invalid addresses in an Evidence structure use `invalid_address`; direct table
inspection of an unknown row or column raises `KeyError`. Generic validation checks exact cell coverage,
Claim/value agreement, scopes, duplicate Issues, canonical identities, cycles and
an explanation for every unavailable cell.

## Values, missing data and units

The strict Evidence payload encoding accepts exact immutable Python types:
`None`, `bool`, `int`, finite `float`, `str`, `UUID`, `date`, `datetime`, `time`,
`timedelta`, and recursively supported tuples/frozensets. Temporal timezones are
restricted to built-in `timezone` and `ZoneInfo`. Mutable subclasses, lists,
dictionaries, arrays, arbitrary enums, live Pint quantities, parser objects and
CAD/GIS sessions are not cell or Claim payloads. Issue detail values follow the
same rules. Use immutable tuples of named values for raw structured observations.

An ordinary Table has fewer restrictions; `frozen=True` alone does not make rich
cells immutable. Evidence restrictions do not change canonical Model property
content. Numeric observations retain explicit unit policy in their supporting
rules; composition supplies canonical quantities. Extraction does not guess units.

`None` means no resolved output value. It requires an applicable Issue; it does not
assert that the domain object does not exist. Zero and `False` are real, distinct
values. Cell-to-Claim agreement uses exact typed encoding, not numeric tolerance.

| Situation | Terminal value | Explanation |
| --- | --- | --- |
| Valid zero | `0` | No missing-value Issue required. |
| Missing formula cache | `None` | `missing_formula_cache`. |
| Rejected numeric text | `None` | Numeric interpretation Issue. |
| Conflicting candidates | `None` | Derived Claim retains all candidates and the rule. |
| Usable value requiring review | Actual value | Advisory Issue can coexist with the value. |

A downstream rule decides whether missing data prevents a complete result, omits
a scope, or remains an explicit unresolved declaration. Truthiness and severity
alone cannot decide. A complete total and its known subtotal are different
results. A check report is not an RK Reconciliation selecting a Fact Claim.

## Issues

`Issue` has `rule_id`, `code`, `severity`, `message`, nonempty unique `at` scopes,
optional `related_claims` and immutable `details`. Its `id` is derived from rule,
code, scopes and related Claim IDs. Message, severity, detail counts and timestamps
do not determine Issue identity. They can still affect the artifact fingerprint.
A changed source edition can create new Issue identity; reviewing an old Issue
does not approve new evidence.

Severity is presentational. Even `Severity.ERROR` does not automatically reject
Evidence or select a value. Operation policies determine their consequences.
There is no `IssueEffect`. The foundation validates structure; each operation owns
its code meanings and details. Cross-input context uses related Claims, while
`at` scopes stay local to the output.

Problems before output exists belong to [Outcome Diagnostics](workflow.md#operations-outcomes-and-diagnostics).
Do not duplicate addressed cell Issues as invocation Diagnostics. Retain input
artifacts and selection/resolution lineage so an output change does not erase the
reason for it. Resolved outputs must not inherit an obsolete missing-value policy
merely because it affected an upstream input.

## Identity and fingerprints

Fingerprints include the `rk.table-evidence/v1` encoding identifier, ordered
rows/columns, content, terminal/upstream Claims, Sources and Issues. Names and
explanatory messages are content. Unordered mappings and sets are canonicalized;
boolean/numeric and temporal type distinctions remain. No `repr`, pickle,
arbitrary stringification or runtime timestamp supplies semantic identity.

A row ID identifies a row, not its complete content. Claim IDs for library
transformations bind their inputs, effective settings, Method version and output
address. Sorting/selection preserve existing Claim objects; changed outputs get
derived Claims. Generic joins, splits and groups are not implemented operations.
Any future implementation must define ordering, cardinality, row identity,
contributor selection and incomplete-result rules explicitly.

Operations prepare an immutable Evidence input once per call, reusing its validated
Claim/Source/Issue indexes and fingerprint. Outputs receive independent validation.
Preparation is local to the exact input object and call; it is not a persistent
cache or a second authoritative representation.

## Numeric interpretation

`tabular.numbers(evidence, *, specifications, settings=None, name=None)` appends
columns from an ordered mapping of output names to `NumberSpec`. Each specification
requires `column`; defaults are `integer=False`, `nonnegative=False` and
`missing_markers=()`. `NumberSpec.from_mapping` rejects unknown fields and wrong
types. Marker sequences are copied, trimmed and deduplicated.

Numbers accept integers and finite floats, including zero and negative values
unless restricted. Integral floats become integers only when requested. Numeric
strings and booleans are not coerced. Fractional counts, blank strings and configured
missing markers become unavailable with Issues. Nonfinite Evidence is already
invalid. Existing columns, row IDs and Claims remain unchanged.

Every result is derived from its source Claim and optional `settings` Claim.
Effective settings are recorded even without that Claim. Settings lineage affects
operation fingerprints and derived identities. Already unavailable inputs retain
upstream Issue codes, messages, severity, details and related Claims at the output
address. Numeric interpretation does not inspect Excel or infer units.

## Selection and concatenation

`tabular.select(evidence, *, row_ids=None, columns=None, name=None)` defaults to all
rows and columns in their current order. Explicit selectors choose output order;
empty selectors are allowed. Existing Claims are reused. Removed Issue scopes are
discarded from the output; surviving scopes retain their explanations and related
Claims. Keep the input when excluded evidence must remain available for audit.

`tabular.concat(inputs, *, name)` requires at least one input and identical
ordered columns. It preserves input and row order. Duplicate row IDs are rejected;
compatible empty inputs are allowed. A table-wide Issue is scoped to that input's
surviving rows; an empty input has no applicable output scope. Identical resulting
Issues are deduplicated. Conflicting Issues or Claim/Source identities make the
operation unavailable.

Malformed requests raise exceptions. Unknown/repeated selectors, missing columns,
output collisions, schema mismatches, duplicate rows and incompatible evidence
return Diagnostics with no output. A cell-level numeric failure can leave an
available output Table. All outputs retain exact terminal Claim coverage and
explanations for `None`.

## Bounded text interpretation and predicates

`workflow.evidence.transform` owns `TransformSpec` and `transform`. The operation
appends derived columns and preserves source columns. Supported policies are
`normalize`, `capture`, `capture_integer`, `lookup`, `agreement`, `fallback`,
`format` and `match`.

Normalization explicitly trims text and applies the chosen case policy. Capture
and match use full regular-expression matches; integer conversion is confined to
`capture_integer`, not added to `NumberSpec`. Lookup uses its declared mapping and
default. Agreement compares available observations with exact types and reports
conflict rather than choosing one. Fallback explicitly takes the first non-`None`
input in declared order. Format allows declared plain field names, not arbitrary
attribute access or executable expressions. Unavailable/conflicting outputs retain
Claims and Issues.

`workflow.evidence.predicates.Predicate` declares one column and accepted values.
Its mapping form requires exactly one of `equals` or `in`. `select_where` selects
matching rows using the same Claim/Issue projection as `select`. Equality is type
sensitive: `False` does not match numeric zero. These bounded operations can run
directly without YAML or the workflow runner.

## Inspection and export limits

The [worked example](../../examples/ingestion/ingestion_evidence.py) demonstrates
available, missing, conflicting and resolved observations and row reordering.
[Excel extraction](excel.md) creates this Evidence from native snapshots.

Bounded display is a projection. Indicate truncation and retain access to full
evidence; do not truncate canonical support for composition. Source text is data,
not executable instructions. Inspection does not accept a decision or alter rules.

An ordinary Table export omits its Claim map and Issues. CSV/Polars therefore cannot
restore lossless Evidence, source observations or Model provenance. There is no
universal Evidence artifact transport/persistence format; declare a companion
encoding when one is needed. Workflow review exports have their own explicit
[contract](workflow.md#workbench-and-publication).
