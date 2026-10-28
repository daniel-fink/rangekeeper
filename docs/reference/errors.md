# Errors and diagnostics

Errors, validation reports, contract failures and Run diagnostics each carry a code.
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
| Structure | `structure.json`, `structure.kind`, `structure.<keyword>` for each JSON Schema keyword, and `structure.value` and `structure.rule` from the generated node checks of typed construction and `replace` | `STRUCTURE_REQUIRED`, `STRUCTURE_TYPE`. A keyword without its own member has the code `STRUCTURE` and a `keyword` value |
| Semantic | `semantic.*` | `CONTRACT`, `UNIQUE`, `CYCLE`, `IDENTITY`, `UNITS`, `ROLE_MISSING` |
| Invariants | `invariant.<kind>` for the local rules of a value type: Period, Span, Movement, Flow and Distribution | `INVARIANT_FLOW`, `INVARIANT_PERIOD` |
| References | `reference.*` | `REFERENCE_MISSING`, `REFERENCE_AMBIGUOUS`, `REFERENCE_KIND` |
| Batches | `batch.*` | `BATCH_MODEL` |
| Hierarchies | `hierarchy.*` | `HIERARCHY_CYCLE`, `HIERARCHY_MULTIPLE_PARENTS` |
| Other errors | Bare words | `DECODE`, `ENCODING`, `REVISION_CONFLICT`, `UNSUPPORTED_VERSION` |
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
part. Its optional `values` field is one JSON object of the named inputs and
evidence of the finding; the code gives the names. An underdetermined solve
references the unknowns that no row constrains. A limit failure has the code of
the limit. See [execution](execution.md#settings-limits-and-conclusions).

| Code | `values` |
| --- | --- |
| `settings_adjusted` | `settings`: the names of the requested settings that changed or did not apply (required). `disposition`: for example `clamped` or `not_applied`. `effective`: the value that applied, when there is one |
| `solver_termination` | `termination`: the backend termination. The other names are the backend evidence, for example `solution_status`, `simplex_iterations` and `solver_options` |
| `solver_scaling` | `rows`: for each compiled row, its `constraint`, `divisor` and `residual_units` |

```python
for diagnostic in run.report.diagnostics:
    if diagnostic.code == rk.errors.Code.SETTINGS_ADJUSTED:
        print(diagnostic.values["settings"], diagnostic.values["disposition"])
```

## Errors

Every error that Rangekeeper raises subclasses `rangekeeper.errors.RangekeeperError`
and has a `code`. Each error has one public path
([ADR-017](../decisions/017-api-and-formats.md)). `rangekeeper.errors` exports
the base and the errors that several packages raise. An error of one package is
exported by that package; the table names the package. Each error also
subclasses the built-in type that callers caught before, so `except ValueError`
still catches a `ValidationError`.

```python
try:
    model = rk.Model.from_data(data)
except rk.errors.ValidationError as error:
    print(error.code, [issue.code for issue in error.report.issues])
```

| Error | Built-in base | Code |
| --- | --- | --- |
| `ValidationError` | `ValueError` | The code of the first issue in `report` |
| `ContractError` | `ValueError` | Given by the rule; `CONTRACT` by default |
| `UnsupportedError` | `ValueError` | Given by the failure; `UNSUPPORTED_CAPABILITY` by default. `document` and `target` locate the declaration |
| `model.system`: `HierarchyError` | `ValueError` | A `hierarchy.*` code. `ids` names the offending Entities |
| `MissingReferenceError` | `LookupError` | `REFERENCE_MISSING`. `requested`, `by`, `kind`, `where` and `candidates` say what was requested and where ([lookups](#lookups)) |
| `AmbiguousReferenceError` | `LookupError` | `REFERENCE_AMBIGUOUS`. A lookup for one item found several; `candidates` names each match |
| `ReferenceTypeError` | `TypeError` | `REFERENCE_KIND` |
| `IdentityConflictError` | `ValueError` | `REFERENCE_IDENTITY` |
| `RevisionConflictError` | `ValueError` | `REVISION_CONFLICT` |
| `UnsupportedVersionError` | `ValueError` | `UNSUPPORTED_VERSION` |
| `UnitError` | `ValueError` | `UNITS`. `suggestions` gives spellings to try |
| `DecodeError`, `EncodingError` | `ValueError` | `DECODE`, `ENCODING` |
| `TableError` | `ValueError` | `TABLE` |
| `UnknownExtensionError` | `LookupError` | `EXTENSION_UNKNOWN`. `suggestions` gives registered names to try ([extension points](extensions.md)) |
| `ExtensionConflictError` | `ValueError` | `EXTENSION_CONFLICT` |
| `model.system`: `SelectionError`, `AggregationError` | `ValueError` | `SELECTION`, `AGGREGATION` |
| `market`: `ReplayUnavailableError` | `ValueError` | `REPLAY_UNAVAILABLE` |
| `specification.rule`: `RuleCapabilityError` | `ValueError` | `RULE_CAPABILITY` |
| `NumericalError` | `ValueError` | `NUMERICAL_FAILURE` |
| `BackendUnavailableError`, `AttemptDeadlineError` | `RuntimeError` | `BACKEND_UNAVAILABLE`, `ATTEMPT_DEADLINE` |
| `PublishedFileError` | `OSError` | `PUBLISHED_FILE` |

### Lookups

A lookup returns one item or raises. A lookup by UUID, code, name, key or path
that finds no item raises `MissingReferenceError`; a lookup for one item by code
or name that finds several raises `AmbiguousReferenceError`. A search, such as
`Model.find_entities`, returns a tuple that can be empty. Both errors have these
fields:

| Field | Contents |
| --- | --- |
| `requested` | The value that the caller gave: a UUID, code, name, key or JSON Pointer |
| `by` | What `requested` is: `"id"`, `"code"`, `"name"`, `"key"` or `"path"` |
| `kind` | The kind of item, for example `"Entity"`, `"Measure"` or `"document"` |
| `where` | The document, store or owner that was searched, for example `"Model <uuid>"` |
| `candidates` | For a missing item, the nearest codes or names that exist; for an ambiguous one, the code of each match |

```python
try:
    model.entity(code="building_c")
except rk.errors.MissingReferenceError as error:
    print(error.requested, error.where, error.candidates)
```

Argument guards raise plain `TypeError` and `ValueError` for a wrong Python
argument. An optional dependency that is not installed raises `ImportError`.
`ValidationError` has the same name as an error in jsonschema, which the
library uses inside; import it from `rangekeeper.errors`.
