# Work on the walkthrough branch

The [walkthrough guide](../guides/walkthroughs.md) tells readers how to run and
build the book. This page is the contributor procedure for its draft branch and
its publication. The general branch rules are in the
[contributor guide](README.md#working-folder-and-branches).

## Branches

| Branch | Contents |
| --- | --- |
| `develop` | The current library. It also keeps the original `walkthrough/` sources and configuration from commit `2c514cbc0e8c5436d65c142166e5bf3d56609f88` as historical teaching material. |
| `codex/walkthrough-acausal` | The draft book under `examples/walkthrough/`. |
| `acausal-modelling` | The complete work before the library and the book were split. Keep it as a recovery reference. |
| `gh-pages` | The published HTML. GitHub Pages serves the root of this branch. |

The original `walkthrough/` sources on `develop` do not show that they work with
the current library.

## Change the draft book

1. Before you change branches, run `git status --short --branch`. Save unfinished
   work on its owning branch.
2. Switch to `codex/walkthrough-acausal` for notebook and book work. You can use
   the same checkout as for library work; a separate worktree is not necessary.
3. Commit and push drafts on that branch.
4. To get library updates, merge `develop` into `codex/walkthrough-acausal`. When
   dependencies change, refresh the walkthrough environment lock and check it.
5. Return to `develop` when the draft work is saved.

Do not change the bytes or provenance of the shared source capture in
[`examples/data/mixed_use_property`](../../examples/data/mixed_use_property).

## Publish the book

Code and draft pushes do not publish the book. Keep the Pages source and
`gh-pages` unchanged while the book is in progress. When the book is ready:

1. Execute and validate the notebooks, then check the local preview. The
   [walkthrough guide](../guides/walkthroughs.md#execute-for-acceptance) gives the
   commands.
2. Merge the draft source into `develop`.
3. Publish the reviewed HTML to `gh-pages` as a separate, explicit action.

A source merge alone does not publish the book.

## History

The [14 October 2026 split record](../history/handoffs/2026-10-14-repository-and-walkthrough.md)
and the [consolidation record](../history/handoffs/2026-10-14-single-folder-consolidation.md)
record how the branches were created and verified. They describe the layout at
that date, not the current procedure.
