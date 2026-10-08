# Remaining retirement gate

The permitted numerical/presentation group is removed. The following group is
**held for official Windows connector publication/receive acceptance**. It is
retained as one dependency group, now isolated under `legacy/`: its `api.py`
constructs old graph objects and its Characteristics/definitions use its own
`measure.py`. See [relocation and fresh checks](../../../contributing/legacy-retirement.md).

| Retained implementation | Removal condition |
|---|---|
| `src/rangekeeper/legacy/api.py` | Complete the approved Windows connector fixture and roundtrip procedure; verify canonical transport covers the required consumer |
| `src/rangekeeper/legacy/measure.py` | Remove its old graph/API callers together; retain canonical `model.measure` and `units` |
| `src/rangekeeper/legacy/graph/`, including its errors, View, reduction, table and JSON adapter | Close the connector gate, scan current callers, then remove the isolated group and its explicit package export together |
| `src/tests/legacy/`: graph/Measure regressions and three live old API tests | Keep useful semantic assertions on canonical Models, then retire tests of the removed API; do not count service exclusions as passed |
| `grasshopper/legacy/`: excluded C# source, tests and resources | Close the Windows gate, then remove excluded implementations; preserve original Rhino/GHX files as historical evidence |
| Temporary `legacy` dependency extra | Remove after the dependency group above has no callers |

The procedure is [Windows development and acceptance](../../../contributing/windows-acceptance.md).
It requires an available host and a concrete approved publication destination.
No new publication is authorised by this retirement work. Mac Rhino checks,
offline envelopes and Python read acceptance do not close the Windows gate.

Keep the Model-backed graph operations (`view`, `selection`, `hierarchy`,
`membership`, `reduction`, `reducers`, `projection`), canonical errors, adapters,
and explicit `migration` converters. Their names are not evidence of legacy status.
No old Graph implementation is required to decode historical JSON with those
explicit converters. Keep schema history and research evidence.

## Move history

The [move manifest](../legacy-isolation/moves.json) records 51 direct moves with
old paths, new paths and original hashes: 19 Python implementation files, seven
whole Python test files and 25 C# or resource files. The
[preservation proof](../legacy-isolation/move-proof.json) checks those moves;
the [symbol ledger](../legacy-isolation/ledger.json) records current symbol locations.
Split test files, new package initializers and directory READMEs are not direct
moves. Thus, the manifest is an audit trail, not the complete future deletion list.
Use the three directory trees below as the removal scope.

The [relocation report](../legacy-isolation/README.md) and
[final state](../legacy-isolation/final-state.json) retain the checks for this
checkpoint. Preserve their logs, hashes and scripts. In particular, `audit.py`,
`verify_final.py` and `verify_installed.py` check this checkpoint, where the held
implementation still exists. They are not post-removal acceptance scripts.
Record later cleanup evidence separately; do not rewrite earlier results.

## Cleanup checklist after the Windows gate closes

This is the current cleanup register. The gate is still **open**. Relocation alone
does not authorize deletion of the held implementation.

- [ ] Link the completed Windows acceptance record here. Include the host and
  package versions, approved destination, pinned publication/receive identifiers,
  and semantic comparisons required by the Windows procedure. Record the accepted
  RK revision. Mac and offline results cannot substitute for this record.
- [ ] Capture fresh repository state and scan Python, notebook cells, C# project
  items, examples and known downstream consumers for remaining callers. Give each
  caller a replacement or an explicit retirement disposition. Keep useful semantic
  assertions as canonical tests before removing predecessor tests.
- [ ] Remove `src/rangekeeper/legacy/`, `src/tests/legacy/` and
  `grasshopper/legacy/` together. Do not remove the canonical files listed below.
- [ ] Remove `legacy` from both `_LAZY_MODULES` and `__all__` in
  `src/rangekeeper/__init__.py`. Do not leave an alias or fallback import.
- [ ] Remove the `legacy` optional extra from `src/pyproject.toml`. Regenerate
  `src/uv.lock` and affected consumer locks through their package tooling.
  Check dependency use before removal: `networkx` is also used by visualization,
  `specklepy` by the canonical Speckle extra, and Pint by canonical units.
- [ ] Remove the obsolete `--ignore=tests/legacy/test_api.py` instruction from
  current test commands, including `src/README.md`. Review current live-service
  tests separately; deleting an exclusion is not service acceptance. Keep old
  commands in historical evidence unchanged.
- [ ] Extend the existing boundary and installed-package checks to prove that
  `rangekeeper.legacy` is absent from the wheel and cannot be imported. Check that
  canonical imports do not load service or presentation dependencies. Keep negative
  tests that mention removed names; such mentions are not runtime callers.
- [ ] Build one candidate wheel. Use that same wheel for installed core/import,
  execution, source workflow, project and notebook acceptance. Run the local
  regression suite, seven schema suites, generation freshness and typing. Run the
  active C# build, cross-language checks and connector checks required by the change.
  Record actual results, exclusions and environment limits.
- [ ] Update the current architecture, upgrade guide, dependency instructions,
  consumer register, documentation index and handoff. Mark this register closed
  only when the removal and its acceptance are complete. Link fresh evidence and
  record the candidate wheel hash, source revision, preservation checks and any
  remaining limitations. Commit and push remain separate actions.

## Files to preserve

All paths below are relative to the repository root.

| Keep | Reason |
|---|---|
| `src/rangekeeper/model/`, `duration/` and `units.py` | Canonical records, dates and units |
| `src/rangekeeper/graph/` and `adapters/` | Model-backed operations and supported integration/presentation boundaries |
| `src/rangekeeper/migration/` | Explicit historical-format conversion without the old runtime |
| `src/tests/fixtures/migration/graph-v1.json` and `graph-v1-expected.json` | Frozen historical wire input and expected canonical content |
| `src/tests/test_migration_foundations.py`, `test_ingestion_evidence.py` and `test_unresolved_measurements.py` | Canonical checks retained outside the predecessor test tree |
| `src/tests/test_legacy_boundary.py`, `test_retirement.py`, `test_model_graph.py`, `test_model_consumers.py` and `tools/schema/verify_install.py` | Regression and dependency guards; extend them for complete package removal |
| `grasshopper/Model/`, `Components/`, `Tests/` and `Rangekeeper.sln` | Active .NET 8 authoring, components, fixtures and host checks |
| `grasshopper/Tests/exampleDesign.3dm` and `exampleDesignConfig.ghx` | Original source evidence, even after the old implementation is removed |
| `grasshopper/Tests/exampleDesignCanonical.ghx`, `Fixtures/connector-envelope.json` and `accept_rhino.py` | Canonical definition and connector/host acceptance inputs |
| Schema history and `docs/research/full-migration/` | Historical contracts, source hashes, move records and verification evidence |

Preserve unrelated `.gitignore` edits, the Syncthing conflict copy, original
workbooks and project archives. Hypar is retired and its ignored local directory
has been [removed at the user's request](../hypar-removal/README.md). That cleanup
does not close the Windows gate or authorize deletion of its held directories.
The future Browser/outliner importer stays on hold.
