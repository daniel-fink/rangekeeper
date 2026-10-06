# MiniZinc acceptance — 6 October 2026

The optional solver gap is closed on this Mac. Strict layout acceptance reports
**92 passed, zero skipped**, including all 24 cases previously skipped for
MiniZinc. The production layout model, geometry checks, scores, assertions and
solver deadlines are unchanged.

## Changes

- Installed the official MiniZinc 2.10.1 Apple Silicon bundle with CP-SAT 9.15 at
  `/Users/daniel/Applications/rk-minizinc-2.10.1`. Its archive matches the SHA-256
  published in the release metadata. `installation.json` records the source,
  hash and path. The adjacent `env.sh` sets `RK_MINIZINC` for a shell; no shell
  startup file was changed.
- Added checksum-pinned macOS and Linux bundle setup in
  [`tools/layout/`](../../../../tools/layout/README.md). Z3 remains the declared
  optional `z3-solver==5.1.0.0` dependency. Runtime package requirements and locks
  were not changed in this task.
- Replaced per-file solver detection with the shared `tests.layout_support`
  plugin. Both environment and PATH discovery use the production toolchain check.
  The two saved-layout tests now accept PATH discovery too. Ten new checks cover
  discovery, absent CP-SAT, cached failures, optional skips, strict preflight and
  rejection of runtime/collection skips.
- Added `tools/layout/verify.py` and the dedicated `Layout acceptance` CI workflow.
  Strict acceptance checks pinned versions, selects all layout test files and
  rejects every skip. It retains metadata, source hashes, commands, counts,
  timings, raw output and JUnit results.

## Evidence

| Check | Result | Record |
|---|---|---|
| Existing layout tests in the retained full runtime | 82 passed, zero skipped | `attempt-1/result.json`, `attempt-1/results.xml` |
| Final strict layout run in the repository `.venv` | 92 passed, zero skipped; 47.41 seconds in pytest | `accepted/result.json`, `accepted/results.xml`, `accepted/pytest.txt` |
| Full local regression with strict solver checks | 1,097 passed, zero skipped; 249.84 seconds | `full-suite.txt`, `full-suite.xml`, `verification.json` |
| Explicit nonexistent MiniZinc path | Failed preflight with exit 1 as required | `missing-tool/result.json`, `missing-tool/preflight.txt` |
| Linux bundle digest, extraction and CP-SAT version | Passed; version 9.15 | `installer-checks.json` |
| Installer rejects corrupt input and an existing destination | Passed | `installer-checks.json` |
| Python formatting and changed-file whitespace | Passed | Local Black check and `git diff --check` |
| CI workflow syntax | Parsed locally | `.github/workflows/layout.yml` |

`baseline.json` records HEAD `305f3ff`, the pre-existing dirty state and starting
hashes. Existing migration changes, `.gitignore` and the Syncthing conflict copy
were preserved. The final runner hashes its test and layout inputs in `result.json`.

The first repository-environment attempt, retained under `final/`, failed before
tests because that environment lacked `jsonschema`. The declared core, layout
and workflow test dependencies were then installed; `accepted/` is the successful
rerun. This was an environment problem, not a solver or geometry failure. The
separate retained full runtime already had those dependencies.

The sandbox initially blocked downloading and mounting the installer and the
package installer needed host access. The authorized operations succeeded with
host access. The disk image was mounted read-only and detached after copying.
No application was launched and no service data was sent.

## Reproduction and limits

From the repository root, using a new output directory:

```sh
. "$HOME/Applications/rk-minizinc-2.10.1/env.sh"
src/.venv/bin/python tools/layout/verify.py --output /tmp/rk-layout-next
```

The full regression command ran from `src/` in the retained complete runtime:

```sh
RK_MINIZINC=/Users/daniel/Applications/rk-minizinc-2.10.1/MiniZincIDE.app/Contents/Resources/minizinc \
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/private/tmp/rk-minizinc-full-mpl \
/private/tmp/rk-full-runtime/bin/python -m pytest -q --require-layout-solvers \
  --ignore=tests/legacy/test_api.py -p no:cacheprovider \
  --junitxml=../docs/research/full-migration/minizinc/full-suite.xml \
  > ../docs/research/full-migration/minizinc/full-suite.txt 2>&1
```

Use new evidence paths when repeating it. The three excluded live service tests
are not included in the 1,097 passing count.

See the [setup and acceptance guide](../../../../tools/layout/README.md) for a new
machine. The runner ignores inherited `PYTEST_ADDOPTS` and does not change the
global environment. Ordinary tests can still skip absent optional solvers;
`--require-layout-solvers` makes such gaps fail acceptance.

Linux archive extraction and its solver configuration were checked on this Mac.
The Linux binaries and GitHub-hosted job have not been executed here. A push will
trigger that job; the workflow addition is not a claim that remote CI has passed.
The three predecessor service tests and the Windows connector gate remain separate.
Previous records with 24 skips remain accurate historical evidence. No commit,
push, package release or external publication was performed.
