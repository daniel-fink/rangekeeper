# Diagnostics and codes

Validation reports, contract failures and Run diagnostics each carry a code.
`rangekeeper.errors.Code` lists the codes
([ADR-016](../decisions/016-safety-defaults.md)). Read a finding by its code
and its fields. Never parse its message: the message is for people, and its
text can change in any release.

```python
import rangekeeper as rk

report = composition.validate(resolver=store)
for issue in report.issues:
    if issue.code is rk.errors.Code.ROLE_MISSING:
        print(issue.targets, issue.values["keys"])
```

## Codes

`Code` is a string enum. A member's value is the text that reports and Runs
record, for example `Code.UNIQUE == "semantic.unique"`. The values are a wire
contract: a Run that is read back has the same code text.

| Group | Values | Examples |
| --- | --- | --- |
| Structure | `structure.json`, `structure.kind`, and `structure.<keyword>` for each JSON Schema keyword | `STRUCTURE_REQUIRED`, `STRUCTURE_TYPE`. A keyword without its own member has the code `STRUCTURE` and a `keyword` value |
| Semantic | `semantic.*` | `CONTRACT`, `UNIQUE`, `CYCLE`, `IDENTITY`, `UNITS`, `ROLE_MISSING` |
| References | `reference.*` | `REFERENCE_MISSING`, `REFERENCE_KIND` |
| Batches | `batch.*` | `BATCH_MODEL` |
| Execution | Bare words in Run diagnostics | `SOLVER_TERMINATION`, `UNDERDETERMINED`, `SYMBOL_LIMIT`, `CONSTRAINT_LIMIT`, `SETTINGS_ADJUSTED` |

`CONTRACT` is the general code of a semantic rule. Rules that callers must tell
apart have their own codes.

## Validation issues

A `ValidationReport` holds `Issue` values. Each `Issue` has these fields:

| Field | Contents |
| --- | --- |
| `code` | A `Code` member |
| `message` | Text for people. It names objects by code or key and by UUID |
| `document_id` | The document that contains the finding, when known |
| `path` | The JSON Pointer of the finding in that document |
| `targets` | The UUIDs of the records that the finding is about |
| `values` | Named inputs of the finding, for example the expected and actual kinds of a reference |
| `evidence` | Measured results that support the finding |

`ContractError` carries the same code and fields. Validation entrypoints copy
them into the `Issue` that they report.

## Run diagnostics

A Run `Diagnostic` records its code as text, a document and a target, numerical
residuals and tolerances, and references to the Values and Movements that take
part. An underdetermined solve references the unknowns that no row constrains.
A limit failure has the code of the limit. See
[execution](execution.md#settings-limits-and-conclusions).
