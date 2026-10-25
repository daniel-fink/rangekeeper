# ADR-009: Classification filters include sub-types

Status: implemented. Recorded: 2026-10-25.

## Problem and choice

A Taxonomy is a tree of Classifications. Each Entity has at most one
Classification, usually a specific leaf such as "2B+S". A filter by a parent,
such as "2B", matched only Entities classified exactly as that parent. Most
Entities have a leaf Classification, so a parent filter usually matched nothing.
A caller who asked for "two-bed apartments" had to collect the sub-types itself.

`View.filter(entity_classification=…)` and `relationship_classification=…` now
match the Classification and all its descendants in its Taxonomy. The new
`exclusive=True` argument keeps the earlier exact match. The `classified`
contributor rule for `Reduction` uses the same convention.
`Model.descendants(id)` and `definitions.descendants(definitions, id)` expose the
sub-type set. They follow each Classification's `parent`.

## Alternatives and consequences

Keeping exact matching as the default would keep earlier results the same. But
every caller would then have to expand the taxonomy itself to get the usual
meaning of a class. An inclusive default matches how a taxonomy is read: a "2B"
includes "2B+S".

Callers that relied on exact matching for a parent Classification get more
Entities. They must pass `exclusive=True`. Leaf Classifications have no
descendants, so their results do not change. `Model.find_entities` stays an exact
search by code, name and classification. No record, schema or wire format changes.

## Sources and related decisions

- [System views and reductions](../reference/system.md#selection-and-traversal).
- [Upgrading](../guides/upgrading.md#candidate-010-classification-filters).
- [Model lookup](../reference/model.md).

Supersedes: the exact-match filter rule in the system reference. Superseded by: none.
