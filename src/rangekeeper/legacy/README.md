# Windows-gated Python predecessor

This package holds the old Graph domain, Measure registry and Speckle API until
the official Windows connector acceptance gate closes. It is not the canonical
Model API. Install the temporary `legacy` extra for its optional runtime dependencies.

```python
from rangekeeper.legacy import graph, measure
from rangekeeper.legacy.graph.adapter import json
from rangekeeper.legacy.api import Speckle
```

The old `rangekeeper.api`, `rangekeeper.measure`, `rangekeeper.graph.Graph` and
`rangekeeper.graph.legacy` paths have no aliases. The former nested graph View and
reduction code now lives directly in `legacy.graph.view` and `legacy.graph.reduction`.
Canonical `rangekeeper.model.system.View` still accepts only Models.

Predecessor code can use shared validation, Evidence and table utilities. Canonical
code must not import this package. JSON wire tags are unchanged; Python module paths
have changed. This does not promise pickle compatibility or unknown downstream
compatibility. Use the supported converters under `rangekeeper.migration` to
upgrade historical JSON without importing the predecessor.

Regression tests are under `src/tests/legacy`. Three old live-service tests remain
unverified. Moving the files is not acceptance of those tests or of the Windows gate.
See the [relocation record](../../../docs/LEGACY_ISOLATION.md) and
[cleanup checklist](../../../docs/research/full-migration/turn4/RETIREMENT.md#cleanup-checklist-after-the-windows-gate-closes).
Remove this package with its predecessor tests and C# tree only after the gate
closes. The checklist also covers root exports, dependencies and retained converters.
