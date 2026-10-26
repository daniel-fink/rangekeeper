# Work on the walkthrough

The [walkthrough guide](../guides/walkthroughs.md) tells readers how to run and
check the lessons. This page is the contributor procedure for the lessons and
their publication. The general branch rules are in the
[contributor guide](README.md#working-folder-and-branches).

## Branches

| Branch | Contents |
| --- | --- |
| `develop` | The library and the walkthrough under [`examples/walkthrough`](../../examples/walkthrough/README.md). It also keeps the original 2022 notebooks in `walkthrough/` as historical teaching material. |
| `codex/walkthrough-acausal` | The interim draft book under `examples/walkthrough/`, with the Jupyter Book 2 build. Read it as source material. Do not push to it. |
| `acausal-modelling` | The complete work before the library and the book were split. Keep it as a recovery reference. |
| `gh-pages` | The published HTML. GitHub Pages serves the root of this branch. |

## Change a lesson

1. Start a `feature/<issue>-<slug>` branch from `develop`, as for library work.
2. Change the lesson, the helpers or their tests under `examples/walkthrough`.
   Keep the [rules for lessons](../../examples/walkthrough/README.md#rules-for-lessons).
3. When dependencies change, refresh the lock with
   `uv lock --project examples/walkthrough` and check it.
4. Execute the lessons from fresh kernels and run the walkthrough tests. The
   [walkthrough guide](../guides/walkthroughs.md#execute-for-acceptance) gives the
   commands.
5. Open a pull request into `develop`.

To reuse draft material from `codex/walkthrough-acausal`, copy it onto your
feature branch and bring it up to the current API. Do not merge that branch.

Do not change the bytes of the shared source capture in
[`examples/data/mixed_use_property`](../../examples/data/mixed_use_property/README.md).
A change to a teaching assumption needs a matching change to its manifest entry
and its origin in `origins.json`.

## Publish the book

Code and lesson merges do not publish the book. Keep the Pages source and
`gh-pages` unchanged while the book is in progress. When the book is ready:

1. Execute and validate the lessons, then convert them and check the local
   preview of the docs site.
2. Publish the reviewed HTML to `gh-pages` as a separate, explicit action.

## History

The [14 October 2026 split record](../history/handoffs/2026-10-14-repository-and-walkthrough.md)
and the [consolidation record](../history/handoffs/2026-10-14-single-folder-consolidation.md)
record how the branches were created and verified. They describe the layout at
that date, not the current procedure.
