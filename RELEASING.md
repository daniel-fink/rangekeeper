# Releasing 0.8.x

`support/0.8` is the maintenance branch for the 0.8 line. It gets bug and
security fixes only; see [SECURITY.md](SECURITY.md). The 1.x line is on
`develop` and `main`.

## Changes on this branch

1. Start a `fix/<name>` branch from `support/0.8`.
2. Make the fix, add a test and add an entry under the next version in
   [CHANGELOG.md](CHANGELOG.md).
3. Open a pull request into `support/0.8`.
4. If the fix also applies to 1.x, open a separate pull request into `develop`.

Do not merge `develop` into `support/0.8`, or `support/0.8` into `develop`.

## Release a version

The [release workflow](.github/workflows/release.yml) publishes a version when
a `v0.8.N` tag is pushed. The tag must point to a commit on `support/0.8`.

1. In a pull request into `support/0.8`:
   - set `version` in [`src/pyproject.toml`](src/pyproject.toml) to `0.8.N`;
   - run `uv lock` in `src/`;
   - replace `(unreleased)` with the date in the `0.8.N` heading of
     [CHANGELOG.md](CHANGELOG.md).
2. Merge the pull request.
3. Tag the merge commit and push the tag:

   ```sh
   git fetch origin
   git tag -a v0.8.N -m "Rangekeeper 0.8.N" origin/support/0.8
   git push origin v0.8.N
   ```

4. The workflow builds the sdist and wheel, runs `twine check` and imports the
   wheel on Python 3.12 and 3.13.
5. Approve the `pypi` deployment in the workflow run. The workflow publishes to
   PyPI and creates the GitHub Release with the changelog section, the files and
   the attestation bundle.

If the tag does not match the package version, or the commit is not on
`support/0.8`, the workflow stops before it publishes.

The one-time PyPI and GitHub environment setup is in the
[release guide on `develop`](https://github.com/daniel-fink/rangekeeper/blob/develop/docs/contributing/releasing.md).

## Build locally

```sh
cd src
uv build --out-dir ../dist
uvx twine check --strict ../dist/*
```

`src/pyproject.toml` pins setuptools 82.0.1, so a local build and a workflow
build give the same package files.

## Provenance of earlier releases

Before 0.8.72, releases were built and uploaded from a local working copy.
For 0.8.70 and 0.8.71 the version bump and the last change were committed
after the upload. On 2026-10-26 the published files were compared with the
rewritten history:

| PyPI version | Uploaded (UTC) | Commit | Result |
| --- | --- | --- | --- |
| 0.8.69 | 2025-12-02 10:33 | `22d1a2f` | Same package files and version |
| 0.8.70 | 2026-03-19 12:48 | `a2c5245` | Same package files and version |
| 0.8.71 | 2026-03-19 12:54 | `4b6df47` | Same sdist and wheel contents |

Method for 0.8.71:

1. Download `rangekeeper-0.8.71.tar.gz` and
   `rangekeeper-0.8.71-py3-none-any.whl` from pypi.org and check their SHA-256
   digests against the PyPI JSON API:
   - sdist `4de724096ea7c278…`;
   - wheel `ce870f8754d4ea53…`.
2. Build `src/` at `4b6df47` with `uv build`.
3. Compare the extracted files. All sdist files are the same. All wheel files
   are the same, except the `Generator` line in `WHEEL` (setuptools 82.0.1 on
   PyPI, a newer setuptools locally) and its hash in `RECORD`.

Commit `21107f0`, the last commit on `main`, does not match 0.8.70 or 0.8.71:
it does not have the `Flow.resample()` fix, the version bump or the
`to_decimal` change. `support/0.8` therefore starts at `4b6df47`, which
contains `21107f0`.

The test suite at `4b6df47` with its lock file has three failures on Python
3.12 and 3.13: two tests need a Speckle token and network access, and
`test_formulas.py::TestSolver::test_residual` fails on both versions. These
failures exist in 0.8.71 and do not depend on the Python version.
