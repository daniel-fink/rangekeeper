# Research and verification evidence

This folder keeps a short summary of each pre-1.0 experiment, migration baseline
and acceptance result. The complete evidence, including logs, captured commands,
notebooks, scripts and archives, is at tag
[`archive/pre-1.0-evidence`](https://github.com/daniel-fink/rangekeeper/tree/archive/pre-1.0-evidence/docs/research). Each summary links to its folder there.

Each result applies to the source and environment recorded with it. Old paths and
dependency names in the archived files are evidence, not current APIs. Use the
[current guides](../README.md) for contracts and [verification](../contributing/verification.md)
for commands. [History](../history/README.md) explains the earlier sequencing.

| Evidence | Summary |
| --- | --- |
| [Schema tooling probes — 2026-09-24](schema-tooling/README.md) | A synthetic-vocabulary study of LinkML JSON Schema and Pydantic generation, preserved for reproduction. The LinkML decision in the schema comparison governs. |
| [Current schema comparison — 2026-10-02](current-schema-comparison/README.md) | Comparison of LinkML and CUE for the Model, Specification and Run schemas, and the decision to keep LinkML. Includes the first CUE import probe and the 2 October schema audit. |
| [Domain migration baseline and turns — 2026-10-02](domain-migration/README.md) | Step 1 observed baseline and the record-boundary feasibility review for the domain migration, with the evidence for turns 1 to 3 and the validation refactor. |
| [Model tables, adapters and source workflows — 2026-10-03](consumer-migration/README.md) | Step 6C/6D verification of Model tables, adapters and source workflows: test-suite results, schema suites, captured Models and Runs, and the revision store. |
| [Full migration evidence — 2026-10-03 to 2026-10-06](full-migration/README.md) | Static discovery for the full refactor review, and the evidence for its four turns: baselines, symbol inventories, flow semantics, movement naming, date-only and financial-library studies, MiniZinc solver experiments, retirement checklists and captured commands. |
| [Graph migration evidence — 2026-10-03](graph-migration/README.md) | Step 6A/6B: canonical Model-backed View, explicit relationship and membership Hierarchy, owner-local Value selection, quantity reducers and immutable Aggregation and Coverage. |
| [Scalar execution checkpoint — 2026-10-03](scalar-execution/README.md) | Step 5 execution evidence: forward, inverse and two-case batch valuation results, backend checks and captured logs. |
| [First walkthrough acceptance — 2026-10-08](basic-dcf-2026-10-08/README.md) | Legacy teaching fidelity, fresh notebook execution and rendered review of the first DCF walkthrough after the Flux and Stream migration, with the API acceptance for direct Flow display and projection verbs. |
| [Flux and Stream implementation acceptance — 2026-10-08](flux-stream-2026-10-08/README.md) | Numerical and acausal checks, installed-wheel examples, performance and memory costs for the Flux and Stream implementation of ADR-005. |
| [Jupyter Book 2 local acceptance — 2026-10-08](jupyter-book-2-2026-10-08/README.md) | First-chapter execution, native tables, a portable reference image and a two-page local Jupyter Book 2 site. |
| [Native Polars display acceptance — 2026-10-08](native-polars-display-2026-10-08/README.md) | Shared native table rendering, configuration isolation and refreshed outputs for the first walkthrough. |
| [Notebook 02 acceptance — 2026-10-12](notebook-02-2026-10-12/README.md) | Complete-source economics, independent arithmetic, the local geometry viewer, interactive graph and chart review, and a three-page local book. |
| [Notebook 02 source preparation — 2026-10-12](notebook-02-source-2026-10-12/README.md) | Complete pinned design capture, canonical conversion, exact legacy graph reconciliation, quantity and geometry-summary checks, and separate teaching assumptions. |
| [Notebook 02 condensation — 2026-10-13](notebook-02-2026-10-13/README.md) | Eight sections, shared presentation helpers, fewer repeated visuals, unchanged financial results and a refreshed local-book review. |
| [Notebook 03 acceptance — 2026-10-13](notebook-03-2026-10-13/README.md) | A fixed development plan, SFFA forward and inverse solves, independent cash-flow and funding checks, and a four-page local book. |
| [Plotly walkthrough style — 2026-10-13](plotly-walkthrough-2026-10-13/README.md) | A shared light and dark chart style, editable Plotly adapters, responsive local embeds and notebook and book validation. |
| [Earlier SQLite Model proof — 2026-10-13](sqlite-model-2026-10-13/README.md) | Schema-driven one-file storage, retained legacy geometry and generator evidence. It predates the Bundle contract of ADR-008 and does not establish its conformance. |
| [Library boundary refactor — 2026-10-13](three-repository-refactor-2026-10-13/README.md) | Owner boundaries, installed-package tests, walkthrough checks, Rhino checks and the required consumer migration for ADR-007. |
| [Bundle T1 evidence — 2026-10-14](bundle-t1-2026-10-14/README.md) | Schema, IO and verification boundaries of the first Bundle development checkpoint. |
| [Independent notebook Geometry viewer — 2026-10-14](independent-geometry-2026-10-14/README.md) | RK took ownership of the notebook geometry viewer source, locked dependencies and build in `tools/geometry`; the packaged renderer was unchanged. |
| [Investigation Bundle — 2026-10-14](investigation-bundle-t1-2026-10-14/README.md) | Producer checks for the expanded Bundle, which delivers a Model with its investigation context, and the remaining format and adoption gates. |
| [T2 selective Bundle reads — 2026-10-14](t2-technical-2026-10-14/README.md) | Exact record-path filtering and direct record-index reads with parameterised DuckDB predicates and limits. |
| [Walkthrough branch split — 2026-10-14](walkthrough-branch-split-2026-10-14/README.md) | Frozen legacy walkthrough sources on `develop`, the retained draft on `codex/walkthrough-acausal`, shared data and integration checks. |
| [T3 integration — 2026-10-15](t3-integration-2026-10-15/README.md) | Integration of the investigation Bundle and selective-read changes into `develop`, with the retained wheel hashes and Bundle test results. |
| [Graph read cost and exact record lookup — 2026-10-21](graph-read-cost-2026-10-21/README.md) | A bounded repair of graph read cost and exact record lookup for a 1,024-node, 1,024-Relationship consumer target, with the retained performance limits. |
| [Guarded semantic export experiment — 2026-10-21](graph-semantic-export-2026-10-21/README.md) | A bounded copy-elimination experiment for semantic export. It was not cleared for delivery. |
| [Bundle opening cost — 2026-10-22](bundle-open-cost-2026-10-22/README.md) | The Bundle Reader validated each retained document three times. It now validates each document once and reuses one slot table per kind. Measured on a 1,024-node, 1,024-Relationship consumer growth fixture. |

Add new dated evidence as a new folder with its own README. Do not rewrite
archived evidence.
