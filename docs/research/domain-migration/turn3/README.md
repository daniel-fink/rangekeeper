# Turn 3 — finalized Runs, interchange and revision storage

Implemented and verified locally on 2026-10-02. Work units **3C and 4** complete the
three implementation turns following the domain migration baseline. Read the
[public API guide](../../../reference/run-and-storage.md) for interfaces, examples, error
behavior and publication guarantees. The next implementation checkpoint is Step 5,
scalar execution with Pyomo/HiGHS; no new-schema executor ran during this work.

## Scope and environment

- Frozen Run facade over generated records, local and resolver-based validation.
- Strict JSON/YAML codecs and immutable memory/directory revision stores, including
  conflict detection, atomic no-overwrite publication and Run dependency validation.
- Public `rangekeeper.Model`, `Specification`, and `Run` exports; YAML optional extra;
  static typing, packaged resources and installed-core verification.
- Branch `acausal-modelling`, HEAD `c91a76c941bac0a26fa18ad5a3105ab4641f22f0`.
  No commit, push or staging operation was performed. Existing dirty work was retained.
- macOS 15.7.9 arm64, Python 3.10.19. Schema environment:
  `/private/tmp/rk-probe-audit-venv/bin/python`, with LinkML **1.11.1**,
  linkml-runtime **1.11.1**, jsonschema **4.26.0**, PyYAML **6.0.3**.
  See the [schema environment](environment-final-1790914269322713000.log).
- Local tests use `/private/tmp/rk-domain-runtime/bin/python`, the existing isolated
  supplemental environment, with Pint 0.24.4 and py-moneyed 3.0. Exact versions,
  platform and import location are in [runtime-environment-final.log](runtime-environment-final.log).
  `src/.venv` was not changed. Static checks use mypy 1.18.2 from
  `/private/tmp/rk-record-typecheck`.
- Cache/output overrides keep generation, wheels, pytest files, plotting and PyStow
  writes isolated. No live services were called. No applicable AGENTS.md was found.

## Results

| Check | Final observed result | Evidence |
| --- | --- | --- |
| Local pytest suite | **702 passed, 2 failed**, 704 executed; no skips or collection errors | [log](pytest-final-1790914315075444000.log), [JUnit](pytest-final.xml) |
| Domain boundary within pytest | **211 passed**: 41 records, 24 composable validation, 20 Model, 21 Specification, 22 Run, 83 IO | Same JUnit report |
| Generated artifact freshness | Passed; generated bundle unchanged | [log](regenerate-check-1790914269455033000.log) |
| Static typing | 52 source files passed; 8 record, 6 domain and 5 IO intentional misuses rejected | [log](typing-verified-1790914271298899000.log) |
| Native record comparison | Passed | [log](native-verified-1790914273531504000.log) |
| Isolated installed wheel | Public roots, all 16 document fixtures, composition, codecs, both stores and import boundaries passed outside checkout | [log](installed-verified-1790914274097250000.log) |
| Public guide example | Complete synthetic failed Run example passed | [log](guide-examples.log) |

The **105 new Run/IO tests all pass**. Coverage includes nested immutability,
explicit root kinds, malformed/ambiguous JSON and YAML, duplicate keys, typed versus
opaque scalar preservation, omission/null/empty, ordered mathematics/objectives/trace,
revision identity/kind conflicts, wrong resolver identities, Run trees, output
references, corrupt storage, concurrent identical/conflicting puts, injected IO
failure, and a real subprocess crash before publication followed by a successful retry.

The same two pre-existing failures remain:

1. `tests.test_adapters::test_supported_adapter_and_table_surfaces_are_explicit`:
   legacy adapter exports do not match the test's expected surface.
2. `tests.test_formulas.TestSolver::test_residual`: observed residual
   `239654.64258295443` versus expected `241049.33`.

The [original narrow reproduction](../evidence/pytest-failure-reproduction.log) and
[validation-refactor verification](../validation-refactor/README.md) establish their
baseline status. No existing assertion was changed. The only existing test edit
renames the low-level Run validator import to `validate_records`.
The three live Speckle tests in `tests/test_api.py` were excluded and remain unverified.

### Seven existing schema suites

All pass with unchanged schema inputs and conformance expectations:

| Suite | Reported coverage | Evidence |
| --- | --- | --- |
| Core | 13 schemas, both examples, 80 rejection cases | [log](schema-validate-final-1790914287839073000.log) |
| Native round trips | Typed identifiers/references and both examples | [log](schema-native_roundtrip-final-1790914289589895000.log) |
| Expressions | 71 valid, 103 structural and 31 semantic rejections | [log](schema-expressions-final-1790914290795365000.log) |
| Formulations | 10 valid, 32 structural and 20 semantic rejections, 10 round trips | [log](schema-formulations-final-1790914293523018000.log) |
| Models | 6 valid, 26 structural and 24 semantic rejections, 6 round trips | [log](schema-models-final-1790914295924495000.log) |
| Specifications | 17 valid, 46 structural and 37 semantic rejections, 17 round trips; composition 13 accepted, 35 rejected, 4 additional round trips | [log](schema-specifications-final-1790914298782098000.log) |
| Runs | 18 valid cases, 28 structural and 45 semantic rejections, 31 round trips | [log](schema-runs-final-1790914302734773000.log) |

Counts overlap; they are not a unique-case total. Run local validation extracts and
reuses existing report/status checks. Resolved validation still delegates to the
same bounded conformance rules. Synthetic fixtures do not establish equation
satisfaction, optimality, reproducibility or authentic execution.

## Reproduction and retained evidence

From the repository root, using the environments documented above:

```sh
python3 docs/research/domain-migration/turn3/verify.py \
  --schema-python /private/tmp/rk-probe-audit-venv/bin/python \
  --runtime-python /private/tmp/rk-domain-runtime/bin/python \
  --typecheck-path /private/tmp/rk-record-typecheck
```

[verify.py](verify.py) runs generation, typing, native comparison, installed-wheel
acceptance, all seven schema suites and pytest. It requires exactly the two known
failing test identities; unexpected failures stop the run. Temporary environment
paths can be replaced using its arguments. The schema environment requires the
pinned tooling plus setuptools >=77 and pip; the runtime environment requires the
repository's local test dependencies, Pint and PyYAML. No environment is silently
installed or modified by the runner.

[verification-commands.jsonl](verification-commands.jsonl) records exact argv, working
directories, environment overrides, exit codes, durations and output names. The latest
timestamped logs linked above are the final full verification after the malformed
explicit-YAML-boolean regression was added. Earlier unsuffixed logs retain the prior
successful run; `installed-development.log` retains an earlier wheel check. The JUnit
file and [final-fingerprints.json](final-fingerprints.json) describe the final run.
Repeated verification appends logs and replaces the final XML/fingerprint snapshot.

The lockfile was refreshed from `src/` with
`UV_CACHE_DIR=/private/tmp/rk-record-uv-cache /Users/daniel/.local/bin/uv lock --offline`.
The restricted attempt failed in uv's macOS configuration lookup; the approved
retry succeeded. All **113 package name/version pairs remain unchanged**; only YAML
optional-extra metadata was added. No numerical backend dependency was introduced.

## Preservation and practical limits

[initial.json](initial.json) retains HEAD, starting index entries and 319 input
fingerprints. [preservation.json](preservation.json), reproduced by
`python3 docs/research/domain-migration/turn3/preserve.py`, compares those inputs,
the verified final source hashes, lock versions and existing test contents.
Authoritative schemas, fixtures, generated records, schema checks, legacy graph and
numerical implementation, and the unrelated `.gitignore` edit remain unchanged.
Documentation, the named domain/IO integration points, test/tooling additions and
optional YAML metadata account for the intended changes.

During this turn the Git index lost 25 pre-existing staged entries through activity
outside these implementation commands. The working files remain present; the index
was neither restored nor otherwise modified by this work. Validation describes the
working tree, not staged snapshots.

Installed-wheel tests use a fresh isolated venv with the needed declared core
dependencies copied in: first without Pint/PyYAML for unit-free operations, then
with those dependencies for all fixtures. This proves the installed core can work
without importing legacy graph, plotting, service or solver packages. It does not
claim a normal full-dependency installation was exercised or remove existing legacy
dependencies from package metadata. Remote CI, external consumers and other operating
systems/filesystems remain unverified.

Filesystem guarantees are bounded to atomic no-overwrite hard-link publication and
file/directory sync where supported. The tests exercise local concurrency and a
process crash, not power-loss durability or a multi-document transaction. An error
after linking may leave a complete revision; retries are idempotent. Direct external
file edits/deletion are outside the immutable-store contract.

The core is ready for the next checkpoint. Step 5 must verify/pin Pyomo with HiGHS,
solve the declared scalar equations in both directions, independently accept candidates,
reuse a genuine forward output, and publish authentic Runs and output Models. Expected
values remain 11 million AUD forward and 27,500 AUD per dwelling per year inverse.
