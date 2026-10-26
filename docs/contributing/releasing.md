# Release Rangekeeper

[ADR-018](../decisions/018-release-and-engineering.md) sets the release lines
and versioning. This page gives the procedure. [SECURITY.md](../../SECURITY.md)
shows the supported versions.

## Release lines and tags

| Line | Branch | Tags | Published by |
| --- | --- | --- | --- |
| 0.8.x maintenance | `support/0.8` | `v0.8.N` | the release workflow on `support/0.8` |
| 1.x pre-releases | `develop` or `main` | `v1.X.YaN`, `v1.X.YbN`, `v1.X.YrcN` | the release workflow |
| 1.x releases | `main` | `v1.X.Y` | the release workflow |

A tag is `v` followed by the exact PEP 440 version on PyPI, for example
`v0.8.72` or `v1.0.0a1`. Do not move or delete a tag after its release.

`support/0.8` gets bug and security fixes only. Its procedure, changelog and
the provenance of 0.8.69 to 0.8.71 are in
[RELEASING.md on `support/0.8`](https://github.com/daniel-fink/rangekeeper/blob/support/0.8/RELEASING.md).
A fix that applies to both lines needs a pull request into each branch.

## The release workflow

[`.github/workflows/release.yml`](../../.github/workflows/release.yml) runs when
a tag that starts with `v` is pushed. The same file is on `develop` and
`support/0.8`; GitHub runs the copy in the tagged commit.

1. **Plan.** It checks the tag format and that the tagged commit is on an
   allowed branch (see the table). Otherwise, it stops.
2. **Build.** It builds the sdist and wheel with `python -m build`, runs
   `twine check --strict` and checks that the file names contain the tag's
   version. It creates a GitHub build provenance attestation for each file.
3. **Import.** It installs the wheel on Python 3.12 and 3.13 and imports
   `rangekeeper`.
4. **PyPI.** It waits for approval of the `pypi` environment, then publishes
   by trusted publishing. PyPI also gets PEP 740 attestations.
5. **GitHub Release.** It creates the release with the files, the attestation
   bundle and the changelog section for the version
   ([`release_notes.py`](../../.github/scripts/release_notes.py)). If the
   changelog has no section, GitHub generates the notes. Pre-releases are
   marked as pre-releases.

A pull request that changes the workflow or its notes script runs steps 1–3
only, without publication. The workflow does not use TestPyPI; the import
check and the approval of the `pypi` environment come before publication.

## Release a 1.x version

1. setuptools-scm derives the package version from the tag, so no version
   change is necessary. On `develop` and `main`, only `v1.*` tags count; see
   [dependencies and versions](README.md#dependencies-and-versions).
2. In a pull request, write the changelog section from the fragments, then
   merge it:

   ```sh
   uv run --locked towncrier build --version 1.0.0a1
   ```
3. Tag the merged commit and push the tag:

   ```sh
   git fetch origin
   git tag -a v1.0.0a1 -m "Rangekeeper 1.0.0a1" origin/develop
   git push origin v1.0.0a1
   ```

4. Approve the `pypi` deployment in the workflow run.
5. Check the release on PyPI and GitHub.

If a step fails before PyPI, fix the cause on the branch, delete the tag and
tag again. If PyPI already has the version, release the next version instead.
PyPI does not accept the same file name twice.

## One-time setup

The maintainer does these steps once, for both release lines. The workflow
cannot publish until they are done. The environments and the PyPI trusted
publisher were set up on 2026-10-26.

### GitHub environments

In **Settings → Environments** of `daniel-fink/rangekeeper`:

1. Create the environment `pypi`. Under **Deployment branches and tags**,
   select **Selected branches and tags** and add the tag rule `v*`. Under
   **Deployment protection rules**, select **Required reviewers** and add the
   maintainer. Do not select **Prevent self-review**; with one maintainer, the
   maintainer approves their own release.

### PyPI trusted publisher

1. Sign in to pypi.org as an owner of `rangekeeper`.
2. Open <https://pypi.org/manage/project/rangekeeper/settings/publishing/>.
3. Under **Add a new publisher**, select **GitHub** and enter:

   | Field | Value |
   | --- | --- |
   | Owner | `daniel-fink` |
   | Repository name | `rangekeeper` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

4. Select **Add**.

### Vulnerability reports

Turn on **Private vulnerability reporting** in **Settings → Code security**.
[SECURITY.md](../../SECURITY.md) tells reporters to use it.

### After the first release

Remove the PyPI API tokens that were used for manual uploads
(<https://pypi.org/manage/account/token/>).
