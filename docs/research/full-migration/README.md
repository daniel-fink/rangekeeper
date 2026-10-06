# Full migration discovery evidence

Captured 2026-10-03 for the [full-refactor review](../../history/FULL_MIGRATION_REVIEW.md).
This is static discovery, not a new test baseline or completed behavior audit.

Run from the repository root:

```sh
/private/tmp/rk-scalar-runtime/bin/python docs/research/full-migration/inventory.py
```

The script uses only the Python standard library and Git; another Python 3.10+
interpreter can replace the temporary interpreter path. It does not import RK,
execute notebooks, read source workbooks or write outside this evidence directory.
The two named external locations are inspected only when available.

- [inventory.py](inventory.py): exact static capture procedure.
- [inventory.json](inventory.json): repository states, source hashes, remaining
  module symbols, candidate consumer references, and parallel branch modules.
- [SYMBOLS.md](SYMBOLS.md): readable symbol checklist, including fields/private
  methods, for assigning behavior contracts before old implementations retire.

RK was at `90c2e00ba7b942a8830960e3df3f3ff616f30fa1`. Projects was at
`5725cc02748ace15e390c8dcea2c5d69185d67c9`; the separate RK assembly-layout worktree
was at `4e5aec42f16a18c4d715f5a2a1b879d98e0f71e3`. The capture records dirty state;
source hashes, not HEAD alone, identify the inspected content. Existing unrelated
`.gitignore` changes were preserved. Only RK documentation/research files were
authored in this review.

Lexical references are candidate callers. They do not resolve aliases, indirect
instance-method calls, dynamic imports, external users or runtime coverage. The
inventory includes seven source walkthroughs and separately lists generated
notebook copies. Active project specifications/tests/notebooks are inspected;
archived project code and generated results are excluded.

New findings include unmigrated version-1 repository workflow examples and
Mandarin's dependency on parallel workbench/layout APIs. Public symbols from that
worktree are captured, but their full behavior and backend requirements need the
P1 contract review. No branch merge, source migration, notebook execution, solver
probe, service request or host verification was performed here.

The last runtime evidence remains the [6C/6D checkpoint](../consumer-migration/README.md):
798 passes and one known numerical failure, with its documented limitations.
Those counts are historical runtime results, not new results from this inventory.

## Unit composition follow-up

Daniel clarified that general Flows need not use currency and that Streams should
support compatible sums and meaningful products. The review now uses the selected
names `model.duration` and `formulations/flow.py` and distinguishes engineering
design work from actual questions requiring user input.

From `src`, reproduce the narrow legacy unit-path probe with:

```sh
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-scalar-runtime/bin/python \
  ../docs/research/full-migration/unit_probe.py
```

[unit_probe.py](unit_probe.py) uses a fresh Pint registry and the same unit helpers
as `Stream.product`; [unit-probe.json](unit-probe.json) records the environment and
observed results. The initial script invocation omitted `PYTHONPATH` and could not
import RK; the command above is the corrected invocation. This check does not
exercise Stream resampling or establish a complete new temporal contract.

Polars/pandas statements in the review are based on linked official documentation.
No Polars implementation or comparative performance benchmark was run. That is an
engineering investigation in the plan, not a choice Daniel must make in advance.

## Turn 1 implementation evidence

The original static inventory above is frozen discovery evidence. The new
[Turn 1 report](turn1/README.md) adds baseline/verification runs, complete disposition
ledger, installed notebook and the implemented content/calculation contracts.
