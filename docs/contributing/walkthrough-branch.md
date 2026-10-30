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

## Publish the site

Code and lesson merges do not publish the book or the docs site. Keep the Pages
source and `gh-pages` unchanged while the book is in progress. Today `gh-pages`
holds the earlier book at its root.

Zensical's fork of mike publishes each release line in its own folder, `/1.0/`
from `develop` and `/0.8/` from `support/0.8`. It also writes `versions.json`,
which the version selector reads. Publication needs explicit approval.

How mike works with this repository:

- `mike deploy VERSION` runs `zensical build --clean` on the staged pages in
  `_build/docs`, with the version in the site URL. It does not stage the pages,
  and its build is not strict. Run `tools/docs/site.py build` first: it stages
  the pages and runs the strict build.
- It commits the built site to the local branch that `remote_branch` in
  `zensical.toml` names (`gh-pages`), in the folder `VERSION/`, and writes
  `versions.json` and `.nojekyll` at the root. The other files on the branch do
  not change, so the earlier book stays at the root.
- Before the commit, it compares the local branch with `origin/gh-pages`. It
  does not fetch. It moves a local branch that is behind to `origin/gh-pages`,
  and stops when the two branches have diverged.
- Without `--push`, it changes only the local branch.
- `mike set-default VERSION` replaces the root `index.html` with a redirect to
  `VERSION/`. The other root files of the earlier book stay.
- `mike serve` serves the local branch, with the version selector, on
  http://localhost:8000.
- `--branch NAME` uses another branch for each command. Use a new branch name to
  preview a publication without a change to `gh-pages`.

The [verification of 30 October 2026](../research/docs-site-versions-2026-10-30/README.md)
records these results. When the book is ready:

1. Execute and validate the lessons. Leave `RK_DESIGN_MODE` and `RK_PATH_COUNT`
   unset, for the full design data and path count. From the repository root,
   make the environment and run the strict build:

   ```sh
   uv sync --locked --all-extras --group versions
   uv run --locked --no-sync python tools/docs/site.py build
   ```

2. Preview the versioned site on a new branch, and check the pages and the
   version selector on http://localhost:8000/1.0/. Then delete the branch:

   ```sh
   uv run --locked --no-sync mike deploy --branch site-preview 1.0
   uv run --locked --no-sync mike serve --branch site-preview
   git branch -D site-preview
   ```

3. With approval, commit the version to the local `gh-pages`. Update
   `origin/gh-pages` first, so that mike starts from the published branch:

   ```sh
   git fetch origin gh-pages
   uv run --locked --no-sync mike deploy 1.0
   uv run --locked --no-sync mike serve
   ```

4. Push `gh-pages` as a separate, explicit action, after a final check of
   `mike serve`:

   ```sh
   git push origin gh-pages
   ```

   The root redirect (`mike set-default 1.0`) replaces the earlier book at the
   root; decide it with the `/0.8/` site
   ([#72](https://github.com/daniel-fink/rangekeeper/issues/72)), which also
   builds the `/0.8/` site.

## History

The [14 October 2026 split record](../history/handoffs/2026-10-14-repository-and-walkthrough.md)
and the [consolidation record](../history/handoffs/2026-10-14-single-folder-consolidation.md)
record how the branches were created and verified. They describe the layout at
that date, not the current procedure.
