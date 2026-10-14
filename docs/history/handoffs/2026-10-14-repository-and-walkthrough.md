# Repository and walkthrough state — 14 October 2026

Status: **branch split complete; draft walkthrough not published**.

This record describes the completed code and documentation split. The remote
commits and Pages settings below were checked on 14 October 2026, before this
record was added. Later documentation commits can advance the branches; these
commits remain the reference points for the split. Use the
[walkthrough guide](../../guides/walkthroughs.md#branches-and-publication) for the
maintained workflow and execution commands.

## Branch state

| Branch | Verified commit | Role and contents |
| --- | --- | --- |
| `acausal-modelling` | [`097a26e`](https://github.com/daniel-fink/rangekeeper/commit/097a26e68ce2926f6323f0873346b36537550219) | Pushed checkpoint of all work saved before the split, including the draft walkthrough. |
| `develop` | [`3d70ece`](https://github.com/daniel-fink/rangekeeper/commit/3d70ece757a2ce7ff6a329b7b3cfcb6ef0835363) | Pushed code merge. The complete original `walkthrough/` tree is preserved. The draft `examples/walkthrough/` tree and its dedicated tools and tests are absent. |
| `codex/walkthrough-acausal` | [`133cc8f`](https://github.com/daniel-fink/rangekeeper/commit/133cc8f73139da06bccc17fe68db2f2a53afb5d2) | Pushed draft commit above the new `develop`. Contains the updated book, tools and helper tests. The original top-level `walkthrough/` tree is removed here. |
| `main` | [`6732e83`](https://github.com/daniel-fink/rangekeeper/commit/6732e83d277c8de81f3dec2906e06d0e75d3b6fa) | Unchanged by the split. |
| `gh-pages` | [`06c085a`](https://github.com/daniel-fink/rangekeeper/commit/06c085aa5d4d5a7fd213d913d9ab3138d54de02b) | Unchanged published site. |

GitHub Pages uses branch-based publishing from `gh-pages`, directory `/`.
The API reported `build_type: legacy` and `status: built`. The
[live site](https://daniel-fink.github.io/rangekeeper/) was not redeployed by this
work. No Pages setting changed.

The integration branch `codex/integrate-acausal` points to `3d70ece` locally.
Its worktree now has `develop` checked out. It is a preparation reference, not a
separate ongoing code branch.

## Preserved sources and shared data

The preservation baseline is the previous `develop` commit
[`2c514cb`](https://github.com/daniel-fink/rangekeeper/commit/2c514cbc0e8c5436d65c142166e5bf3d56609f88).
All 177 tracked files under `walkthrough/`, including the tracked build files,
match that baseline byte for byte on the new `develop`. The tree object is
`f9259ab9edc03062dd2f611e63a2e26dcfc125ab`.

The draft was restored in a new commit above the code merge. It is therefore an
explicit change that can later merge back into `develop`; it is not only a copy
held on the already-merged checkpoint branch.

Both working branches use the shared capture at
[`examples/data/mixed_use_property`](../../../examples/data/mixed_use_property).
All 10 retained data files preserve the checkpoint bytes and provenance. SQLite
tools use this shared location. The draft notebooks and geometry display also
use it. Shared library code, including the Geometry viewer, remains on `develop`.
The split adds no public library API changes.

## Local worktrees

These paths identify the worktrees on the machine used for this split. They are
local locations, not requirements for another clone.

| Use | Branch | Local path |
| --- | --- | --- |
| Code development | `develop` | `/Users/daniel/.codex/worktrees/integrate-acausal/Rangekeeper` |
| Walkthrough writing and preview | `codex/walkthrough-acausal` | `/Users/daniel/.codex/worktrees/walkthrough-acausal/Rangekeeper` |
| Saved checkpoint checkout | `acausal-modelling` | `/Volumes/Data/Projects/Rangekeeper` |

Use `git status --short --branch` before changing branches or committing work.
The code and draft worktrees were clean after the split. Further code and schema
edits appeared in the original checkout during integration. They were excluded
from the saved checkpoint and merge, and were left untouched. This record does
not claim to capture work done after `097a26e` in other feature branches or
worktrees.

## Verification completed

The [integration evidence](../../research/walkthrough-branch-split-2026-10-14/README.md)
records the preserved tree, shared-data hashes and package checks. The
[complete draft evidence at its saved commit](https://github.com/daniel-fink/rangekeeper/blob/133cc8f73139da06bccc17fe68db2f2a53afb5d2/docs/research/walkthrough-branch-split-2026-10-14/README.md)
records notebook and preview acceptance.

- Code: 852 library tests and 26 SQLite tests passed. SQLite offline reopen,
  generated Python and C# artifacts, 16 native fixture round trips and typing
  checks passed.
- Packaging: a clean source archive and wheel built. Installed-wheel checks
  passed. The wheel includes Geometry assets and excludes the walkthroughs and
  examples.
- Documentation: local links and navigation passed on both branches.
- Draft: three helper tests and all 81 code cells across the three active chapters
  passed. The independent financial audit passed. Fresh kernels used Python
  3.12.12 and the verified Rangekeeper 0.9.0 wheel.
- Preview: Jupyter Book 2.1.7 built the introduction and three chapters with
  `--strict`. Browser checks covered navigation, tables, the 3D view and object
  selection, and the development cash-flow chart. No console errors were observed.

These are local macOS checks. They do not establish new Windows, Rhino, remote
CI or external-service acceptance. The legacy notebooks remain historical
sources; their preservation does not establish that they run against the new
API. Saved notebook outputs and metadata remain as in the checkpoint. Fresh
execution results and the local preview were generated separately.

## Continue work and publish later

Develop library code from `develop`. Write and preview the book in the draft
worktree on `codex/walkthrough-acausal`. Merge later code updates from `develop`
into that branch as needed. Follow the
[walkthrough guide](../../guides/walkthroughs.md) for its locked environment,
fresh-kernel execution and local book build.

The current local book contains the introduction and notebooks 01–03:
`basic_dcf.ipynb`, `design_to_value.ipynb` and `development_feasibility.ipynb`.
Notebooks 04–06 remain planned under the
[agreed curriculum](../../decisions/006-walkthrough-curriculum.md). Remaining
source migration, complete-book acceptance, old-URL redirects and public
publication remain open.

When the walkthrough is ready, validate the notebooks and rendered book, then
merge the draft source changes into `develop`. Publish the reviewed HTML to
`gh-pages` only as a separate, explicit action. Until that step, keep `gh-pages`
and the Pages source unchanged. Ordinary code and draft pushes do not publish
the walkthrough.
