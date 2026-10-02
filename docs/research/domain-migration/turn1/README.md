# Turn 1 verification — generated records and shared validation

Observed 2026-10-02 on `acausal-modelling`, HEAD
`c91a76c941bac0a26fa18ad5a3105ab4641f22f0`. Changes are uncommitted.
This record follows the historical [Step 1 baseline](../BASELINE.md); it does not
replace those measurements. See [working interfaces](../../../RECORD_BOUNDARY.md).

## Final results

| Check | Result | Evidence |
| --- | --- | --- |
| Reproducible generation | All five artifacts match regeneration, 50 LinkML classes accounted for. | [log](regenerate-check.log), [manifest](../../../../src/rangekeeper/_schema/manifest.json) |
| Static typing, mypy 1.18.2 | Seven checked source/example files pass; eight deliberately invalid calls are rejected. | [log](typing-verified.log) |
| Shared native bundle | 16 Model/Specification/Run fixture round trips pass, with stock LinkML normalization explicitly distinguished from exact immutable-record export. | [log](native-verified.log) |
| Isolated installed wheel | Packaged schema/manifest/native/typing artifacts, construction, validation, timestamp rejection and lightweight imports pass outside the checkout. | [log](installed-verified.log) |
| Existing schema suites | All seven pass with their existing acceptance/rejection cases. | Logs below |
| Local Python suite | **534 collected/executed: 532 passed, 2 existing failures**, 7 warnings, no skips. Includes **41 new passing boundary tests** and 491 previously passing tests. | [log](pytest-final.log), [JUnit](pytest-final.xml) |
| Preservation | 179 protected tracked schema/fixture, existing test, graph and `.gitignore` files unchanged. Function/class ASTs in all six moved semantic modules match HEAD, except centralized ContractError ownership and imports. | [report](preservation.json) |

The two failures match the original baseline: adapter `__all__` lacks expected
`ingestion`/`operation`, and `TestSolver.test_residual` obtains
239654.64258295443 instead of 241049.33. Neither was repaired or reclassified.
The three live Speckle API tests remain excluded and unverified. External consumer
execution, Python 3.11–3.13, remote CI and solver integration remain unverified.

| Schema suite | Final log |
| --- | --- |
| Core structural examples | [validate](schema-validate-final.log) |
| Original native round trips | [native_roundtrip](schema-native_roundtrip-final.log) |
| Expressions/constraints | [expressions](schema-expressions-final.log) |
| Formulations | [formulations](schema-formulations-final.log) |
| Models | [models](schema-models-final.log) |
| Specifications/composition | [specifications](schema-specifications-final.log) |
| Runs | [runs](schema-runs-final.log) |

The suite output retains the original “generated schemas” wording; the structural
schemas now come from the packaged shared bundle. `generate.py --check` independently
verifies that bundle against the current authoritative inputs before these final runs.

## Environment and commands

The [verification runner](verify.py) retains exact argv, cwd, selected environment
overrides, elapsed time and exit status in
[verification-commands.jsonl](verification-commands.jsonl). The final input and
artifact hashes are in [final-fingerprints.json](final-fingerprints.json).

- Python 3.10.19. Schema tools use `/private/tmp/rk-probe-audit-venv/bin/python`:
  LinkML 1.11.1, linkml-runtime 1.11.1, jsonschema 4.26.0 and PyYAML 6.0.3.
  Full versions are in [environment-final.log](environment-final.log).
- The local test environment extends the prior isolated
  `/private/tmp/rk-domain-runtime` environment with jsonschema, its runtime
  dependencies and `rfc3339-validator` copied from the schema environment. It still
  inherits the existing `src/.venv` numerical packages. The repository venv was
  not modified. This is an explicitly supplemental environment, not proof that the
  original environment already supplied the new dependency.
- mypy 1.18.2 was downloaded into `/private/tmp/rk-record-typecheck` and exposed only
  to the type-check command via PYTHONPATH. Initial sandbox attempts failed on cache
  access/network availability; the isolated download succeeded with approved network
  access. No source change was used to evade those restrictions.
- The installed-wheel check builds from a temporary copy with setuptools 79.0.1,
  then installs the wheel into a fresh Python venv with only the record boundary's
  dependency subset. It confirms that LinkML, NumPy, pandas, Pint, Pyomo and Speckle
  are absent. It does **not** install/test all Rangekeeper dependencies or claim that
  the existing distribution metadata is already split into a minimal core extra.
- `uv.lock` now includes the new validation dependencies and previously unrecorded
  workflow/excel optional dependencies. No existing locked package version changed.
  [Lock result](lock.log). Python 3.11+ selects a different rpds-py version; only the
  Python 3.10 environment was executed here.

From the repository root, using the recorded temporary environments:

```sh
/private/tmp/rk-probe-audit-venv/bin/python docs/research/domain-migration/turn1/verify.py
```

For a fresh schema-check environment, install `tools/schema/requirements.txt`,
`mypy==1.18.2`, `pytest>=8,<9`, and `setuptools>=77` under Python 3.10. Then run:

```sh
python tools/schema/generate.py --check
python tools/schema/typecheck.py
python tools/schema/verify_native.py
PYTHONPATH=src python -m pytest --noconftest src/tests/test_records.py -q
python tools/schema/verify_install.py
```

The full historical numerical/graph baseline additionally needs the environment
recorded in [Step 1](../BASELINE.md). The runner accepts explicit Python paths and
`--typecheck-path`; pass an empty typecheck path when mypy is installed directly in
the schema environment. It expects precisely the two known baseline failures.

## Scope of evidence

Early logs without `final`/`verified` in their names are intermediate checks. The
final runner covers the delivered code. CI configuration runs regeneration, typing,
native/boundary/wheel checks and the seven schema suites, but has not run remotely.

No authoritative schema, fixture, existing test expectation, graph implementation,
consumer implementation or unrelated `.gitignore` content changed. Public facades,
resolvers, revision stores, independent numerical acceptance and execution remain
future work. No commit, push or release occurred.
