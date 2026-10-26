# Changelog

This file records changes on the 0.8 maintenance line (`support/0.8`).
The 1.x line keeps its own changelog on `develop`.

## 0.8.72 (unreleased)

First release from `support/0.8` through the tag-triggered release workflow.
The package code is the same as 0.8.71.

- Allow Python 3.13: `Requires-Python` is now `>=3.10, <3.14`. The 0.8.71
  test suite gives the same results on Python 3.12 and 3.13.
- Declare the setuptools build backend and pin setuptools 82.0.1, the version
  that built 0.8.70 and 0.8.71.
- Publish from GitHub Actions with PyPI trusted publishing. Each release has
  PEP 740 attestations on PyPI and a GitHub build provenance attestation.
- Add `SECURITY.md` with the supported versions and the 0.8 end-of-life process.

## 0.8.71 (2026-03-19)

Built locally before the release workflow existed. Commit `4b6df47` (tag
`v0.8.71`) reproduces the published files. See [RELEASING.md](RELEASING.md#provenance-of-earlier-releases).

- `rangekeeper.format.to_decimal` returns `Decimal("Infinity")`,
  `Decimal("-Infinity")` or `Decimal("NaN")` for non-finite values.

## 0.8.70 (2026-03-19)

Built locally. Commit `a2c5245` (tag `v0.8.70`) reproduces the published files.

- `Flow.resample()` passes `origin="epoch"` only for fixed-length (tick)
  frequencies.

## 0.8.69 and earlier

No changelog was kept. See the commit history and the
[PyPI release history](https://pypi.org/project/rangekeeper/#history).
