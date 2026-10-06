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

| Operation | Movement UUIDs |
|---|---|
| `Movement.replace`, Model revision, solver publication | Preserve existing IDs |
| Unit conversion, trimming, filtering and cleaning | Preserve retained IDs |
| `Flow.clone()` | Fresh IDs for an independent Value |
| Scaling, difference, collapse, aggregation, products, integration, resampling, valuation and account calculations | Fresh IDs for result movements |
| Alignment | Preserve existing IDs; create IDs for missing placeholders |
| Scenario generation | Deterministic IDs from the owning Value UUID and period |

`Flow.from_events` and `Flow.from_periods` accept `ids=` for explicit identity.
Otherwise they generate UUIDs. Decoding never generates missing IDs. Reusing one
Flow under a second Value would duplicate its Movement identities; call `clone()`
to make that independent copy.

## Draft upgrade

The current document versions are Model/Specification 0.6.0 and Run 0.3.0.
`migration.upgrade_model` and `upgrade_specification` explicitly convert supported
older drafts. A former owner/key address maps to a deterministic UUID derived from
the Value UUID and key. This gives separately upgraded Models and Specifications
the same target IDs. Supply new external revision pins explicitly, then validate
with a resolver. Opaque evidence and source inputs remain unchanged. No automatic
decoder upgrade, old type alias, or historical Run rewrite is provided.

See [record operations](RECORD_BOUNDARY.md), [calculations](CALCULATIONS.md) and
[Run storage](RUN_AND_STORAGE.md) for the related contracts.
