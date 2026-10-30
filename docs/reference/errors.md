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
| Semantic | `semantic.*` | `CONTRACT`, `UNIQUE`, `CYCLE`, `IDENTITY`, `UNITS`, `ROLE_MISSING`, `MODEL_MISSING` (no Model, or no pinned Model), `RESOLVER_MISSING` (a call must load included or case Specifications and has no resolver) |
| Units | `incompatible_units`: the two sides of an equation, the operands of a sum, or a value and the quantity that fixes it, have units with other dimensions ([dimensional analysis](#dimensional-analysis)) | `INCOMPATIBLE_UNITS` |
| Currency amounts | `currency_amount` (a magnitude whose type does not match its units) and `amount_digits` (more than 15 significant digits) | `CURRENCY_AMOUNT`, `AMOUNT_DIGITS` |
| Invariants | `invariant.<kind>` for the local rules of a value type: Period, Span, Movement, Flow and Distribution | `INVARIANT_FLOW`, `INVARIANT_PERIOD` |
| References | `reference.*` | `REFERENCE_MISSING`, `REFERENCE_AMBIGUOUS`, `REFERENCE_KIND` |
| Batches | `batch.*` | `BATCH_MODEL`; `BATCH_REQUIRED` (the call reads the cases of a batch, and the Specification or Outcome has none) and `BATCH_UNSUPPORTED` (the call takes one concrete Specification or one leaf Outcome, not a batch) |
| Hierarchies | `hierarchy.*` | `HIERARCHY_CYCLE`, `HIERARCHY_MULTIPLE_PARENTS` |
| Equation text | `equation.*` | `EQUATION_SYNTAX` (text that does not parse), `EQUATION_FUNCTION` (a function, method or member that equation text cannot use) |
| Alignment | `alignment.*` for Periods and Flow coordinates that do not align | `ALIGNMENT_CROSSES`, `ALIGNMENT_PARTIAL`, `ALIGNMENT_MIXED`, `ALIGNMENT_DIFFER`, `ALIGNMENT_DUPLICATE`, `ALIGNMENT_GAP` |
| Comparisons | `comparison.*`, from `rk.execution.compare` | `COMPARISON_CASES`, `COMPARISON_SCALAR`, `COMPARISON_BATCH`, `COMPARISON_EMPTY` |
| Distributions | `distribution.*`, from `Outcome.distribution` and `Outcome.mean` | `DISTRIBUTION_VALUE`: a Flow value has no distribution, and a date value has counts but no mean |
| Other errors | Bare words | `DECODE`, `ENCODING`, `REVISION_CONFLICT`, `UNSUPPORTED_VERSION` |
| Execution | Bare words in Run diagnostics | `SOLVER_TERMINATION`, `UNDERDETERMINED`, `NONAFFINE_UNKNOWNS`, `SYMBOL_LIMIT`, `CONSTRAINT_LIMIT`, `SETTINGS_ADJUSTED` |

`CONTRACT` is the general code of a semantic rule. Rules that callers must tell
apart have their own codes.

### Dimensional analysis

Model validation checks the units of each equation when a Model is committed,
made or read (ADR-016). The two sides of an equality or a bound, and the
operands of a sum or a difference, must have compatible units; a product or a
quotient multiplies or divides them. A failure is an issue with the code
`incompatible_units`. Its `values` give the `equation` text, the `term` that
fails and its two `units`; its target is the Constraint:

```python
issue.values == {
    "equation": "total_cost = land_cost + area",
    "term": "land_cost + area",
    "units": ["AUD", "sqm"],
}
```

A call of an equation function has the units that its registry entry gives,
such as the units of the Flow for `operating.at(on=sale_date)`, and a growth
profile of an amount per year has the units of each Period's amount. A part
whose units are unknown, such as a selection or a query, is not checked. Specification validation checks each quantity that fixes a value
against the value's units: the issue has `key`, `units` and `expected`, and
`fix()` raises `UnitError` with the code `INCOMPATIBLE_UNITS`. A conversion
between incompatible units raises the same `UnitError`. Execution reports units
that disagree as `incompatible_units` with the Status `INVALID`, never as an
unsupported capability.

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
references the free unknowns that the equations do not determine. A limit failure has the code of
the limit. See [execution](execution.md#settings-limits-and-conclusions).

| Code | `values` |
| --- | --- |
| `settings_adjusted` | `settings`: the names of the requested settings that changed or did not apply (required). `disposition`: for example `clamped` or `not_applied`. `effective`: the value that applied, when there is one |
| `solver_termination` | `termination`: the `Termination` value (`feasible`, `infeasible`, `limited`, `failed` or `unknown`; a Run written before 1.0.0b1 can hold `limit` or `error`, which `Outcome.evidence` reads as `limited` and `failed`; a Run of 1.0.0a1 holds a backend word, and a Run that `tools/upgrade` converted has no `values`: `Outcome.evidence` reads both as `unknown`). The other names are the backend evidence; for `pyomo-highs`, `termination_condition` (the Pyomo condition), `solution_status`, `simplex_iterations` and `solver_options` |
| `solver_scaling` | `rows`: for each row, its `constraint`, `divisor` and `residual_units`. The `pyomo-highs` backend records it |
| `underdetermined`, `uniqueness_not_assessed` | `equality_rank` and `unknown_count`, from the analysis of the affine problem. `unknowns`: the keys of the free unknowns, as `Model.key_of` gives them, which `Outcome.free_unknowns` reads with or without an output. The diagnostic's `references` are those unknowns |
| `nonaffine_unknowns` | `equation`: the text of the Constraint, for example `"noi = coverage * debt_service"`. `unknowns`: the keys of the unknowns in the term that is not affine, as `Model.key_of` gives them. The diagnostic's `references` are those unknowns, as for `underdetermined` |
| A failure from `UnsupportedError` | `equation`, when the failure is in one Constraint |
| `active_side` | No active side of each `max` and `min` held ([piecewise equations](execution.md#piecewise-equations)). `target` is the Constraint whose side disagrees; `targets` names several. The message gives the equations |
| `specification_invalid` | `issues`: each validation issue of the attempt, with its `code`, `message`, `document`, `path`, `targets`, `values` and `evidence` |
| A failure from another error | `path`, when the error has one; `targets`, when it names more than one record. One target is the diagnostic's `target` |
| `constraint_residual` | `equation`: the text of the Constraint that was checked. `formulation`: the Formulation that groups an equation of the Model, by its name (such as `"Funding"`) or, for an entity's default Formulation, its code. `target` is the Constraint |

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
    model = rk.Model.from_data(data=data)
except rk.errors.ValidationError as error:
    print(error.code, [issue.code for issue in error.report.issues])
```

Every error takes its message first and each field by keyword. These fields
(`rk.errors.ErrorFields`) are common to all errors, with the meaning that they
have in an `Issue`:

| Field | Contents |
| --- | --- |
| `code` | A `Code` member. An error class without its own code takes one |
| `document_id` | The document that contains the failure, when known |
| `path` | The JSON Pointer of the failure in that document |
| `targets` | The UUIDs of the records that the failure is about |

An error class adds its own fields after these, also by keyword. An error keeps
all of its fields through `pickle`.

| Error | Built-in base | Code |
| --- | --- | --- |
| `ValidationError` | `ValueError` | The code of the first issue in `report`. `ValidationError(report)` takes the report; the common fields are those of its first issue |
| `ContractError` | `ValueError` | Given by the rule; `CONTRACT` by default. `values` and `evidence` are the named inputs and measured results |
| `UnsupportedError` | `ValueError` | Given by the failure; `UNSUPPORTED_CAPABILITY` by default. `document_id` and `targets` locate the declaration (the Constraint), and `equation` gives its text. With `NONAFFINE_UNKNOWNS`, `unknowns` gives the keys of the unknowns in the term that is not affine |
| `execution`: `OutcomeError` | `ValueError` | The code of the diagnostic that gives the reason; `SOLVER_TERMINATION` by default. `status` is the Outcome's `Status`. `Outcome.raise_for_status()` raises it when no other error applies ([execution](execution.md#settings-limits-and-conclusions)) |
| `model.system`: `HierarchyError` | `ValueError` | A `hierarchy.*` code, given by keyword. `targets` names the offending Entities |
| `duration`: `AlignmentError` | `ValueError` | A `ContractError` with an `alignment.*` code, given by keyword: `ALIGNMENT_CROSSES` when a Period crosses the bounds of a selection, `ALIGNMENT_PARTIAL` when Periods end with a partial Period, `ALIGNMENT_MIXED` when Flows mix dated and period amounts, `ALIGNMENT_DIFFER` when Flows that must match have other coordinates, `ALIGNMENT_DUPLICATE` when a Flow repeats a coordinate, and `ALIGNMENT_GAP` when Periods leave a gap. `values` gives the Periods as ISO intervals ([Spans and Periods](calculations.md#spans-and-periods)). `duration` and `flow` raise it |
| `MissingReferenceError` | `LookupError` | `REFERENCE_MISSING`. `requested`, `by`, `kind`, `where` and `candidates` say what was requested and where ([lookups](#lookups)) |
| `AmbiguousReferenceError` | `LookupError` | `REFERENCE_AMBIGUOUS`. A lookup for one item found several; `candidates` names each match |
| `ReferenceTypeError` | `TypeError` | `REFERENCE_KIND` |
| `IdentityConflictError` | `ValueError` | `REFERENCE_IDENTITY` |
| `RevisionConflictError` | `ValueError` | `REVISION_CONFLICT` |
| `UnsupportedVersionError` | `ValueError` | `UNSUPPORTED_VERSION` |
| `UnitError` | `ValueError` | `UNITS`, or `INCOMPATIBLE_UNITS` for units with other dimensions. `suggestions` gives spellings to try |
| `EquationError` | `ValueError` | `EQUATION_SYNTAX` by default, or the code of the failure: `REFERENCE_MISSING`, `REFERENCE_AMBIGUOUS`, `UNITS`, `EQUATION_FUNCTION` or `PREDICATE`. `text[start:end]` is the part of the equation text that fails, and `suggestions` gives text to try ([equation text](expressions.md#equation-text)) |
| `DecodeError`, `EncodingError` | `ValueError` | `DECODE`, `ENCODING` |
| `TableError` | `ValueError` | `TABLE` |
| `UnknownExtensionError` | `LookupError` | `EXTENSION_UNKNOWN`. `suggestions` gives registered names to try ([extension points](extensions.md)) |
| `ExtensionConflictError` | `ValueError` | `EXTENSION_CONFLICT` |
| `model.system`: `SelectionError`, `RollupError` | `ValueError` | `SELECTION`, `ROLLUP` |
| `market`: `ReplayUnavailableError` | `ValueError` | `REPLAY_UNAVAILABLE` |
| `execution.rule`: `RuleCapabilityError` | `ValueError` | `RULE_CAPABILITY` |
| `NumericalError` | `ValueError` | `NUMERICAL_FAILURE`, or `NUMERICAL_REJECTION` when verification rejected a candidate |
| `BackendUnavailableError`, `AttemptDeadlineError` | `RuntimeError` | `BACKEND_UNAVAILABLE`, `ATTEMPT_DEADLINE` |
| `PublishedFileError` | `OSError` | `PUBLISHED_FILE`. `file` is the published file; the `OSError` that stopped the confirmation is the cause |

### Lookups

A lookup returns one item or raises. A lookup by UUID, code, name, key or path
that finds no item raises `MissingReferenceError`; a lookup for one item by code
or name that finds several raises `AmbiguousReferenceError`. A search, such as
`Model.find_entities`, returns a tuple that can be empty. Both errors have these
fields:

| Field | Contents |
| --- | --- |
| `requested` | The value that the caller gave: a UUID, code, name, key or JSON Pointer |
| `by` | What `requested` is: `"id"`, `"code"`, `"name"`, `"key"` or `"path"`. A dotted key such as `"building_a.income"` is a `"path"`, and `requested` is the whole dotted key |
| `kind` | The kind of item: a record or class name, such as `"Entity"`, `"Value"`, `"Movement"`, `"Specification"` or `"Outcome"`, or `"document"` for a store |
| `where` | The document, store or owner that was searched: its kind, then its code, name or UUID when it has one, for example `"Model <uuid>"`, `"Entity building_a"`, `"Specification Front door"` or `"ModelDraft"` |
| `candidates` | For a missing item, the nearest codes or names that exist; for an ambiguous one, the code of each match |

```python
try:
    model.entity(code="building_c")
except rk.errors.MissingReferenceError as error:
    print(error.requested, error.where, error.candidates)
```

An argument of the wrong Python type raises `TypeError`. Every other failure on
a public path raises a `RangekeeperError` subclass with a `Code`: a wrong value,
a lookup that finds nothing, data or state that is not valid. `shared`,
`schema`, `money`, `duration`, `flow`, `finance` (`pv`, `npv`, `irr` and
`payment`), `market.dynamics`, `model`, `specification` and the `Outcome` and
comparisons of `execution` follow this rule: for example, `Table.column` and
`Record.has_field` raise `MissingReferenceError`, and `Record.from_data` raises
`ValidationError` with `structure.json` for data that is not JSON. In `flow`, an
unresolved or non-finite amount raises `NumericalError`, incompatible units
raise `UnitError`, coordinates that do not align raise `AlignmentError`, a
missing line raises `MissingReferenceError`, and conflicting names or revisions
in `Stream.merge` raise `IdentityConflictError` or `RevisionConflictError`. The
older `finance.financial` functions and the other internal `market` modules
still raise plain errors; their replacements
([#167](https://github.com/daniel-fink/rangekeeper/issues/167),
[#298](https://github.com/daniel-fink/rangekeeper/issues/298)) follow the rule.
An optional dependency that is not installed raises
`ImportError`.
`ValidationError` has the same name as an error in jsonschema, which the
library uses inside; import it from `rangekeeper.errors`.
