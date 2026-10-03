# Scalar execution checkpoint: observed evidence

Verified 2026-10-03 Australia/Sydney, from `acausal-modelling` at
`53f5d3e72f97b7099bcc7973386ba47ccb4b7784`. Step 5 is implemented in
`src/rangekeeper/execution/`; see the [API and capability guide](../../SCALAR_EXECUTION.md).
This is local implementation evidence; no commit, push, remote CI run or consumer
migration is claimed. The starting checkout had only the unrelated `.gitignore`
edit, preserved byte-for-byte.

## Actual valuation results

The [example script](../../../tools/execution/valuation.py) loads only the input
Model and Specification fixtures. It executes forward, revises Specifications to
pin that genuine output, executes inverse, and executes a sequential two-case batch.
It does not load synthetic expected-output Models or Runs.

| Observed quantity | Forward | Inverse on the forward output |
| --- | --- | --- |
| Capital value | 11,000,000 AUD | Assigned 10,000,000 AUD |
| Annual rent per dwelling | Assigned 30,000 AUD/dwelling/year | 27,500 AUD/dwelling/year |
| NOI | 550,000 AUD/year | 500,000 AUD/year |

Inspect the [summary](observed/summary.json), [forward Run](observed/run-forward.json),
[forward Model](observed/model-forward.json), [inverse Run](observed/run-inverse.json),
[inverse Model](observed/model-inverse.json) and [batch Run](observed/run-batch.json).
The [revision directory](observed/revisions) includes every referenced input,
Specification revision, child Run and accepted output needed for current validation.
UUIDs and timestamps vary on reproduction; numerical acceptance, lineage, declarations,
status and accounting are the reproducible assertions.

The observed forward output is `1c9dbb73-d5ab-4fa5-83fc-ad42c9bf7825`.
The inverse output is `0c3b8ef2-a7bc-4b12-a754-cf1dc10ef4e1`, a revision of that
actual forward output. Each Run records actual versions, settings, termination,
row scaling, iteration count, timing and independent dimensional residuals.

## Verification results

| Check | Observed result | Evidence |
| --- | --- | --- |
| Baseline before implementation | 702 passed, two failures, 704 executed | [log](baseline.log), [JUnit](baseline.xml) |
| Final local Python suite | **745 passed, the same two failures**, 747 executed; no skips/errors | [log](pytest.log), [JUnit](pytest.xml) |
| New scalar execution coverage | **43 passed**, included in the final suite | [tests](../../../src/tests/test_execution.py) |
| Generated artifacts | Fresh, no source changes | [log](generation.log), [fingerprints](verified-sources.json) |
| Static API checks | 66 source files pass; 8 record, 6 domain, 5 IO and 4 execution examples rejected as intended | [log](typing.log) |
| Native immutable record equivalence | Passed | [log](native.log) |
| Seven existing schema suites | All pass, with unchanged cases and expectations | Logs below |
| Isolated installed wheel | Lightweight imports; core and units/codecs/stores; missing-backend behavior; genuine process-isolated forward/inverse execution and disk publication all pass outside checkout | [log](installed.log) |
| Preservation | 201 protected existing files unchanged; 259 verified source fingerprints current; all 113 prior lock entries retain versions, only Pyomo/Highspy added | [report](preservation.json) |

The two failures reproduced before and after implementation are:

- `tests/test_adapters.py::test_supported_adapter_and_table_surfaces_are_explicit`:
  legacy adapter `__all__` differs from its existing expected list.
- `tests/test_formulas.py::TestSolver::test_residual`: legacy numerical result
  `239654.64258295443` differs from the existing expected `241049.33`.

Neither legacy implementation nor its expectations was edited. Three live-service
tests in `tests/test_api.py` were excluded, as in the baseline. External projects,
Speckle/host integrations, other platforms and remote CI remain unverified.

Schema-suite evidence is [validate](schema-validate.log),
[native round trip](schema-native_roundtrip.log), [expressions](schema-expressions.log),
[formulations](schema-formulations.log), [Models](schema-models.log),
[Specifications](schema-specifications.log) and [Runs](schema-runs.log).
These preserved checks still describe their own bounded/synthetic scope; some
legacy terminal messages say execution is unimplemented. They do not invoke the
new adapter, whose evidence is recorded separately here.

Execution tests cover changed inputs and declared operators, real output reuse,
unit conversion, bounds, infeasibility, underdetermination, unsupported operations,
missing roles, original-expression rejection of a forged solver candidate, checking
after serialization, immutable definitions/provenance, nested mixed batches,
settings accounting, actual iteration-limit termination and killing/reaping a
stalled worker. Constant-only mathematics, unconstrained Values, conjunctions,
affine powers/division, nonfinite candidates and malformed references are included.

## Environment and reproduction

The local runtime is Python **3.10.19**, macOS **15.7.9 arm64**, with Pyomo
**6.10.1**, Highspy/HiGHS **1.15.1**, NumPy **2.2.6**, Pint **0.24.4** and
PyYAML **6.0.3**. The schema environment uses LinkML **1.11.1**,
linkml-runtime **1.11.1** and jsonschema **4.26.0**. Mypy is **1.18.2**.
[Runtime inventory](environment.log) and [schema inventory](schema-environment.log)
record actual versions and import location. No packages were installed into
`src/.venv`; the added backend lives in a temporary supplemental environment.

The local paths below identify this verification's environments, not portable
runtime requirements:

- `/private/tmp/rk-scalar-runtime/bin/python`: new venv, with `.pth` access to the
  preceding supplemental runtime and `src/.venv` packages; Pyomo/Highspy added here.
- `/private/tmp/rk-probe-audit-venv/bin/python`: pinned schema/code-generation tools.
- `/private/tmp/rk-record-typecheck`: supplemental mypy installation.

From the repository root:

```sh
python3 docs/research/scalar-execution/verify.py \
  --schema-python /private/tmp/rk-probe-audit-venv/bin/python \
  --runtime-python /private/tmp/rk-scalar-runtime/bin/python \
  --typecheck-path /private/tmp/rk-record-typecheck
```

For a fresh machine, prepare separate Python 3.10 environments: install
[`tools/schema/requirements.txt`](../../../tools/schema/requirements.txt),
`mypy==1.18.2` and `setuptools>=77` in the schema environment; install the repository
package with `[execution,yaml,workflow]` in the runtime environment. To reproduce
the recorded legacy test results precisely, also match the retained runtime
dependency inventory. Point `--typecheck-path` to the schema environment's
site-packages when mypy is installed there. The runner checks that the only full-suite
failures are the two names above; a changed environment may require investigating
different results rather than treating that expectation as a portable guarantee.

The runner records exact argv, working directory, selected environment variables,
exit status, duration and log path in [commands.jsonl](commands.jsonl). Python tests
run from `src`; schema and packaging tools run from the root. Matplotlib uses `Agg`
and temporary cache paths. Packaging, generated artifacts and installed checks use
isolated temporary output directories. Repeated verification preserves previous logs
and chooses a fresh observed-output directory.

[Initial fingerprints](initial.json), [verified source fingerprints](verified-sources.json)
and [preservation report](preservation.json) retain the input/change boundary.
The authoritative LinkML YAML, generated records/artifacts, existing schema checks,
fixtures, legacy graph code and existing tests were unchanged. New execution files
were observed staged during the session; the implementation did not issue Git index,
commit or push commands. Review the final working tree when preparing a commit.

Because repository rules ignore `.log` files, [evidence.tar.gz](evidence.tar.gz)
also retains all local logs, JUnit files and verification manifests for later
delivery. Extract it into a temporary directory when those loose logs are absent.

## Development findings and remaining limits

The initial Pyomo probe confirmed the modern `Highs` interface, explicit solution
loading and public iteration/status evidence; [backend-probe.json](backend-probe.json)
retains its numerical result. The adapter uses no private solver model to extract
the candidate. Version pins are intentional because this interface was tested at
these versions. Primary references: [Pyomo release](https://pypi.org/project/pyomo/6.10.1/),
[Highspy release](https://pypi.org/project/highspy/1.15.1/) and
[HiGHS options](https://ergo-code.github.io/HiGHS/dev/options/definitions/).

Development logs are retained separately from the final passing run. Early new-test
failures included an over-broad comparison of Formulation Values whose quantities
were expected to change, a missing Measure name in a new fixture, and an installed
import assertion that incorrectly excluded NumPy after Pint had performed unit
operations. Those test assumptions were corrected without changing old expectations.
An initial iteration fixture was eliminated by presolve, so the final deterministic
two-variable bounded problem verifies a real one-iteration limit instead.

A larger 16-variable dense expression fixture was interrupted after approximately
227 seconds in JSON Schema validation before solving. It is retained in the
development log, not counted as a final pass or a HiGHS failure. Large expression
trees need future validation-performance work. The worker has an enforced deadline;
the entire synchronous API call does not, including reference preflight,
document validation, acceptance and persistence.

This checkpoint solves **affine feasibility** after explicit assignments. It does
not implement ordered optimization objectives, nonlinear unknown products, rich
temporal content, imposed queries or Specification-local Value publication.
Generic `relative_tolerance` is explicitly reported unapplied, not mapped to an
unrelated absolute solver tolerance. Independent acceptance has its own documented
dimensional policy. No uniqueness or preference-optimality claim is made.

Step 6 is graph/consumer migration under the [migration map](../../DOMAIN_MIGRATION_MAP.md).
