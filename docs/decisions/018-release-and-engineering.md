# ADR-018: Release lines, versioning and engineering practice

Status: accepted for 1.0; release lines, pre-releases, versions, changelog and CI implemented (1.0.0a1, 1.0.0a2); docs site build implemented (#191), publication pending; structure guardrails and the strict typing ratchet implemented (#400). Recorded: 2026-10-26.

## Problem

- **No reproducible releases.** PyPI has 0.8.x releases that no commit
  reproduces exactly.
- **No upper bound for 0.8.x users.** Downstream applications that use 0.8.x
  have no upper version bound, so a 1.0 release on PyPI would replace their version.
- **No release tooling.** There is no release workflow, changelog or single
  version source.
- **Narrow CI.** CI runs only pytest, on one operating system and one Python version.
- **Repository content.** The history contains third-party copyrighted files.
  The docs contain evidence dumps and the names of unrelated private projects.

## Choice

### Release lines

- **`support/0.8`** starts from the last 0.8 commit, after the history rewrite.
  It receives only bug and security fixes, until an announced end of life.
  `SECURITY.md` shows the supported versions.
- **`develop` and `main`** carry 1.x. `main` receives 1.0.0 from `develop`.
- **Pre-releases:**
  - 1.0.0a1: structure;
  - 1.0.0a2: foundations;
  - 1.0.0b1: API and format freeze;
  - 1.0.0rc1: complete, with a soak of at least two weeks;
  - 1.0.0: release.

  The tracking project records each milestone's exit criteria. 1.0.0 waits for
  the full walkthrough ([ADR-019](019-walkthrough-direction.md)).

### Versions and changes

- **Version source.** setuptools-scm derives the version from tags on each
  release line. `__version__` is read from package metadata. The C# example
  uses the same version.
- **Changelog.** Each pull request adds a towncrier fragment. CI requires it.
- **Python.** Versions 3.12 and 3.13 are supported. 3.14 is added when the
  dependencies publish wheels for it. A version is dropped only in a minor
  release, and the changelog announces the change.
- **Dependencies.** Packages declare compatible version ranges. Exact pins
  appear only in lock files. The library does not refuse other installed
  versions at runtime; evidence records the versions it found.

### Tooling and CI

- **Tools.** ruff lints and formats; it replaces Black. mypy runs in strict
  mode for `rangekeeper.*`. pre-commit runs ruff, mypy, nbstripout and the
  towncrier check.
- **Strict typing ratchet.** mypy is strict for the whole package. One
  override lists the packages that are not yet strict; the end state is strict
  mode with no override. Each step removes packages from the override, and
  their annotation codes from the ruff structure baseline. The order is:
  1. the root module, `errors` and `money`
     ([#400](https://github.com/daniel-fink/rangekeeper/issues/400));
  2. `duration`, `finance`, `profile` and `quantity`;
  3. `execution`, `run` and `specification`, after the execution fixes of
     [#377](https://github.com/daniel-fink/rangekeeper/issues/377);
  4. `flow`, `model` and `io`, each with its split in
     [#399](https://github.com/daniel-fink/rangekeeper/issues/399);
  5. `shared` and `schema`, after the record runtime helpers are typed;
  6. `market`, after its 1.0 API
     ([#298](https://github.com/daniel-fink/rangekeeper/issues/298),
     [#299](https://github.com/daniel-fink/rangekeeper/issues/299)).
- **Structure baseline.** ruff checks function size, arguments, imports and
  annotations in `src/rangekeeper`. Per-file ignores list the findings of the
  older code. CI fails when a pull request adds to the per-file ignores or to
  the mypy override, so both only shrink.
- **CI jobs:**
  - lint and types;
  - generated-file checks (schema, C# example and manifest hashes);
  - docs links and the site build;
  - tests on Linux and macOS with Python 3.12 and 3.13, and on Windows with
    Python 3.13;
  - one minimal job for each optional extra;
  - tests against the built wheel;
  - walkthrough execution;
  - the .NET example build.
- **Releases.** A tag starts a release workflow. It publishes to PyPI with
  trusted publishing for both release lines.
- **Tests** live in a top-level `tests/` folder that mirrors the packages. It
  also has `tests/contracts` (golden formats, API snapshot and deterministic
  builds), `tests/integration` and `tests/walkthrough`. Tests named after
  project history move into their owners.

### Repository content

- **Copyrighted files.** One history rewrite removes the third-party
  copyrighted files. Links to legitimate sources replace them.
- **Private names.** Names of unrelated private projects are removed from
  branch tips.
- **Evidence archive.** Pre-1.0 evidence moves to an archive tag. Each research
  folder keeps a short summary.

### Documentation site

- **Tooling.** The docs site uses Zensical, with mkdocstrings for the API
  reference. CI converts notebooks for it.
- **Versions.** Zensical's mike fork publishes versioned sites (`/0.8/` and `/1.0/`).
- **Publication.** Publishing the site stays an explicit, approved step
  ([walkthrough procedure](../guides/walkthroughs.md#branches-and-publication)).

## Alternatives and consequences

- **Static versions in `pyproject.toml`.** This relies on manual bumps on two
  lines; the 0.8 drift shows that risk.
- **A hand-written changelog.** It would cause conflicts between the two lines.
- **Keep Black.** Two tools would format and lint, where ruff can do both.
- **Remove copyrighted files only from branch tips.** The files would stay
  available in history.

The [contributor guide](../contributing/README.md) and
[verification guide](../contributing/verification.md) change when the tooling lands.

## Sources and related decisions

- [ADR-004: package and project ownership](004-package-and-project-ownership.md),
  amended by this record for CI and tooling.
- [ADR-019: walkthrough direction](019-walkthrough-direction.md).

Supersedes: none. Amends: ADR-004. Superseded by: none.
