# Isolated Windows-gated predecessor code

The retained implementation now lives under explicit `legacy` directories. This
is a relocation, not removal or acceptance of the Windows connector gate. The
canonical schemas, mathematics, source meanings and active C# build inputs are
unchanged. The relocation follows the uncommitted Turn 4 retirement slice.

```text
src/rangekeeper/
  graph/                         Model-backed views, hierarchy and reductions
  model/                         canonical domain records
  migration/                     explicit historical wire converters
  legacy/
    api.py                       old Speckle API
    measure.py                   old Measure and unit registry
    graph/
      graph.py, entity.py, assembly.py, relationship.py
      characteristics.py, definitions.py, classification.py, taxonomy.py
      provenance.py, revision.py, update.py, errors.py, _catalog.py
      view.py, reduction.py, table.py
      adapter/                   old Graph JSON codec

src/tests/
  legacy/                        predecessor regression and old live tests
  fixtures/migration/            fixed historical JSON for canonical converters

grasshopper/
  Model/, Components/, Tests/     active .NET 8 projects
  legacy/
    Model/, Components/, Tests/   excluded predecessor source and resources
```

Use canonical records and operations for new work:

```python
from rangekeeper import Model
from rangekeeper.model import Entity, Assembly, Measure
from rangekeeper.graph import View
from rangekeeper.migration import convert_graph
```

Use explicit imports only when inspecting the held implementation:

```python
from rangekeeper.legacy import graph, measure
from rangekeeper.legacy.graph.adapter import json
from rangekeeper.legacy.api import Speckle
```

The former `rangekeeper.api`, `rangekeeper.measure`, old domain exports from
`rangekeeper.graph`, and `rangekeeper.graph.legacy` paths have no aliases.
The predecessor View and reduction code now lives directly in `legacy.graph`.
The canonical `graph.errors` contains only Model-operation errors; predecessor
errors live with the predecessor. Shared encoding errors remain in root `errors`.

Dependency direction is explicit: predecessor code can use shared Evidence,
validation and table utilities; canonical code must not import `legacy`.
The package stays lazy and the temporary `legacy` dependency extra is unchanged.
This move changes Python import paths and does not promise pickle compatibility.
Historical Graph JSON tags remain unchanged. Canonical converters need no old
implementation, as shown by the frozen wire fixture and fresh-process checks.

Predecessor-only tests have moved into `src/tests/legacy`. Two mixed test files
were split so their canonical checks stay in the main suite. Migration tests now
use a fixed synthetic JSON fixture instead of constructing an old Graph at runtime.
The three live predecessor tests remain excluded from local acceptance:

```sh
# Run from src/
python -m pytest -q --ignore=tests/legacy/test_api.py
```

The original Rhino model and `exampleDesignConfig.ghx` stay at their original
paths as source evidence. The active definition remains `exampleDesignCanonical.ghx`.
Old icons, screenshots, excluded tests and the exploratory `unnamed.gh` moved with
the old C# source. The active projects still compile only their explicit canonical
source lists. No legacy C# project or compatibility assembly was introduced.

## Verification and remaining gate

[Fresh evidence](research/full-migration/legacy-isolation/README.md) records
1,063 local tests passed, 24 optional MiniZinc skips, generation freshness, typing,
installed core/execution/source checks, explicit predecessor roundtrips, and the
C# build and cross-language checks. Import checks find no canonical-to-legacy or
old-path imports. The schema files are unchanged; the seven prior schema-suite
results remain the Turn 4 evidence, not claimed as newly rerun here.

The [Windows procedure](../grasshopper/WINDOWS_DEVELOPMENT.md) still controls final
removal. Its publication/receive gate is open. All retained implementation is now
in the isolated trees, so final deletion can remove those trees, their tests and
the temporary extra without another domain move. Keep historical wire converters
and original source evidence after that deletion. No commit, push or publication
was performed for this relocation.

## Future cleanup

Follow the [remaining retirement gate and cleanup checklist](research/full-migration/turn4/RETIREMENT.md#cleanup-checklist-after-the-windows-gate-closes).
It specifies the three trees to remove, root exports, dependency extra and locks,
test exclusions, acceptance checks and files to preserve. The
[move manifest](research/full-migration/legacy-isolation/moves.json) retains old
and new paths; it does not include every split test or newly added package file.
Keep the relocation evidence unchanged and add a separate record for final removal.
