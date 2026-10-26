# Notebook 02 source preparation on 12 October 2026

The [project brief](../../guides/mixed-use-project.md) and
[detailed chapter outline](../../history/plans/006-notebook-02-outline.md) are prepared.
The [source package](../../../examples/walkthrough/data/mixed_use_property) is a
complete capture of the original pinned Speckle object, with a canonical conversion
and separate financial assumptions. This is source-preparation evidence, not
notebook, solver, 3D-viewer or local-book acceptance.

## Acquisition

The initial sandbox read failed at DNS resolution. A read with network access
authenticated to `app.speckle.systems` using existing local configuration and
received project `c0f66c35e3`, object `e7acaac21ae7e9369339900a4aaeb827` with
SpecklePy 3.0.7. No service write or public publication occurred. Credentials were
not copied into artifacts.

The SDK memory transport contained exactly the root and its 3,006 declared
descendants. All detached references resolve. Original JSON strings are retained
in `transport.json.gz`, including property, context, Breps, display geometry and
materials. Original content IDs are preserved.

SDK reserialization produced a different root content ID. It is not used as the
source archive. The preparation tool expands original references and removes only
`__closure` indexes from the conversion input. The archive retains those indexes.
The expanded conversion input has SHA-256
`1b9e0e1231b87902227df0b8738b96b18c7ed3ce1f171014a9c5d73e3909299a`.

## Verified source and conversion

- All 50 domain identities agree with the legacy graph at Git commit
  `6732e83d277c8de81f3dec2906e06d0e75d3b6fa`.
- All 63 relationship triples agree, not merely their counts: 49 spatial
  containment, 11 service and three grouping links.
- The canonical Model stores 36 Entities and 14 Assemblies. Its spatial hierarchy
  spans the same 50 objects with one root and one parent per non-root object.
- All 144 measurement magnitudes and their reviewed units, and all 45 property
  values, agree with the source. Domain IDs, names and classifications are retained.
- The 52 geometry associations reference original captured content IDs, cover all
  50 domain objects and pass canonical envelope validation.
- GFA from the 33 unique floor objects totals 42,786.25911463894 m².
- All 33 floor GFAs and three utility volumes agree with the supplied Brep area or
  volume summaries at absolute tolerance `1e-7`, relative tolerance `1e-10`.
  This does not independently recompute Breps or verify authoring-host geometry.
- Canonical JSON and Speckle-envelope round trips preserve complete Model content.
- Separate income and cost assumptions are extracted from the pinned legacy
  notebook's constant AST expressions without executing that notebook. Reviewed
  time, sign and valuation conventions are documented in the project brief.

## Commands and environment

Source preparation used the repository `.venv` (Python 3.10.19) with the current
editable checkout. This does not replace the Python 3.12–3.13 notebook environment
or fresh-kernel chapter acceptance. The legacy converter source hash is recorded
in `audit.json`; artifact hashes and capture metadata are in `manifest.json`.

Commands, from the repository root:

```sh
.venv/bin/python tools/docs/prepare_property.py verify
.venv/bin/python -m pytest src/tests/test_speckle_mapping.py -q
.venv/bin/python -m black --check tools/docs/prepare_property.py
PYENV_VERSION=3.13.12 python tools/docs/check.py
git diff --check
```

The verification reconstructs the Model and review tables from the retained
transport archive without network access and requires exact output agreement.
The existing mapping suite passed 15 tests. Final command and negative-check
results are retained in [verification.json](verification.json).

## Remaining acceptance

Author and execute notebook 02; redraw the object-model diagram for current
semantics; verify Speckle embeds and selected views; inspect regenerated PyVis and
Plotly interaction in the notebook and Jupyter Book; and then add the accepted
chapter to `myst.yml`. The source inventory is not a replacement for those visual
teaching aids. Public publication is outside this preparation step.
