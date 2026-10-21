# Semantic-export candidate: packaging amendment

Status: exact packaging extension released and locally verified, 21 October 2026.
The original proposal is preserved in packaging-1; Git delivery is not released. WW-51 remains the sole RK owner on
`feature/semantic-validation-read-cost`. Core remains read-only.

## Inputs and exact scope

Preserve experiment `final-manifest.json` SHA256
`7fd9ac4ab4a3c3208b6dc7c07177d1c2724889b55ace728739aba023b1cf24a3`,
`snapshot.json` SHA256
`60a689c2951eaf7450c27d43e145e2a27154969ed1a96c0c22b68abe92a1c0cd`,
all baseline/candidate sources, tests, helpers, results and earlier failed runs.
The four experiment files remain pinned by that manifest. This new proposal is
an explicit planning addition; do not overwrite the experimental manifest to add it.

Propose **0.10.0.dev5**, replacing dev4 only in:

- `pyproject.toml`: `[project].version`.
- `uv.lock`: the `[[package]]` entry with `name = "rangekeeper"` and editable
  source `"."`; only its `version` field changes.

Current local history, RK runtime/distribution artifact names and Core references
contain no dev5 use. Fresh `git ls-remote --heads --tags origin` confirms remote
`develop` is still `8c50e06bd045b1298da15be5be296a1150d2d339`, with no dev5 tag.
This is a repository/local artifact uniqueness check, not a registry-publication
claim. Recheck at activation and stop on a collision or competing owner.

The only runtime package change remains the reviewed `_validate` guard in
`src/rangekeeper/model/validation.py` (SHA256 `65cf657cc70a926fa56f67bbfdfbad289eb5dec1108c9abc83685e09b7326942`).
All 145 package files must remain byte-identical to the measured candidate.
There is no source `__version__` or other metadata edit. `README.md`, `LICENSE`,
`setup.py` and `MANIFEST.in` are immutable build inputs. Generated egg-info and
`rangekeeper-0.10.0.dev5.dist-info/{METADATA,WHEEL,RECORD,top_level.txt,licenses/LICENSE}`
are confined to the new build/artifact area; they are not repository edits.

Additional tracked paths are only the two version files above and this proposal.
The existing experiment README and research index may receive bounded packaging,
review and delivery notes after authorization. The new equivalence test remains
unchanged. No schema, generated source, dependency constraint or Core change.

## New runtime and operation sequence

Use a new `.runtime/graph-semantic-export-2026-10-21/packaging-1/` directory.
Proposed helpers, written and hashed before use:
`activate-packaging.py`, `build-wheel.py`, `check-wheel.py`, `wheel-tests.py`,
`freeze-packaging.py` and, only after later Git clearance, `delivery-receipt.py`.
All output folders are created exclusively; failures and numbered successors are
preserved. See the [packaging result](README.md#dev5-packaging-verification) for
the executed helpers, environments, one runner correction and exact artifact.

1. Activation records the current branch/HEAD, fresh remote refs, empty index,
   all tracked/protected hashes, old artifact hashes, experiment pins, exact helper
   sources, commands and interpreter. Include this proposal as an administrative
   addition. Before any version or administrative edit, save exact copies of all
   four experiment files and the original pyproject/lock under `packaging-1/preserved`.
   Pin those copies to the old experiment manifest and activation inventory, so
   its original README/index bytes remain verifiable after later packaging notes.
   Preserve walkthrough and gh-pages refs and every Interface preview.
2. Make exactly the two version substitutions. Require a byte diff of those two
   lines only. Parse both lock versions and prove the other **89 package entries**,
   RK requirements/markers/extras and all top-level lock metadata are identical.
   Run `uv lock --check --offline`; any other required lock change stops this window.
3. Use the pinned Python 3.12.3 interpreter recorded in the experiment environment
   receipt (resolved executable SHA256 `3c2d68354ddd4151e708de7103090a7c84def3ce6584f543d3ba3bd74615fb65`).
   Create `build-env` with `python -m venv --without-pip`. Copy the exact installed
   setuptools 80.9.0 and pip 24.0 payloads from the protected prior `.runtime/graph-read-cost-2026-10-21/schema-env`
   into this new environment using distribution RECORD inventories, with detached
   copies, original hashes and required metadata. Copy no RK package. No resolver,
   tool upgrade, old-environment install or network download is permitted.
4. Create `runtime-env` from the unchanged dependency selections with:
   `UV_PROJECT_ENVIRONMENT=<packaging-1>/runtime-env uv sync --frozen --offline --all-extras --group dev --no-install-project --no-install-package rangekeeper-examples --python <pinned-python>`.
   Record interpreter, all installed distribution versions/RECORD hashes and logs.
   Install neither local editable project: RK enters only through the exact wheel;
   examples are read through their source path for tests. Assert no RK distribution
   or editable RK path exists before step 7. Compare all other dependency versions
   against the experiment environment, explicitly excluding only RK and the local
   examples project from this dependency-only inventory. Stop on any other change.
   The old 76-distribution environment is read-only; neither source tree receives
   generated editable-install metadata.
5. `build-wheel.py` copies exactly the 145 pinned candidate package files and five
   build inputs to new `build-source`, with the approved pyproject version change.
   Exclude ignored `.DS_Store`, bytecode and caches by using the explicit tracked
   inventory; record exclusions. Do not copy an old build directory. From that
   stage run `<build-env>/bin/python -c 'from setuptools.build_meta import build_wheel; build_wheel("<absolute-candidate-dir>")'`.
   The sole wheel is `rangekeeper-0.10.0.dev5-py3-none-any.whl`; record bytes and SHA256.
6. `check-wheel.py` rejects duplicate/unsafe archive paths, verifies every RECORD
   digest/size and exact package membership, then matches all 145 payload hashes
   to the frozen measured candidate. Compare dev4/dev5 metadata: name, Python range,
   requirements, extras, license and build tag are unchanged; version and dependent
   dist-info paths/RECORD entries are the only intentional differences. Require
   no examples, environments, build caches or undeclared files in the artifact.
7. Install that exact wheel only into the new runtime:
   `uv pip install --python <runtime-env>/bin/python --offline --no-deps --reinstall-package rangekeeper <absolute-wheel>`.
   Verify installed metadata version, wheel digest and every installed RK payload.
   Recheck non-RK environment inventory. No Core adoption or shared installation.

## Exact-wheel checks and independent artifact review

Run serially, with pinned source/tests and no concurrent source edits. Set
`PYTHONDONTWRITEBYTECODE=1`, `MPLBACKEND=Agg`, and new packaging-local TMPDIR,
MPLCONFIGDIR and PYSTOW_HOME paths. Preserve complete commands, exit codes and logs.

- Run unchanged `tools/schema/verify_install.py --wheel <exact-wheel>` with the
  new build interpreter and the new runtime interpreter for `--runtime-python`,
  `--financial-python`, `--execution-python` and `--tables-python`. These are exact
  installed-artifact slices; no artifact rebuild or old-environment mutation.
- `wheel-tests.py` runs these unchanged files through the installed package:
  `test_model_validation_equivalence.py`, `test_structural_validation_equivalence.py`,
  `test_model_inspection.py`, `test_records.py`, `test_record_behavior.py`,
  `test_domain_model.py`, `test_reference_identity.py`, `test_validation_composition.py`,
  `test_domain_io.py`, `test_scenario_contracts.py` and `test_scenarios_policies.py`.
  Use `pytest -q -p no:cacheprovider --import-mode=importlib -o pythonpath=examples --basetemp <new-dir>`.
  Remove checkout `src` from process/environment import paths; retain only examples
  as necessary. Assert package origin before tests and every loaded RK module
  afterwards; check after collection and after tests that checkout `src` is absent from sys.path. Child tests use the new installed interpreter and inherit the same
  source-free environment. Record their scope; no source test is relabelled as wheel evidence.
- Through that installed wheel, read each unchanged full primary/growth fixture
  twice and verify both exports against the same compact oracle and input hashes.
  Record correctness and origin; do not reuse these checks as new paired timing
  evidence or a Core five-second result.
- Run Black check on the two changed Python files, documentation and `git diff
  --check`. The 140 equivalence/1,248 full source passes remain valid only if their
  source/test pins match. Version-only packaging does not require repeating
  generation, seven conformance suites or .NET work: no schema/generated/native
  files change. Stop and amend the scope if a broader change becomes necessary.

`freeze-packaging.py` produces a new packaging manifest, never replaces the
experiment manifest. Pin all proposed delivery files, 150 build inputs, 145 wheel
payload files, exact artifact/version, installed metadata, commands/helpers/tests,
receipts, dependency comparisons, exclusions, failures, source equivalence and
all tracked/protected files outside scope. Independent review must check exact
wheel contents and imports, test results, documentation, original refs and index.
Send that complete artifact packet to the coordinator **before Git staging**.

## Separate scoped delivery and downstream gate

Only after artifact review and explicit delivery clearance: stage the exact seven
paths (the original four, this proposal, pyproject.toml and uv.lock), verify staged
blobs against the approved manifest, commit on the existing feature branch,
integrate into `develop` using the shared workflow and push the scoped branches.
No force push, broad staging, cleanup, worktree or publication. Record source/merge
commits, tree equality, exact committed path/blob hashes, wheel/manifest hashes,
fresh live remote equality, clean primary checkout on develop, unchanged protected
refs/evidence and explicit ownership release. Preserve the wheel in ignored runtime
for a later independently released Core vendor/lock/environment window.

Packaging accepts neither capacity nor deployment. Growth RK first-read median
remains 7.224 seconds; the latest delivered Core growth read failed at 5.016 seconds
under the former rule. The user now permits a longer finite initial load and
requires responsive graph interactions. The 1024/1024 target, full properties and
provenance, matched browser/private-state reopen and actual-host gates remain.
A separately reviewed Core/Interface opening-budget amendment will implement that
new decision. Existing deployment/live approval gates still apply.

## Deferred validation repair leads: read-only ranking

This ranking preceded the user's longer-initial-load decision. Keep it as retained
analysis only; no walker, parser or validator experiment is released or needed
to satisfy the former five-second rule.

Evidence is the retained `graph-read-cost-2026-10-21/a-profile-primary-1/read.prof`,
`read.txt` and source inventory, cross-checked against current source. It predates
exact lookup and the semantic-export candidate; its 7.119-second profiled primary
run is an attribution guide, not a new timing or a saving prediction. Do not add
parent cumulative times to their children, or scale profiled costs into an
unprofiled 1024 result. The latest growth first-read gap is at least 2.224 seconds
before Core overhead.

1. **Recommend selective recorded-unit traversal as the next bounded experiment.**
   The second full `walk` subtree costs 0.380974 seconds cumulatively in the retained
   profile. This is separate from identity indexing (0.372519 seconds), which must
   remain complete. Target only `schema/index.py` for a private schema-directed
   selective walker/reachability map, `model/validation.py:recorded_unit_issues`
   for consumption and new `src/tests/test_unit_validation_traversal.py`. Preserve
   the exact ordered sequence obtained by filtering the current exhaustive walk
   to Domain, Measure, Quantity, Flow and Value. Use a fixed point over all declared
   embedded-record options, including recursive and union fields; prune only fields
   that cannot reach a target. Preserve parent-before-child order, original paths,
   anonymous records, null/empty presence and generated-record ownership. References
   and opaque content remain opaque. Do not skip Provenance by name: scenario
   branches can contain units. Unknown/subclass forms must retain the exhaustive
   path until equivalence is proved. Keep unit parsing, compatibility, prerequisite
   reference validation and every ordered issue unchanged. Compare a frozen full
   walker/issue oracle, including custom UnitSystem behavior and multiple faults,
   before paired full-fixture trials. A new exact helper/runtime/protection proposal
   is required; this paragraph does not activate the experiment. The 0.380974
   subtree includes field decoding and must not be added to those costs again.
2. **Parser allocation removal needs a stronger semantic proof first.** The JSON
   codec's preliminary strict-copy subtree costs 0.255890 seconds, separate from
   the constructor's required copy. Exact scope would be `io/json.py:_parse` and
   new `src/tests/test_json_parse_equivalence.py`; no constructor/runtime shortcut.
   The standard decoder creates fresh builtin containers and string keys. A
   deferred `parse_float` overflow flag might remove this whole copy while keeping
   duplicate-key, syntax and non-JSON-constant errors ahead of overflow rejection.
   However, the old recursive copy can raise RecursionError before an overflow or
   before later construction. Falling back when overflow is seen does not preserve
   finite deep-input failures. There is no proved decoder-depth fallback yet.
   Keep this below the walker until acceptance, exception family/message/cause and
   error precedence are proved, including deeply nested opaque content. No alternate
   decoder, monkeypatch support claim or validation bypass is implied.
3. **Supported validator keyword preparation is a smaller, uncertain lead.**
   `schema/validation.py` and `test_structural_validation_equivalence.py` would
   be the exact paths. jsonschema `__attrs_post_init__` costs 0.212807 exclusive
   seconds across all calls; keyword-list construction is only part of that cost.
   Resolver and scope setup also contribute; the removable share is unknown. Public
   `create(applicable_validators=...)` could retain immutable schema keyword tuples;
   stock assertions, scope guards, ordering and unknown-schema fallback must stay.
   It does not remove stock `descend` or evolved-validator construction. The
   explicit `if` evolve subtree is only 0.090792 cumulative seconds and overlaps
   this work; do not sum it as a separate large saving.

The dominant structural `_validate_json` subtree is 3.745 profiled seconds.
Stock `descend` and `evolve` self times are 0.499163 and 0.431987 seconds; those
are inside that subtree, not extra savings. No supported prepared-descend API has
been established. Copying dependency internals, replacing the validator, changing
schemas/diagnostic multiplicity or reducing checks is outside the allowed repair.
A substantive change there needs a separate supported upstream/API investigation
and exact dependency proposal. The unit-registry cold subtree (0.824340 seconds)
is also not a removable traversal cost; prewarming does not satisfy a cold-read gate.

The selective walker remains the strongest bounded local lead in this analysis,
but is now deferred. Prioritize the complete embedded experience under a finite
opening budget and measure interactions separately. Preserve the full fixtures
and all former failures; do not treat a longer opening as evidence of fast interaction.
