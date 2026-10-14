# Walkthrough branch split — 14 October 2026

The [integration record](integration.json) pins the saved checkpoint, preservation
baseline and checks. The prepared code merge retains all runtime and schema files
from that checkpoint. `develop` keeps the complete original `walkthrough/` tree;
the acausal draft continues on `codex/walkthrough-acausal`. See the
[branch procedure](../../guides/walkthroughs.md#branches-and-publication).

## Integration checks

- All 177 tracked legacy walkthrough files match the old `develop` byte for byte.
- All 10 mixed-use capture files match the checkpoint at their new shared location.
- 852 library tests and 26 SQLite tests pass. The two draft helper tests stay with
  the draft branch and are not counted in this library total.
- Python and C# generated artifacts are current; all 16 native fixture round trips
  pass. Typing checks pass for 142 valid sources and all intended invalid fixtures.
- A clean source archive builds a wheel. Installed-wheel checks pass for records,
  units, IO, graph reduction, finance, forward/inverse execution and Polars tables.
  The wheel includes Geometry assets and excludes the walkthroughs and examples.
- The documentation navigation check passes. Full-merge whitespace findings occur
  in 42 pre-existing files, all unchanged from the checkpoint. Captured evidence
  and third-party generated files were not reformatted.

Run checks from the repository root, with the declared runtime extras and the
pinned schema tools installed. Use the [verification guide](../../contributing/verification.md)
for commands. These are local macOS results; they do not establish new Windows,
Rhino, external-service or publication acceptance. The legacy notebooks were
preserved, not migrated or re-executed against the new library.

Pages remains configured for `gh-pages` at `/`. Publication is a separate action.

## Draft verification

The draft starts from `develop` merge `3d70ece` and restores the saved walkthrough
from `097a26e` in a new commit. [Draft checks](draft.json) record its scope.
The local environment now requests RK 0.9's `calculations`, `execution` and
`visualisation` extras. Its lockfile is current.

The shared capture is outside the notebook directory. Geometry displays serve
both directories from one explicit local root. The new regression test fetches
the descriptor and all three retained source files through that server and checks
their hashes. Book staging generates its own relative geometry descriptor, adapts
source links and iframe paths, and keeps the packaged viewer manifest current.

All [81 active notebook cells](draft-notebooks.json) pass in fresh Python 3.12.12
kernels against the exact wheel recorded in the integration manifest. The
[independent financial audit](draft-finance-audit.json) passes. Three helper tests
pass. Jupyter Book 2.1.7 builds all four pages with `--strict`.

Browser review confirms the Notebook 02 geometry view, selection of
`buildingAhotelFloor1` with GFA 1,697.452 m², chapter navigation, tables and embedded
outputs. Notebook 03's development cash-flow chart renders with labelled years
and AUD values. No browser console errors were observed during these checks.
This is a local preview, not a Pages deployment or full curriculum acceptance.

Authored notebook outputs and metadata remain as saved in the checkpoint. Fresh
executions and the reviewed site were generated separately; the builder rejects
stale helper sources. Retained historical build files were not republished.

New code/schema edits appeared in the original `acausal-modelling` working tree
after the checkpoint. They were left untouched and are outside this split.
