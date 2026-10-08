# Examples

Maintained examples live in [`examples/`](../../examples). Install the library
and the example builders from the same checkout. From the repository root:

```sh
python -m pip install '.[calculations,execution,tables,plotting,visualization,workflow]' ./examples
```

The `rangekeeper-examples` distribution supplies `rangekeeper_examples`. It is a
development and teaching dependency, outside the Rangekeeper runtime wheel. The
former `rangekeeper.examples` imports are removed:

```python
from rangekeeper_examples import design, investment
```

The Python development group and walkthrough environment use this local package.
Install the matching library and the extras each example needs.

## Find an example

| Directory | Contents |
| --- | --- |
| [`walkthrough/`](../../examples/walkthrough) | Seven notebook sources, book configuration and teaching resources; see [walkthroughs](walkthroughs.md) |
| [`rangekeeper_examples/`](../../examples/rangekeeper_examples) | Shared design and investment builders, plus synthetic layout cases |
| [`schema/`](../../examples/schema) | Complete wire documents and smaller syntax fragments, described below |
| [`workflow/`](../../examples/workflow) | Synthetic equipment/accommodation configurations and source-to-solver example; see [source workflows](source-workflows.md) |
| [`ingestion/`](../../examples/ingestion) | Synthetic Excel extraction and source Evidence examples |
| [`execution/`](../../examples/execution) | Forward and inverse valuation using the wire documents |
| [`grasshopper/`](../../examples/grasshopper) | Rhino source and Grasshopper definitions; see [Grasshopper](grasshopper.md) |

## Run standalone examples

Run from the repository root. Output directories must be fresh. The Excel example
creates a temporary synthetic workbook by default.

```sh
python examples/ingestion/ingestion_evidence.py
python examples/ingestion/excel_ingestion.py
python examples/execution/valuation.py --examples examples/schema --output /tmp/rk-valuation
python examples/workflow/scalar.py --output /tmp/rk-source-solve
```

## Wire examples and fixtures

The files in `examples/schema/` are both reusable examples and conformance inputs.
There is one maintained copy. Complete Model, Specification and Run documents are
distinct from expression or structural fragments. A fragment need not satisfy the
requirements of a complete Model revision.

| Example | Purpose |
| --- | --- |
| [`model.yaml`](../../examples/schema/model.yaml) | Canonical Model document used by forward and inverse examples |
| [`specification-forward.yaml`](../../examples/schema/specification-forward.yaml), [`specification-inverse.yaml`](../../examples/schema/specification-inverse.yaml) | Investigations over exact revisions |
| [`run-forward.yaml`](../../examples/schema/run-forward.yaml), [`run-inverse.yaml`](../../examples/schema/run-inverse.yaml) | Stored Run document shapes; executing an example provides fresh solver evidence |
| [`ownership.yaml`](../../examples/schema/ownership.yaml) | Taxonomies, Measures, entities, shared references and provenance; a structural fragment |
| [`binary-expression.yaml`](../../examples/schema/binary-expression.yaml) | Ordered operands and a reference in a binary expression |
| [`constraint.yaml`](../../examples/schema/constraint.yaml) | Constraint declaration referring to a predicate |
| [`function-expressions.yaml`](../../examples/schema/function-expressions.yaml), [`query-aggregation.yaml`](../../examples/schema/query-aggregation.yaml) | Function and query syntax cases |
| [`valuation-expressions.yaml`](../../examples/schema/valuation-expressions.yaml), [`valuation-formulations.yaml`](../../examples/schema/valuation-formulations.yaml) | Valuation expression and formulation cases |

The [Model–Specification–Run concept](../concepts/model-specification-run.md) and
[expression reference](../reference/expressions.md) define their meaning.
[Schema development](../contributing/schema.md) explains the conformance checks.
A fixture passing structural validation is not proof of solver or host execution.

Authoritative definitions and negative conformance cases remain in `schema/`.
Test-only fixtures, such as the connector envelope, stay with their owning tests.
Captured notebooks and results under `docs/research/` are historical evidence.
They are not maintained examples. Rebuild the walkthrough site after source
changes before any separately authorized publication.


## Stream and acausal hierarchy example

Run `PYTHONPATH=src:examples src/.venv/bin/python -m rangekeeper_examples.flux`
from the repository root, or use the installed development environment with
`python -m rangekeeper_examples.flux`. The [source](../../examples/rangekeeper_examples/flux.py)
shows labelled display, annual resampling and a connected forward/reverse
investigation. Its codebase acceptance precedes notebook migration; see
[ADR-005 evidence](../research/flux-stream-2026-10-08/README.md).
