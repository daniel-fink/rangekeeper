# Retire the held predecessor

**Status: held until Windows connector acceptance.** The old Graph domain,
Measure registry, Speckle API and C# components form one retained dependency group.
Canonical Model code uses independent records and operations. Follow
[Windows acceptance](windows-acceptance.md) before removing this group. Layout
solver checks have their own acceptance procedure and do not change this gate.

This page is the current retirement procedure. The
[Turn 4 retirement record](../research/full-migration/turn4/RETIREMENT.md) and
[relocation evidence](../research/full-migration/legacy-isolation/README.md)
describe their historical checkpoints and paths; preserve those files unchanged.

## Retained scope and boundaries

| Held tree | Content |
| --- | --- |
| `src/rangekeeper/legacy/` | Old Graph/Measure/Speckle implementation, including graph views, reduction, tables and JSON adapter |
| `src/tests/legacy/` | Predecessor regressions and three unverified live-service tests |
| `src/grasshopper/legacy/` | Excluded C# classes, components, tests, icons, screenshots and exploratory `unnamed.gh` |

The active .NET 8 Model, Components and Tests projects stay outside `legacy/`.
Their explicit compile/resource lists exclude the predecessor. Do not add the
held source to those projects or introduce a compatibility assembly.

Use canonical records for new work. Historical wire conversion under
`rangekeeper.migration` does not require the predecessor runtime. Explicit imports
remain available only for work on the held implementation:

```python
from rangekeeper.legacy import graph, measure
from rangekeeper.legacy.graph.adapter import json
from rangekeeper.legacy.api import Speckle
```

Old `rangekeeper.api`, `rangekeeper.measure`, `rangekeeper.graph.Graph` and
`rangekeeper.graph.legacy` paths have no aliases. Legacy view and reduction modules
live directly in `legacy.graph`; canonical `rangekeeper.model.system.View` accepts
only Models. Legacy errors stay with their owner; shared encoding errors live in
`shared.errors`.

Predecessor code can use shared validation, workflow Evidence and table utilities.
Canonical code must not import `legacy`. The package remains lazy; its temporary
`legacy` extra supplies optional dependencies. Historical JSON tags are unchanged.
Moved Python module paths do not promise pickle or unknown downstream compatibility.

The three live tests in `src/tests/legacy/test_api.py` remain excluded from local
acceptance. An exclusion is not a passed service test or a closed host gate. See
[verification](verification.md) for current commands.

## Removal checklist

- [ ] Link the completed Windows acceptance record here. Include the accepted
  revision, versions, authorized destination, safe publication/receive pins and
  required semantic comparisons. Mac and offline results cannot substitute.
- [ ] Capture fresh repository state. Scan Python, notebooks, C# project items,
  examples and known downstream consumers for callers. Assign a replacement or
  explicit retirement to each. Retain useful semantic assertions as canonical
  tests before removing predecessor tests.
- [ ] Remove the three held trees together. Preserve the files listed below.
- [ ] Remove `legacy` from `_LAZY_MODULES` and `__all__` in
  `src/rangekeeper/__init__.py`. Do not leave an alias or fallback import.
- [ ] Remove the `legacy` extra from `pyproject.toml`; regenerate `uv.lock`
  and affected consumer locks through their package tools. Check shared dependency
  use first: visualization still uses NetworkX, canonical Speckle uses SpecklePy,
  and canonical units use Pint.
- [ ] Remove the obsolete `--ignore=src/tests/legacy/test_api.py` from current commands.
  Review any other service tests separately. Keep historical commands unchanged.
- [ ] Extend boundary and installed-package checks to prove that `rangekeeper.legacy`
  is absent and cannot import. Check that canonical imports do not load service or
  presentation dependencies. Keep negative tests that mention removed names.
- [ ] Build one candidate wheel. Use it for installed core/import, execution,
  workflow, project and notebook acceptance. Run local regressions, all seven
  schema suites, generator freshness and typing; run the active C# and connector
  checks required by the change. Record exclusions and environment limits.
- [ ] Update current architecture, upgrade instructions, dependencies, consumers,
  navigation and decision links. Mark removal complete only after implementation
  and acceptance pass. Add fresh evidence with source revision, wheel hash and
  preservation checks. Commit and push are separate actions.

## Preserve after removal

| Material | Reason |
| --- | --- |
| `src/rangekeeper/model/`, `specification/`, `run/`, `shared/`, `calculations/` and `workflow/` | Current records, operations, units, calculations and evidence |
| `src/rangekeeper/adapters/` and `migration/` | Current integrations and explicit historical wire conversion |
| `src/tests/fixtures/migration/graph-v1.json` and `graph-v1-expected.json` | Frozen historical input and expected canonical content |
| Canonical migration, ingestion, unresolved-measurement, boundary, retirement, Model and consumer tests | Semantic coverage and dependency guards outside the held tree |
| `tools/schema/verify_install.py` | Installed-package verification; extend for complete removal |
| `src/grasshopper/Model/`, `Components/`, `Tests/` and `Rangekeeper.sln` | Active authoring, fixtures, round trips and host checks |
| `examples/grasshopper/exampleDesign.3dm` and `exampleDesignConfig.ghx` | Original Rhino/GHX source evidence |
| `examples/grasshopper/exampleDesignCanonical.ghx`, `src/grasshopper/Tests/Fixtures/connector-envelope.json` and `Tests/accept_rhino.py` | Canonical definition and connector/host acceptance inputs |
| Schema history and `docs/research/` | Historical contracts, source hashes, move records and verification evidence |

Preserve unrelated edits, original workbooks and project archives. The old move
manifest records direct relocations, not every split test or new file; it is not
a complete deletion list. Its `audit.py`, `verify_final.py` and
`verify_installed.py` verify a checkpoint where the predecessor exists. Do not run
or rewrite them as post-removal acceptance. Add a separate result for retirement.
