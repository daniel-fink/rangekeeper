# Turn 4 baseline and acceptance — 6 October 2026

The accepted Turn 3 work was committed and pushed before deletion:

| Repository | Branch | Checkpoint |
|---|---|---|
| Rangekeeper | `acausal-modelling` | `305f3ff6d460834ea803bae2fa6ad5c48a1627c9` |
| Projects | `feature/mandarin-assembly-layout` | `6146ad2039278db773f3bdc2c159d82149d5abc1` |
| Layout reference, read only | `feature/assembly-layout-constraints` | `4e5aec42f16a18c4d715f5a2a1b879d98e0f71e3` |

Remote branch SHAs matched the two checkpoint commits after pushing. The Turn 4
changes follow those checkpoints and are not committed or pushed. No release,
service publication or private source upload occurred.

`baseline.json` records dirty paths, Python/import environment, dependency versions,
404 verification-input hashes and 91 protected files. Protected content includes
both unrelated `.gitignore` edits, the Syncthing conflict copy, original workbooks,
archives, Rhino model and old GHX. The historical 1,061-pass result is labelled as
Turn 3 evidence. Fresh starting collection found 1,085 tests including the 24
optional skips, excluding the three named live API tests.

## Candidate artifact and environments

All current consumer acceptance uses this one wheel:

```text
rangekeeper-0.8.71-py3-none-any.whl
SHA-256 027a4cd6727a43f30de7b0ddf0cd6adf06355c73e91da5f866157d2c1dcfac14
```

- Runtime: Python 3.10.19; package versions in `baseline.json`.
- Schema: LinkML 1.11.1, linkml-runtime 1.11.1, jsonschema 4.26.0.
- Typing: mypy 1.18.2, 168 sources and explicit negative-call checks.
- Clean core: normal wheel installation and dependency resolution; 13 packages
  including RK. No NumPy, pandas, Polars, plotting, service SDK or solver installed.
- Clean Projects: Python 3.13.11, same wheel with `[workflow,excel]` and named
  test/notebook tools. No editable RK, old project package, archive or earlier
  output participates in a build. No NumPy/pandas/Polars/networkx/Speckle/Pyomo/Plotly.
- Full-feature notebook checks put that wheel's unpacked package first in a
  controlled kernel environment. They do not import RK from the checkout.
- C# uses the existing .NET 8 build and Rhino's installed arm64 runtime. C# source
  is unchanged; generation freshness and a new cross-language fixture pass.

## Results

| Check | Actual result | Evidence |
|---|---|---|
| Full local Python suite | **1,058 passed; 24 skipped** | `full-suite.txt`, `full-suite.xml` |
| Canonical behaviour before deletion | 46 passed | `numerical-migration-final.txt` |
| Canonical behaviour and removal guards after deletion | 59 passed | `retirement-guards-final.txt` |
| All seven schema suites | Passed | `schema-*.txt` |
| Python and C# generation freshness | Passed | `generation.txt`, `csharp-generation.txt` |
| Static typing and intended rejections | Passed | `typing.txt` |
| Installed immutable records, units, codecs, stores, lightweight imports | Passed | `installed.txt`, `core-acceptance-final.txt` |
| Installed PyXIRR-only and process-isolated scalar forward/inverse, reuse and publication | Passed | `installed.txt` |
| Seven walkthroughs, including both design fixtures | Passed in fresh kernels | `notebooks.txt` |
| Three real source builds and strict historical comparisons | Passed | `project-builds.txt`, `project-comparisons.txt` |
| Mandarin tests / East Whisman tests | 8 passed, 1 reference skip / 6 passed; lint and typing passed | `project-tests.txt` |
| Separate older Mandarin SOM comparison | 3 passed | `mandarin-som-reference.txt` |
| Mandarin fresh review notebook | Passed | `mandarin-notebook.txt` |
| Upgrade-guide and documentation examples outside checkout | Passed | `guide.txt`, `documentation-examples-final.txt` |
| Python → C# → Python preservation | Passed | `cross-language-*.txt` |
| Captured Mac Rhino export through candidate Python wheel | 50 objects, 63 relationships; envelope equality passed | `rhino-export-validation.txt` |
| Rebuilt walkthrough site from accepted notebooks | Passed | `book-build-retry.txt`, `retain-book.txt` |
| Dependency lock checks and normal minimal installation | Passed | `lock-check.txt`, project lock logs, install logs |

Source outputs preserve the Turn 3 counts: Mandarin 377 objects/376 relationships
and checks 776 agree, 14 unavailable, 28 difference; December 73/72 and 368 agree,
6 unavailable; November R2 37/36 and 144 agree, 45 unavailable. These retained
business findings are not software failures. Strict comparisons preserve quantities,
units, identities, membership, lineage, source locations, decisions and named null
mappings. Private outputs remain in the isolated workspace.

## Limits and failed attempts

The 24 skips require the optional MiniZinc executable. Three live predecessor API
tests are excluded. The Windows connector gate is still open. This is acceptance
of the permitted retirement slice, not full external integration or full retirement.

The prior profiled Python 3.10 native allocator crash remains an unexplained,
non-reproduced Turn 3 event. This turn changes no execution or validation mathematics
and does not claim to diagnose it. New full-size private design solves and Mac UI
recomputation were not repeated: the corresponding C#/execution sources are unchanged.
The recorded Mac export was revalidated with the new wheel. Browser interaction
acceptance remains the Turn 3 evidence for unchanged viewer assets.

Representative fresh PNGs were inspected for dates, units and labels: signed design
expenses and five-year capital dips; dated hindsight sale alternatives; dimensionless
market components. The static book was rebuilt, but no new in-app HTML preview is
claimed after the earlier local-file browser policy block. Plot data and notebook
outputs remain in the generated book and executed notebooks.

Initial setup failures remain in their logs: missing source import path during
historical capture, migrated-test API mistakes, a stale deleted-test import, an
incorrect acceptance-helper column name, two stale documentation-example imports,
AST handling of a known notebook magic, and a mistaken Plotly asset path. Each has
a passing retry. The sandboxed `uv` environment command failed in macOS system
configuration; Python venv creation plus an authorised normal installation passed.
The final preservation helper initially included deliberately changed runtime/tests
and generated notebook copies in its unchanged-file assertion. Its corrected scope
checks an explicit permitted change list and the original source notebooks; all
91 protected files pass. No failure was hidden by changing expected financial or
source results.

The schema harnesses print historic statements about capabilities outside their
scope. Those lines describe the harnesses, not the present library; execution is
verified separately. Counts are not added across overlapping suites.
