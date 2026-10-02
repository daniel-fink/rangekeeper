# Composable validation refactor — 2026-10-02

Implemented after Turn 2, before Turn 3. The [domain guide](../../../DOMAIN_CORE.md#composable-validation)
documents module ownership, operations, and limits. No schema, fixture, solver,
consumer implementation, or existing test expectation was changed.

## What changed

- Argument guards remain in `validate.py`; `is_text` now exposes its existing type
  narrowing through `TypeGuard[str]`.
- `require`, `require_unique`, `require_acyclic`, and `require_ownership` live in the
  domain-independent `_validation.py`. Callers import exceptions from `errors.py`.
- Model and partial Specification validation use one `validate_formulation_names`.
- `Scope` contains read-only lookup tables over borrowed records. Expression/domain
  analysis, Function signature checks, and predicate validation are separate functions
  receiving an explicit scope. `build_scope` composes indexing and signature checks.
- Constraint code uniqueness is checked per owner. Combined predicate validation has
  no `check_codes` switch; repeated references to one predicate remain valid.
- `ContractError` can retain a specific code and path; `bounded` carries those into
  `ValidationReport`. The extracted helpers and predicate checks use that context.
  Canonical Model paths are retained for Formulations, ownership, and the shared
  Entity/Assembly code namespace. Remaining legacy rules may still emit generic
  `semantic.contract` issues. This is not exhaustive semantic error collection.
- Schema conformance scripts use the refactored calls; their fixtures and assertions
  retain their meaning. Public domain construction and lookup APIs are unchanged.

## Verification

| Check | Result | Evidence |
| --- | --- | --- |
| Full local pytest run | **599 executed: 597 passed, 2 unchanged baseline failures**, 7 warnings, no skips/errors. | [log](pytest-current.log), [XML](pytest-current.xml) |
| Record/domain/refactoring acceptance | **106 passed** within that run, including **24 new regression cases**. | [summary and preservation](preservation.json) |
| Seven schema suites | All pass with the prior acceptance/rejection counts. | [core](schema-validate-final.log), [native](schema-native_roundtrip-final.log), [expressions](schema-expressions-final.log), [formulations](schema-formulations-final.log), [models](schema-models-final.log), [specifications](schema-specifications-final.log), [runs](schema-runs-final.log) |
| Static checks | 38 source/example files pass; all 8 generated-record and 6 domain misuse examples are rejected as intended. | [log](typing-verified.log) |
| Installed wheel | Record operations and unit-free public Model/Specification operations pass in a fresh minimal environment outside the checkout. | [log](installed-verified.log) |
| Generation and native records | Five artifacts still match generation; 16 native fixture round trips pass. | [generation](regenerate-check.log), [native](native-verified.log) |

The unchanged failures are the adapter export-list mismatch and numerical solver
residual discrepancy already characterized in the [baseline](../BASELINE.md). No
expectations were weakened. Three live Speckle API tests remain excluded/unverified.
Remote CI, external consumers, other Python versions and other platforms were not run.
No new-schema executor or authentic Run publication is claimed.

Regression coverage includes separate Python argument errors, missing/null names,
case-sensitive owner-local uniqueness, escaped diagnostic paths, shared descendants
versus cycles, repeated/cyclic containment, prerequisite gating, propagation of
programming errors, read-only scope tables, shared predicate references, independent
signature checking, cross-kind mathematical identity collisions, and canonical
Model/Specification diagnostic paths. The original 82 boundary tests remain unchanged.

## Reproduction and retained state

Run from the repository root:

```sh
/private/tmp/rk-domain-runtime/bin/python docs/research/domain-migration/validation-refactor/verify.py
```

[verify.py](verify.py) accepts explicit schema/runtime Python paths and a mypy path.
It records exact argv, cwd, environment overrides, exit status, and log locations in
[verification-commands.jsonl](verification-commands.jsonl), then checks that the only
pytest failures are the two named baseline failures. Build and generation checks use
isolated temporary directories. Repeated runner logs get distinct filenames; retain
separate evidence directories for separate implementation checkpoints.

The schema environment uses Python 3.10.19, LinkML/linkml-runtime 1.11.1,
jsonschema 4.26.0, and PyYAML 6.0.3; see [environment](environment-final.log).
The supplemental runtime and mypy 1.18.2 installation are the unchanged
[Turn 2 environments](../turn2/README.md#reproduction-and-environments).
The wheel check still exercises the documented minimal dependency subset, not every
legacy integration or full numerical stack.

The first full run (`pytest-final.log`) included the first 20 new cases. Four additional
public diagnostic-path integration cases were then added and the final full run was
retained as `pytest-current.log`. Runtime code did not change between the seven-suite,
type, wheel checks and that final pytest run. Early development surfaced missing type
annotations and a test command issued from the wrong cwd; these were corrected before
final acceptance. No implementation or conformance failure remains from this refactor.

[initial.json](initial.json) records the starting hashes, HEAD, index entries, and
local backup directory. [final-fingerprints.json](final-fingerprints.json) records
final verification inputs. [preservation.json](preservation.json) confirms 285 of the
310 initially fingerprinted files were unchanged; all changed existing files are in
the approved runtime/check/documentation scope. Authoritative schemas, fixtures,
generated artifacts, legacy graph/numerical code, existing tests, dependencies,
and the unrelated `.gitignore` edit are unchanged.

The index acquired a staged copy of the new regression test outside these commands;
it was left alone and predates the four final integration cases. Existing staged
entries were preserved. Verification exercises the working tree. HEAD remains
`c91a76c941bac0a26fa18ad5a3105ab4641f22f0`; no staging, commit or push command was run.

Next is the previously agreed **Turn 3 / work units 3C and 4**: Run, strict codecs,
revision stores, final public exports and package acceptance.
