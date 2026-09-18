# Evidence table operations

`rangekeeper.graph.adapter.ingestion.tabular` provides `NumberSpec`, `numbers`,
`select` and `concat`. Each operation returns `Outcome[Evidence[Table]]`, with a
versioned `Operation` describing effective settings and ordered input fingerprints.
These operations consume existing Evidence; they do not read workbook cells.

```python
from rangekeeper.graph.adapter.ingestion import tabular

numeric = tabular.numbers(
    extracted,
    specifications={
        "number_area": tabular.NumberSpec(column="area", nonnegative=True),
        "number_count": tabular.NumberSpec(
            column="count", integer=True, nonnegative=True,
            missing_markers=("-", "–", "—"),
        ),
    },
    settings=configuration_claim,  # optional existing Claim[str]
)
if numeric.output is not None:
    selected = tabular.select(numeric.output, row_ids=selected_ids,
                              columns=("area", "number_area"))
combined = tabular.concat((first_block, second_block), name="Schedule")
```

## Numeric specifications

`NumberSpec` is immutable, keyword-only, and has strict `from_mapping` and
`to_mapping` conversion. `column` is required; `integer=False`,
`nonnegative=False`, and `missing_markers=()` are the defaults. Booleans must be
actual booleans. Marker sequences are copied, trimmed and deduplicated.

Mapping keys name new output columns, appended in mapping order. Existing values,
row IDs and Claims remain unchanged. Numbers accept integers and finite floats,
including zero and negative numbers unless restricted. Integral floats become
integers only when requested. Numeric strings, booleans, fractional counts,
blank strings and configured missing markers remain unavailable with Issues.
Evidence validation already excludes non-finite values.

Every numeric result is a derived Claim referencing its source Claim and optional
settings Claim. The operation records effective settings even when no settings
Claim is supplied. Operation fingerprints include the complete settings lineage;
Claim IDs bind the operation and output address. Repeated identical inputs and
settings yield identical Claims and fingerprints.

Already-unavailable inputs retain upstream Issue codes, messages, severity,
details and related Claims at the derived output address. No Excel inspection or
severity-based availability decision occurs. Units and domain interpretation
remain downstream responsibilities.

## Selection and concatenation

`select` defaults to retaining every row/column in existing order; explicit
selectors choose their order. Empty selectors are allowed. Existing Claim objects
are reused; removed Issue scopes are discarded, surviving scopes retain their
explanations and related Claims. Changed scopes use normal Issue identity rules.

`concat` requires at least one table and identical ordered columns, preserving
input/row order and existing Claim objects. Duplicate row IDs are rejected. Empty
compatible inputs are allowed. Each table-wide Issue becomes row scopes for its
own input; an empty input has no applicable output scope. Identical resulting
Issues are deduplicated; conflicting Issues or canonical Claim/Source identities
produce an unavailable Outcome.

Malformed requests raise validation exceptions. Input incompatibilities—unknown
selectors, repeated selectors, missing columns, output collisions, conflicting
evidence, schema mismatches and duplicate rows—produce Diagnostics with no output.
Cell-level numeric failures leave the output table available. All outputs retain
the existing Evidence requirement of exactly one terminal Claim per cell and an
applicable Issue for every unavailable value.
