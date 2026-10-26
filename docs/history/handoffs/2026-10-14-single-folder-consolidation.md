# Single-folder consolidation — 14 October 2026

> Edited extract, 17 October 2026: external application references were removed.
> Retained RK results keep their original scope; this is not an unchanged capture.

Status: current development code, including the Bundle candidate, is on `develop`.
The unfinished walkthrough remains on `codex/walkthrough-acausal`. The sole RK
working folder was the primary local checkout, with `develop` checked out.
This integration does not approve the Bundle format for release or adoption by the primary consumer.
No walkthrough publication or primary consumer migration was performed.

## Saved commits and branch roles

These are the verified code and validation checkpoints before this documentation
update. Later documentation commits can advance the working branches. Check
`git status --short --branch`, `git log -1 develop`, and
`git log -1 codex/walkthrough-acausal` before continuing work. Fetch the remote
when its latest state is needed; do not assume these hashes are still the tips.

| Branch or checkpoint | Commit | Retained purpose |
| --- | --- | --- |
| `codex/core-lifecycle-bundles` | `e03b6c437b6aa8b4b9584adf805271d80e5889ba` | Pushed recovery checkpoint of the 35 explicitly staged candidate files. |
| Candidate merge into `develop` | `3b596718b80a974ed53994e3866d9c08d5193886` | Bundle candidate combined with the newer repository-state documentation. |
| `develop` validation checkpoint | `6837b9adbe30a05c331d279563edc6d4a92d48cf` | Historical SQLite compatibility repair after combined testing. |
| `codex/walkthrough-acausal` validation checkpoint | `3d45a922338ce3dec1c18188da3291c1e07b28e8` | Merged development code, refreshed draft lock and local notebook/book evidence. |
| `acausal-modelling` | `097a26e68ce2926f6323f0873346b36537550219` | Unchanged saved checkpoint before the branch split. |
| `feature/assembly-layout-constraints` | `4e5aec42f16a18c4d715f5a2a1b879d98e0f71e3` | Retained branch and remote checkpoint after removal of its old worktree. |
| `main` | `6732e83d277c8de81f3dec2906e06d0e75d3b6fa` | Unchanged. |
| `gh-pages` | `06c085aa5d4d5a7fd213d913d9ab3138d54de02b` | Unchanged published site. |

GitHub Pages remains branch-based publishing from `gh-pages`, directory `/`,
with `build_type: legacy`. No Pages setting or publication command was changed.
The [previous split record](2026-10-14-repository-and-walkthrough.md) is preserved
as historical evidence. Its worktree table describes the earlier state; use the
[walkthrough guide](../../guides/walkthroughs.md#branches-and-publication) for the
current single-folder procedure.

## Preservation and recovery

The complete 177-file `walkthrough/` tree, including tracked build files, remains
byte-for-byte identical to the original baseline. Its Git tree is
`f9259ab9edc03062dd2f611e63a2e26dcfc125ab`.
The shared `examples/data/mixed_use_property` tree is unchanged at
`c911cee08e5f1a05eb53918773bc479e91cf02fb`.
The previous repository-state note remains blob
`85fb7a67c1111690bcf825bef7285b6888864541`.

`develop` contains none of the tracked draft `examples/walkthrough/` files,
`tools/docs/build_book.py`, `tools/docs/render_property.py`, or
`src/tests/test_walkthrough_plots.py`. Those stay on the draft branch. The new
schema and library code were merged into that branch, not its draft files back
into `develop`. Authored notebooks were unchanged during validation.

Both managed worktrees were archived through their owning Codex chat after their
clean, pushed commits and ignored contents were checked. Recoverable archive
records remain. The manual `rk-core-lifecycle` and `rk-assembly-layout` worktrees
were removed without force after their clean branches matched their upstreams.
Branches and recovery commits were retained. No uncommitted work was discarded.

Local recovery material is retained outside the RK working folder under
`[external path omitted]`:

- `recovery.gitbundle`: verified complete history for the five development,
  walkthrough and recovery refs listed above.
- `preserved/rk-assembly-layout/`: 1,926 retained artifact/toolchain files and links,
  with 626,290,107 file bytes copied and hash-verified; its manifest records paths.
- `preserved/primary-walkthrough-ignored/`: the original folder's ignored draft
  outputs and environment, retained with a byte/link inventory after switching
  to `develop`. These are recovery material, not an active second checkout.
- `preserved/primary-property-viewer-ignored/`: 9,403 ignored legacy walkthrough
  renderer files and links, moved with a verified inventory.
- `source.tar`, `dist/`, `build.json`, `execution-verified/`, `finance-audit.json`
  and `book/`: the source, wheel, fresh outputs, independent audit and local preview.

Ignored recovery files are not protected by a Git push. Back them up separately.
Reproducible caches/builds/environments in the removed auxiliary worktrees were
not treated as unique source. Other ignored content in the primary folder was
preserved. Do not recreate the auxiliary worktrees for routine development.

## Verification and remaining work

The [candidate and combined draft evidence](../../research/bundle-t1-2026-10-14/README.md)
records commands, environments, wheel hash and limits. Library tests: 858 passed.
The combined check exposed a collision in the older SQLite experiment when it
read the new live schema. The repair pins its exact original Model 0.7 schema and
rejects newer Models before writing. All 27 SQLite tests then passed; an existing
database reopened with network and original capture access blocked.

Python/C# generated artifacts, 16 native fixture round trips, typing with expected
negative fixtures, and installed-wheel checks passed. The installed checks cover
actual forward/inverse solves, PyXIRR and Polars as well as the minimal record
boundary. All 81 active notebook cells, the independent financial audit and three
walkthrough helper tests passed. The strict Jupyter Book 2.1.7 build and local
browser checks passed within their recorded scope. The older recorded C# check
used explicit .NET 10 roll-forward for its .NET 8 target; native .NET 8 and Rhino
host acceptance remain open.

The candidate wheel was built from the clean `3b59671` source archive; the later
SQLite repair changes only the historical tool, not installed RK source. Its
SHA-256 is `534ca425f25cbeb5e6c2c6530b94516091e1811aada0d788939153c9cfe03467`.
The final documentation update does not change that runtime artifact.

Continue the primary consumer refactor against this exact committed engine and wheel. Keep
format review and unclosed ADR-008 P1–P8 cases visible: exhaustive presence/union
coverage, native formats/assets, change cases, scale and hostile-file bounds,
complete queries, render conversions and real-host evidence remain incomplete.
The primary consumer's full PA0–PA5 contract and required remote ingestion acceptance also remain
open. Development integration is not format approval.

Notebooks 04–06, complete-book acceptance, public edit/source links, redirects
and publication remain separate walkthrough work. Continue it on the draft branch.
Do not change `main`, `gh-pages`, Pages settings, the saved acausal checkpoint or
the primary consumer as a consequence of this consolidation.
