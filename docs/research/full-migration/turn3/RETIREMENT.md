# Turn 4 retirement register

This is a removal plan, not a claim that the old implementation has been removed.
The [consumer register](CONSUMERS.md), [current scan](legacy-dependencies.json), and
[frozen behavior inventory](../turn1/ledger.json) supply ownership and evidence.
The frozen 671-symbol inventory remains historical; `ledger.json` in this folder
adds current consumer dispositions without rewriting that baseline.

## Ordered removal tasks

1. Preserve the accepted synthetic characterizations as canonical tests. Remove
   old-API comparison tests only after their behavior has a canonical assertion.
2. Remove old numerical implementations and their root exports together:
   `flux.py`, `_legacy_duration.py`, `measure.py`, `distribution.py`,
   `extrapolation.py`, `projection.py`, `formula/`, `dynamics/`, `segmentation.py`,
   and `policy.py`. Destinations are `model.flow`, `model.duration`, `duration`,
   `units`, `calculations`, `formulations`, `scenarios`, and `policies`.
   Keep canonical `duration/`, `graph/projection.py`, and `formulations/financial.py`.
3. Remove presentation leftovers `format.py`, `rgba_from_cmap`, `update_class`, and
   the commented-only `space.py` once their remaining test/import guards are
   updated. Detached adapters replace active consumers. Do not add aliases back.
4. Retire old graph implementation files as one dependency group:
   `graph/_catalog.py`, `graph/graph.py`, `graph/entity.py`, `graph/assembly.py`,
   `graph/relationship.py`, `graph/characteristics.py`, `graph/classification.py`,
   `graph/taxonomy.py`, `graph/definitions.py`, `graph/provenance.py`,
   `graph/revision.py`, `graph/update.py`, `graph/table.py`, `graph/adapter/`,
   and `graph/legacy/`. Remove superseded exports and old-only errors after a
   dependency scan. Keep `graph/view.py`, `selection.py`, `hierarchy.py`,
   `membership.py`, `reduction.py`, `reducers.py`, `projection.py` and their
   canonical errors. Explicit wire converters under `migration/` remain supported.
5. Retire `api.py` and the old Speckle boundary only when the held integration
   gate below is closed or a reviewed retirement explicitly narrows support.
   If this requires an old graph dependency, hold that dependency group too.
6. Remove excluded legacy C# source/old project scaffolding only after the Windows
   gate closes. The original Rhino model and GHX stay as historical evidence;
   they are not compiled or required by the new authoring definition.
7. Remove old generated build caches and stale generated files after checking
   the rebuilt walkthrough site. Do not delete historical research evidence.
8. Narrow optional dependencies after import absence tests and all accepted
   consumer checks pass from a new wheel. Regenerate documentation and repeat
   the full regression, schema, typing, installed and host checks appropriate to
   the actual removals. Record the paired RK/Projects state. Commit and push need
   a separate instruction.

## Gates

| Group | Replacement evidence | Removal condition |
|---|---|---|
| Numerical/temporal algorithms | Turn 1/2 kernels and financial library, seven Turn 3 installed walkthroughs, synthetic parity checks | Every preserved behavior has a canonical test; no active consumer import remains |
| Source Graph consumers | Three real Model builds, exact comparisons, source lineage, Projects tests and fresh-kernel Mandarin review | Accepted source builds remain reproducible after removal; held transport group does not import these files |
| Graph views/reduction/table | Model-backed operations, workbench, layout and browser tests | Keep canonical operation tests; remove only the superseded classes/exports |
| Root presentation/class patching | All seven notebooks use explicit construction and detached adapters | Scan has no executable retained caller |
| Speckle/C# host predecessor | Offline mapping and Mac Rhino accepted; pinned Python receive accepted | **Hold:** current official Windows connector publication/receive still requires an approved destination and host |
| Historical formats | Explicit Graph/Speckle/profile converters accepted | Retain converters and their fixtures; old implementation is not required to decode them |
| Hypar | User explicitly retired support | Preserve historical files; no current acceptance or compatibility claim |
| Browser/outliner | Future importer on hold | No implementation/removal in this migration |

A lexical hit in a negative import test is evidence that removal is guarded, not
an active runtime dependency. Unknown downstream consumers have no compatibility
claim; the upgrade guide gives the explicit migration path.
