# References and identity

`Reference(target: UUID)` addresses one Value or Movement. The record contains no
revision UUID. Its containing Model or composed Specification supplies the scope.
`Model.resolve(reference)` returns the declared record; `Model.movement(id)` selects
a Movement directly. A Movement gets its units and Measure from its owning Value.

## Complete immutable revisions

A Model is one complete snapshot. It needs no previous Model to read its content.
Creating a revision copies the content into another immutable Model and gives that
Model a new UUID. Value and Movement UUIDs remain stable when their content changes.
`previous` records lineage; it is not an instruction to load missing content.

For example, M1 can contain a rent Value of $30,000. M2 can contain the same Value
UUID with an amount of $35,000. Both snapshots remain complete. A Reference to that
Value resolves to $30,000 in M1 and $35,000 in M2. The reference does not choose the
revision. A Specification chooses it explicitly through its input Model pin.

A Run pins the Specification used for the attempt. Diagnostic `references` resolve
only in that Run's input Model, even when the diagnostic's `document` and `target`
identify a Specification Constraint. Those fields identify the reported subject;
the references identify participating Values and Movements. Batch diagnostics have
no single participant scope, so participant references belong on child Runs. An
attempt without a valid input scope cannot report participant references.

## Movement identity and alignment

Each Movement requires a UUID unique across the Model. Keys are optional labels.
Event alignment uses `(date, key)`; repeated dates need distinct nonblank keys.
Period alignment uses its boundaries and optional recorded date. Neither alignment
rule uses the UUID. This allows separately authored Flows to align without sharing
identities. Changing a label or coordinate does not break a UUID reference.

### One rule for transforms

A transform keeps the ID of each Movement that it **passes through**: a Movement
that it selects, or whose amount it gives in other units. Each Movement that a
transform **calculates**, its amount or its coordinate, is a new Movement with a
fresh ID, also when the result equals the input (`flow.scale(1)`,
`flow.shift(by=0)`). So a transformed Flow can go under another Value only when
it has no Movement that it passed through; `clone()` gives fresh IDs to all of
them.

| Transform | Movement UUIDs |
|---|---|
| `Flow.trim`, `clean`, `drop_zeroes`, `trim_empty`; `Stream.select`, `select_values`, `trim`, `with_flows`, `with_policy`, `merge` and `stream[name]` | Kept: they select Movements |
| `Flow.convert` | Kept: the same amounts in other units |
| `Flow.since`, `until` | Kept for the Movements that keep their amounts; fresh for each zero |
| `Stream.align` | Kept for the Movements that are present; fresh for each placeholder |
| `Stream.dated` | Kept for the dated amounts; fresh for each period amount that gets a date |
| Arithmetic (`+`, `-`, `*`, `/`, unary `-`), `scale`, `negate`, `round`, `shift`, `multiply`, `integrate`, `integrate_time`, `cumulative`, `diff`, `split`, `resample`, `collapse`; `Stream.resample`, `split`, `aggregate`, `sum`, `min` and `max`; `rk.finance.pv` | Fresh for every result Movement |
| `Flow.clone()` | Fresh for every Movement, for an independent Value |
| `Flow(amounts=)`, `from_events`, `from_periods`, `from_profile` | Fresh: new Movements |

Records and documents are not transforms. `Movement.replace` and `Flow.replace`
keep the IDs that they are not given. A Model revision and solver publication keep
the IDs of existing Movements, and scenario generation makes deterministic IDs from
the owning Value UUID and period. Methods that return the same Flow
(`require_resolved()`, `check()`, unary `+`) make no Movements.

For explicit identity, make the `Movement` records and pass them as
`Flow(units=, movements=)`. Decoding never generates missing IDs. Reusing one Flow
under a second Value would duplicate its Movement identities; call `clone()` to
make that independent copy.

## Comparison rules

`record == other` is type-sensitive and preserves collection order. `record.equivalent(other)`
ignores only schema-declared unordered collection order. Both preserve scalar types,
signed floating zero, multiplicity, field presence and opaque-content order. Neither
performs unit conversion. Model/Specification revision checks live in `schema/revision.py`;
content-hash encodings remain separate provenance contracts. A revision check ignores
the Metadata slots that the schema marks with the `lineage` annotation (`id` and
`previous`); every other field is content.

Store idempotency and revision conflict checks use schema equivalence. Run output
validation uses exact comparison for preserved historical Claims. A schema-unordered
collection rule must not erase ordering inside opaque evidence. Model-backed `Stream.merge`
requires the same Model revision and exactly equal Model content; schema equivalence
alone does not establish that two pinned views refer to the same snapshot content.

## Explicit format migration

Document readers accept every format with their major version, up to their own
version, without silently upgrading content. The packaged versions come from the
schema manifest. The [upgrade guide](../guides/upgrading.md)
owns supported source versions, conversion order and external pin remapping.
Migration creates new revisions. Historical Runs retain their original document
pins and reader environment; they are not rewritten as current executions.

See [record operations](records.md), [calculations](calculations.md) and
[Run storage](run-and-storage.md) for related contracts.

Internal declaration, expression-analysis and numerical symbol tables use UUID
keys. Conversion to wire/backend strings occurs at those boundaries. Shared record
traversal retains original JSON pointers and never follows References or traverses
opaque Claim content. The numerical target helpers in `model.targets` (typed
records) and `model._scope` (raw mappings) use one Value/Movement ownership rule;
reading a quantity never creates an assignment.


Model-backed Stream calculations retain source Value references separately from
current derived content. `.source_values` exposes those originals; transformed
Streams cannot be used as original Value selections in passive builders. Numerical
resampling and aggregation use new Movement IDs. Structural trimming retains IDs.
Builder keyword renames preserve saved operation strings, operand/binding order
and declaration IDs. Python `financial.pv` retains the saved `present_value` name.
