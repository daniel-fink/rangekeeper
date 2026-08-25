# Rangekeeper Grasshopper components

The Grasshopper project is the source-authoring side of Rangekeeper's graph
model. It associates Rhino geometry with stable domain entities, constructs
classified relationships and assemblies, validates the result, and emits a
canonical Rangekeeper Snapshot for publication.

The current C# implementation is a legacy Rhino 7/Speckle v2 implementation.
Phase 6 of the
[`GRAPH_REFACTOR_IMPLEMENTATION_PLAN.md`](../GRAPH_REFACTOR_IMPLEMENTATION_PLAN.md)
replaces it directly; backwards compatibility is not a goal.

## Target architecture

```text
Rhino 8 model objects
    -> Rangekeeper entities, labels, relationships, and assemblies
    -> validation and canonical Snapshot
    -> geometry + stable IDs + ordinary metadata
    -> official Speckle v3 Data Object and Collection components
    -> explicit Publish
```

Rangekeeper owns the domain graph. The official Speckle connector owns Rhino
geometry conversion, connector-specific Grasshopper types, authentication,
model selection, transport, and publication.

The Rangekeeper C# model and components must therefore:

- remain independent of Speckle `Base` and connector-internal Goo/wrapper types;
- mirror the canonical Python concepts and Snapshot schema;
- preserve immutable domain IDs separately from Rhino object IDs, Speckle
  `applicationId`, and Speckle content IDs;
- serialize deterministically so C# and Python can share fixtures;
- expose ordinary Grasshopper-compatible values at the connector boundary;
- validate the complete graph before publication; and
- require an explicit user-controlled publication trigger.

The root Speckle Collection carries the canonical Snapshot envelope. Individual
geometry Data Objects carry stable entity-association metadata for inspection
and geometry lookup. Collection nesting or display geometry is not the source of
truth for graph reconstruction.

## Intended component groups

The exact component names will be finalized during the Phase 6 implementation,
but the supported surface is organized around these responsibilities:

1. **Taxonomy and Classification** — define owned classification terms and
   optional arborescences.
2. **Entity** — associate stable identity, name, primary classification,
   labels, measures, features, provenance, and optional Rhino geometry.
3. **Relationship** — connect source and target entity IDs using a required
   relationship Classification.
4. **Assembly** — define explicit entity and relationship membership without
   synthesizing `member_of` edges.
5. **Model and Validation** — collect the complete graph and report actionable
   validation diagnostics.
6. **Snapshot and Speckle Export** — produce the canonical Snapshot envelope and
   ordinary geometry/metadata outputs consumed by official Speckle v3 nodes.

## Source acceptance model

The end-to-end acceptance assets are:

```text
Tests/exampleDesign.3dm
Tests/exampleDesignConfig.ghx
```

`exampleDesignConfig.ghx` will be rebuilt for Rhino 8 using native model-object
querying where practical. It must not depend on EleFront, Speckle v2 components,
or the legacy Rangekeeper Entity/Assembly implementation.

The legacy published result provides the semantic regression baseline:

- 50 canonical entities;
- 63 relationships;
- 49 `spatiallyContains` relationships;
- 3 `contains` relationships; and
- 11 `services` relationships.

The inspected source baseline is 735 Rhino objects across 30 layers, with 12
semantically tagged mass objects. The legacy GHX contains 222 components and
Speckle connector 2.17.1 nodes. These source counts help detect accidental loss;
the rewritten GHX is expected to be smaller and does not need to preserve its
legacy component count.

Matching those counts is necessary but not sufficient. Acceptance also checks
stable identity, endpoint associations, classifications, labels, assemblies,
Snapshot round-trip equality, geometry association, and the walkthrough's
numerical results.

## Development and testing

Pure domain logic and cross-language Snapshot fixtures should run on macOS and
Windows. Rhino, Grasshopper, the official Speckle v3 connector, and publication
are accepted on the dedicated Windows host.

Provisioning, SSH/Codex handoff, build/install commands, interactive steps, and
the acceptance checklist are documented in
[`WINDOWS_DEVELOPMENT.md`](WINDOWS_DEVELOPMENT.md).
