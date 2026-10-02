# Turn 2 verification — Model and Specification domain APIs

Observed 2026-10-02 on `acausal-modelling`, HEAD
`c91a76c941bac0a26fa18ad5a3105ab4641f22f0`. This covers work units 3A/3B; see the
[implemented API guide](../../../DOMAIN_CORE.md). It follows the preserved
[Turn 1 results](../turn1/README.md) and [original baseline](../BASELINE.md).

## Results

| Check | Observed result | Evidence |
| --- | --- | --- |
| Domain and record boundary tests | **82 passed**, including 41 new Turn 2 cases. | [log](boundary-final.log) |
| Full local suite | **575 executed: 573 passed, 2 known failures**, 7 warnings, no skips. | [log](pytest-final.log), [JUnit](pytest-final.xml) |
| Static checking | 35 source/example files pass; all 8 record and 6 domain negative examples are rejected. | [log](typing-verified.log) |
| Installed wheel outside checkout | Record checks plus public Model lookup/revision and Specification composition/validation pass without importing Pint, legacy Graph or a solver for unit-free inputs. | [log](installed-verified.log) |
| Generation and native interoperability | Artifacts still match regeneration; 16 native fixture round trips pass. | [generation](regenerate-check.log), [native](native-verified.log) |
| Existing schema suites | All seven pass with intended outcomes unchanged. | [core](schema-validate-final.log), [native](schema-native_roundtrip-final.log), [expressions](schema-expressions-final.log), [formulations](schema-formulations-final.log), [models](schema-models-final.log), [specifications](schema-specifications-final.log), [runs](schema-runs-final.log) |
| Guide examples | Both Python examples execute together successfully. | [log](guide-examples.log) |

The unchanged failures remain the adapter export-list mismatch and residual solver
result 239654.64258295443 versus expected 241049.33. Three live Speckle API tests are
excluded/unverified. No downstream project, remote CI, Windows or Python 3.11–3.13
execution is claimed. No numerical executor produced a Run.

Coverage includes multiple Values per Measure, canonical Assembly storage, nested
Formulation ownership, UUID/kind errors, opaque-content exclusion, exact-search order,
revision isolation/rollback/no-ops, known-predecessor identity reuse, provenance
preservation, unordered versus mathematical/opaque order, currency/count dimensions,
unit conversion, partial contributions, local reference kinds, diamond includes,
contributor traces, duplicate/conflicting requirements, batch boundaries, revision pins,
and recorded units in Specification-local Values.

## Reproduction and environments

[verify.py](verify.py) records argv, cwd, environment overrides, duration and status
in [verification-commands.jsonl](verification-commands.jsonl). Final hashes are in
[final-fingerprints.json](final-fingerprints.json); [initial.json](initial.json) retains
the working-tree input snapshot before implementation. Run from the repository root:

```sh
/private/tmp/rk-probe-audit-venv/bin/python docs/research/domain-migration/turn2/verify.py
```

The runner accepts explicit schema/runtime Python paths and a mypy package path. It
expects exactly the two known baseline failures. It writes isolated build/test/cache
outputs and retains verification logs here. The environment matches Turn 1:

- Python 3.10.19; LinkML/linkml-runtime 1.11.1, jsonschema 4.26.0, PyYAML 6.0.3.
  Full schema environment: [log](environment-final.log).
- Local tests use the supplemental `/private/tmp/rk-domain-runtime` environment,
  inheriting existing numerical packages and the copied validation dependencies.
  Pint 0.24.4 and py-moneyed 3.0 were observed. The pinned 308-code currency snapshot
  is packaged data; runtime code does not import moneyed or use locale.
- mypy 1.18.2 remains isolated in `/private/tmp/rk-record-typecheck`.
- The wheel test installs into a fresh venv with only the record-boundary dependency
  subset. Unit-free Model/Specification operations need no Pint import. Actual unit
  operations were tested in the runtime with its declared Pint dependency; the minimal
  wheel environment does not claim full unit-capable installation acceptance.

For focused checks in an environment with the pinned schema requirements, pytest,
Pint 0.24.4 and mypy 1.18.2:

```sh
PYTHONPATH=src python -m pytest --noconftest src/tests/test_records.py src/tests/test_domain_model.py src/tests/test_domain_specification.py -q
python tools/schema/typecheck.py
python tools/schema/verify_install.py
```

CI configuration includes these boundaries but has not run remotely. Earlier logs
without `final`/`verified` are intermediate observations, not the final acceptance run.

## Preserved work and next boundary

Authoritative schema/fixtures, generated artifacts, legacy graph/numerical implementations,
old test expectations and unrelated `.gitignore` content remain unchanged. The Turn 1
record test changes only its import to the explicitly renamed low-level
`specification.validation.validate_records` operation. The shared Specification header
check was extracted for local saved-contribution validation; composition still uses
the existing additive algorithm and all conformance cases pass.

The Git index acquired staged snapshots of some new files during implementation.
Those staged copies predate final refinements; staging was left untouched, and the
reported checks exercise the final working tree. No commit or push was performed.

Next is **Turn 3 / work units 3C and 4**: finalized Run facade and resolver support,
strict JSON/YAML codecs, memory/directory revision stores, final public root exports,
optional dependency boundaries and complete installed-package acceptance. Generic
Claim/Fact-content agreement, equation unit inference, imposed query evaluation,
solver execution and legacy consumer migration remain later work.
