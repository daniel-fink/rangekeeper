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
