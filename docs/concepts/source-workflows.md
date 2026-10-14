# Source workflows and reproducibility

A source workflow builds a canonical Model from captured observations and reviewed
interpretation rules. It keeps observation, interpretation and publication as
separate operations. Its `WorkflowSpec` is source configuration, distinct from the
mathematical `Specification` used by an `Executor`. Its `Operation` and `Outcome`
records are distinct from a mathematical `Run`.

Read the [workflow reference](../reference/workflow.md) for the implemented
configuration and API, or [run a source build](../guides/source-workflows.md).
The [framework concepts](model-specification-run.md) explain the three document roots.

## What makes a build reproducible

Exact source bytes, complete configuration, retained adapter code and a pinned
execution environment must be sufficient to reproduce a Model. A rebuild must not
need an LLM, notebook state, conversation history, a previous generated Model or
an unrecorded human decision.

| Input | Required content |
| --- | --- |
| Sources | Captured editions, bound to checksums and logical source keys. A mutable URL or path alone does not identify an edition. |
| Configuration | Source selection, extraction, parsing, definitions, business identities, classifications, memberships, reviewed decisions, unresolved-choice policies and checks. |
| Adapter code | The Python implementations and supporting files used by the build. Retain the code as well as its revision or content hash. |
| Environment | Rangekeeper, selected operation implementations and relevant runtime/dependency versions. Compatibility ranges are not a reproducible environment lock. |

The loader records the exact bytes of the four YAML configuration files. The
runner also records effective parameters and implementation identity. Keep the
original files: a manifest or hash does not replace its inputs.

External facts must enter as declared source evidence or explicit settings.
Wall-clock time, current working directory, mutable services and local notebook
overrides cannot supply hidden Model inputs. A cache can improve speed, but it
must not determine correctness. A missing or changed input must not be silently
replaced by a previous successful output.

## Authoring and execution

During authoring, a person or assistant can inspect sources, identify ambiguity,
propose mappings and revise configuration or project adapter code. A decision
must reach an executable mapping, parameter, selection or policy before it affects
a build. Prose explains that decision; it is not executable configuration. A passing
build or silence during review does not establish approval.

Execution applies the retained code and reviewed settings. It does not ask an LLM
to reinterpret data or generate replacement code. An unresolved choice needs an
explicit policy: preserve unavailable evidence, produce an authorized provisional
representation, defer the affected scope, or report that output is unavailable.

Use ordinary Python for project-specific algorithms. Promote a helper into the
library when its responsibility and reuse are demonstrated. Do not require a
universal transformation language or a new library operation for every source
layout.

## Stages and ownership

| Stage | Responsibility |
| --- | --- |
| Read | An adapter captures a source edition and native observations. Excel preserves addresses, formulas, cached values and physical blanks. |
| Inspect | Bounded, read-only descriptions and samples support review. Inspection does not accept a mapping or alter evidence. |
| Extract | The declared native ranges and columns become addressed outputs with source Claims. Layout normalization does not rewrite raw observations. |
| Interpret | Explicit parsing, selection, classification and resolution produce derived Claims. Retain the basis for selection and excluded inputs. |
| Compose | Workflow composition creates definitions, objects and explicit memberships under declared business identities. |
| Check | Declared comparisons and invariants report completeness and disagreement. They do not repair source content. |
| Publish | A caller explicitly stores a Model revision or exports a review bundle. Source execution alone does neither. |

The [Evidence contract](../reference/evidence.md) binds Table cells to terminal
Claims and applicable Issues. A successful extraction can contain unavailable
cells; it is different from an invocation with no output. A real zero or `False`
must not become missing. An Issue explains affected content; its severity alone
does not determine whether another operation can use that content.

Source observations and their support chains are transient workflow objects.
Composition converts them into schema provenance records. Domain validation does
not import source readers, service clients, presentation tools or solver backends.
Adapters and Evidence transformations can also run directly without YAML or the
workflow runner.

## Identity and acceptance

Source identity describes an edition. Evidence-row identity describes an output
within that edition. Business identity describes a domain object. Changing a
workbook's row order or an observation must not accidentally replace the apartment
or asset that it describes. Changed source support can still change the Model
revision, because a revision includes its provenance.

The acceptance test is a fresh-environment rebuild using only the declared inputs.
Repeated builds must agree on content, identities, evidence bindings and substantive
check results. Repeat the build without caches. Include changed editions,
unavailable values, unresolved choices and failed prerequisites. Compare canonical
content, not Python object addresses or incidental display formatting.

Structural validation and repeatability establish neither correct interpretation
nor physical completeness. Review the declared policies and compare outputs with
independent expectations. A source check report does not perform mathematical
execution or certify a solver result.
