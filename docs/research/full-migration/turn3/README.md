# Turn 3 verification index

Start with [BASELINE.md](BASELINE.md) for environments, preservation, scope and
limitations, and [COMMANDS.md](COMMANDS.md) for reproduction. The
[implementation contract](../../../history/FULL_MIGRATION_TURN3.md) describes the public
interfaces. The [retirement register](RETIREMENT.md) names what Turn 4 may remove
and what the unresolved Windows connector gate still holds.

| Check | Observed result | Retained evidence |
|---|---|---|
| Full RK local suite | **1,061 passed, 24 skipped, 7 warnings** | [text](complete-suite.txt), [JUnit](complete-suite.xml) |
| Seven schema suites | All pass; Run suite repeated after the scoped-index correction | [commands](checks/commands.jsonl), [Run result](accepted-schema-runs.txt), `checks/schema-*.txt` |
| Python generation | Fresh | [result](accepted-generation.txt) |
| Static typing | 168 source files pass; all intended invalid calls rejected | [result](complete-typing.txt) |
| Exact installed wheel | Records, codecs, stores, lightweight imports, artifacts, numerical library, scalar execution and source workflow pass | [result](complete-installed.txt), [wheel](complete-wheel.txt), [fingerprint](artifact-final.json) |
| Seven walkthroughs | All run from that wheel in fresh kernels; four paired uncertainty scenarios | [commands/results](complete-notebooks.txt), [source/output fingerprints](notebook-fingerprints.json), [generated site](../../../../examples/walkthrough/_build/html/index.html) |
| Upgrade-guide examples | Pass outside the checkout | [script](guide_example.py), [captured output](complete-guide.txt) (empty on success) |
| Viewer | 35 unit checks pass; browser-only case then passes in actual Chrome | [unit](viewer-tests.txt), [browser](viewer-browser.txt) |
| Workbench, layouts and transport | Included in full suite; 86 scoped tests pass, 24 MiniZinc skips | [JUnit](complete-suite.xml), [scoped result](complete-layout.txt) |
| Three source builds | Mandarin, December and November R2 pass | [result](complete-project-builds.txt) |
| Exact historical comparisons | Domain, lineage and checks agree under named representation mappings | [result](complete-project-comparisons.txt), [comparator](compare_projects.py) |
| Project tests and tooling | Mandarin 8 pass/1 separate-reference skip; East Whisman 6 pass; Ruff and ty pass | [result](complete-project-tests.txt) |
| Older Mandarin SOM comparison | All 3 tests pass in a separate process | [result](complete-mandarin-history.txt) |
| Mandarin review | Fresh kernel executes all 5 code cells from wheel-only Python 3.13 | [result](complete-mandarin-notebook.txt) |
| Full-size design on Python 3.10 and 3.13 | 36 contributors, 4,541 unknowns, 302 source Claims preserved; normal validation/export pass | [summary](large-design-summary.json), [3.10](accepted-design-310.txt), [3.13](accepted-design-313.txt) |
| Independent real-design arithmetic | All 4,541 quantities, dates, components, reversion and PV agree | [3.10](complete-design-oracle-310.txt), [3.13](complete-design-oracle-313.txt), [oracle](design_oracle.py) |
| New pinned Speckle read | Pass; 36 Entities, 14 Assemblies, 63 relationships | [result](complete-live-read.txt) |
| C# generation/build | Fresh generated records; component and test builds have no errors/warnings | [freshness](accepted-csharp-freshness.txt), [components](dotnet-components.txt), [tests](dotnet-tests.txt) |
| C# semantics and cross-language | Presence, identity, detachment, duplicate checks and full rich/ordered round trip pass | [pure checks](csharp-tests.txt), [Python check](accepted-cross-language.txt) |
| Rhino 8 host | Recompute and reopen pass; identity stable and revision predecessor retained | [host](rk-ghx-report.json), [components](rk-ghx-state.json), [semantic comparison](rhino-comparison.json) |
| Documentation | Rebuilt from accepted outputs; captured Plotly rendered offline; no build warnings | [build](complete-book.txt), [retention](complete-book-retention.txt) |
| Consumer dependency scan | 0 runtime legacy references in migrated RK consumers and 17 active project sources | [RK](legacy-dependencies.json), [Projects](project-dependencies.json) |
| Preservation | 91 protected files unchanged; wheel matches source; HEADs unchanged and indexes empty | [result](accepted-preservation.txt), [hashes](preservation-final.json), [closing state](closing-state.json) |

One additional profiled Python 3.10 process hit a native allocator crash after
returning a feasible Run. Both normal reruns passed; the cause remains unresolved.
See [the bounded diagnostic](large-model-runtime-crash.json).

The 24 skipped tests require MiniZinc (18 CP-SAT checks, four dual-engine checks,
two optional-solver checks). The three old live tests are excluded rather than
silently marked passing. The seven warnings are retained legacy pandas aliases.
The Windows official connector gate remains open, with an explicit fixture and
[acceptance procedure](../../../contributing/windows-acceptance.md). No external
publication was attempted. Hypar is retired; Browser/outliner remains on hold.

Real source data, live payloads, real output Models, private comparison maps,
environments and caches are not part of this retained evidence. Public walkthrough
outputs use synthetic fixtures. Older interim `.log` files remain local and
ignored; the selected accepted reports use `.txt` so they can be retained without
changing the user's ignore rules.

[Process exit codes](completion-exit-codes.json), [generated artifact hashes](generated-book-hashes.json),
and [retained evidence hashes](evidence-hashes.json) close this acceptance record.
