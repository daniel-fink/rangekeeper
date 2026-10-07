# Why the source workflow APIs exist

Source workflows keep an observation, its interpretation and its publication as
separate operations. A successful read can contain missing data; that is different
from a request that could not execute. `WorkflowSpec` describes a source build.
It is separate from the mathematical `Specification` passed to `Executor`.

## Responsibilities

| Owner | Reason |
| --- | --- |
| `adapters.excel` | Preserve cell addresses, formula/cache state and physical blanks before tabulation |
| `evidence.Evidence` | Keep Table cells, Claim chains and applicable Issues together |
| `operation` | Record effective inputs, parameters, method identity and an Outcome |
| `workflow.catalog` | Select concrete operations and format integrations explicitly |
| `workflow.composition` | Turn reviewed inputs and mappings into canonical Model declarations |
| `workflow.checking` | Attach declared source and Model checks without repairing source content |
| `io` and review adapters | Publish reloadable records or detached views at explicit boundaries |

`Evidence[Table]` binds cells to terminal Claims. `EvidenceKey` addresses a row or
cell independently of display order. Row UUIDs survive selection and reordering.
An Issue explains affected content; its severity alone does not decide whether a
calculation may use it. A valid zero is never equivalent to a missing value.
Construction validates coverage, Claim/value agreement and issue scope. This
establishes structural trust, not business correctness. Each operation prepares an
immutable input once, reuses its Claim and issue indexes and fingerprint, and
validates the output independently. `ClaimKind` and `Severity` re-export the
canonical generated enums; generic scalar encoders do not accept arbitrary enums.

An `Operation` records reproducible computation identity. `Outcome` separates a
usable result from expected input incompatibility. Caller errors remain exceptions.
Semantic fingerprints ignore comments and docstrings but include executable record
behavior. Exact source hashes remain audit evidence alongside semantic identity.

## Composition and independent use

Ingestion operations can run directly without YAML or the workflow runner. Format
adapters own reading and interpretation; generic scheduling depends on declared
operation contracts. The runner does not contain a growing set of Excel branches.
Composition and checking can also run directly on reviewed inputs.

The operation catalog is the composition point for dependencies, schemas, handlers
and implementation identity. A new capability must define these together. See
[format contracts](GRAPH_WORKFLOW_FORMATS.md) and the
[consumer guide](CONSUMER_MIGRATION.md) for concrete entry points and examples.

Source policy remains explicit: numeric coercion, missing values, aggregation,
classification and units belong to the declared rule that interprets the source.
Source adapters do not silently choose a domain policy for the caller. Export does
not authenticate, publish to a service or execute financial equations.

Relevant owners are [Evidence](../src/rangekeeper/evidence/evidence.py),
[tabular operations](../src/rangekeeper/evidence/tabular.py),
[the catalog](../src/rangekeeper/workflow/catalog.py),
[composition](../src/rangekeeper/workflow/composition.py) and
[checking](../src/rangekeeper/workflow/checking.py).
