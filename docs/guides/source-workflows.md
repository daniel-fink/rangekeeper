# Build and review a source workflow

A source build applies reviewed configuration to captured inputs and returns a
canonical Model with Evidence and checks. It does not solve equations. Read the
[source-workflow concepts](../concepts/source-workflows.md) for reproducibility and
the [workflow reference](../reference/workflow.md) for exact contracts.

## Prepare the inputs

Install the `workflow` extra using the [installation guide](installation.md).
Retain the input files, the pinned environment and the four reviewed configuration
files: `sources.yaml`, `model.yaml`, `decisions.yaml` and `checks.yaml`. Each outer
file requires `version: 2`; nested Excel extraction specifications use version 1.

Define business keys, Value keys, units, memberships, missing-value policies and
checks explicitly. Resolve any interpretation that would otherwise require a
question during execution. Do not use a previous generated Model as a hidden
fallback for an unavailable source.

## Run a bounded example

The [equipment](../../examples/workflow/equipment/spec) and
[accommodation](../../examples/workflow/accommodation/spec) examples contain
synthetic data and use the same operations. Run from the repository root:

```sh
python examples/workflow/create_inputs.py /tmp/equipment-inputs --domain equipment
python -m rangekeeper.workflow \
  --spec examples/workflow/equipment/spec \
  --inputs /tmp/equipment-inputs \
  --output /tmp/equipment-review
```

Use a fresh output directory. Replace `equipment` with `accommodation` to run the
other example. Both cover real zero, unavailable readings, ambiguous labels,
conflicting observations, source notes, physical blanks and incomplete totals.
The equipment configuration uses shared `equipment_sizes` numeric policies and
`equipment_readings` measurement bindings; accommodation uses inline declarations.
Both resolve to normal library requests without a project generator.

Inspect the canonical `model.json`, source checks, findings, manifest and offline
review/viewer output. Review both operands and their completeness when a check
fails. Equal counts do not prove equal members. A known subtotal must not be
presented as a complete total.

## Use Python without implicit export

```python
from pathlib import Path
from rangekeeper.workflow import load, run
from rangekeeper.workflow.review import export
from rangekeeper.io import DirectoryStore

spec = load(Path("project/spec"))
outcome = run(spec, input_root=Path("project/inputs"))
if outcome.output is not None:
    result = outcome.output
    DirectoryStore(Path("project/revisions")).put(result.model)
    export(result, Path("project/review-new"))
else:
    for diagnostic in outcome.diagnostics:
        print(diagnostic.code, diagnostic.message)
```

`run` performs no publication. The explicit store call saves a revision; the
explicit export call writes a review bundle. Keep the export destination fresh:
its canonical JSON writer does not overwrite an existing revision file. Retain the
returned Evidence and operations when further interpretation needs their support.

## Use the workbench for repeated builds

```python
from pathlib import Path
from rangekeeper.workflow import workbench

state = workbench.inspect(
    Path("project/spec"),
    input_root=Path("project/inputs"),
    output_root=Path("project/builds"),
)
attempt = workbench.build(
    Path("project/spec"),
    input_root=Path("project/inputs"),
    output_root=Path("project/builds"),
    on_progress=workbench.notebook_progress(),
)
```

Inspection creates no files. A build writes a new checked local bundle and records
an independent attempt. Read its status and diagnostics before using `result`.
A previous successful bundle remains available as history when a new build fails;
it does not become the failed attempt's result. Review changes with the Model diff,
configuration decisions, clarifications and source references. See the
[publication contract](../reference/workflow.md#workbench-and-publication) for failures
at the publication boundary.

## Run adapters directly

Use the [Excel example](../../examples/ingestion/excel_ingestion.py) for snapshot
inspection and physical extraction without the workflow runner. Its adjacent YAML
contains the extraction policy. Use the
[Evidence example](../../examples/ingestion/ingestion_evidence.py) for missing values,
conflicts, explicit resolution and row reordering. The [Excel](../reference/excel.md)
and [Evidence](../reference/evidence.md) references explain their limits.

## Continue into mathematical execution

Install the workflow and execution dependencies. From `src`, run:

```sh
PYTHONPATH=. python ../examples/workflow/scalar.py --output /tmp/rk-source-example
```

The destination must not exist. This example reads an XLSX observation of 10 m²,
builds separate net/gross Values with one Measure, and round-trips the Model through
YAML. It then explicitly authors `gross = net + net` in a new revision. The real
executor solves gross as 20 m². The inverse investigation assigns gross 50 m² and
solves net as 25 m². Both Runs receive resolver-backed validation; source provenance
remains in the accepted output Models.

The equation, investigation, solve and storage are explicit steps. A successful
source build alone is not a numerical acceptance result. See
[execution](../reference/execution.md) and [Run/storage](../reference/run-and-storage.md).
