# Bundle opening cost — 22 October 2026

## Result

`Reader(path)` validated each retained document three times: once in
reconstruction and twice more through `snapshot` (in `_Documents` and in
`_collect`). The Reader now keeps the documents it reconstructed and validated,
without a snapshot. It also reuses one slot table per kind during
reconstruction. Every existing check remains: file inventory and hashes,
reconstruction, one complete validation per document, the derived index
comparison, descriptor and Bundle identity, and the dependency closure.
Documents given to `write` by a caller are still validated as snapshots.

`Reader(path, check_index=False)` skips the derived index comparison and keeps
the index schema and file hash checks. A consumer that has already opened the
Bundle with the full check, and checks its manifest before each later open, can
use it for later opens. Version `0.10.0.dev6`.

## Measurement

Fixture: the WW-51 growth Model, 1,024 nodes and 1,024 Relationships, 93,212
records, 17.5 MB as JSON. Apple Silicon, Python 3.12, Arrow 23.0.1, DuckDB 1.4.3.
One run each; times include no profiler.

| Step | Before | After |
| --- | ---: | ---: |
| `Model.from_data` from JSON, for comparison | 5.3 s | 5.3 s |
| `Reader(path)` | 23.2 s | 10.8 s |
| of which validation (`Model.from_data`) | 13.2 s | 4.5 s |
| of which derived index comparison (`_shred`) | 2.3 s | 2.2 s |
| of which document digests | 1.5 s | 1.6 s |
| `Reader(path, check_index=False)` | — | 7.1 s |

## Checks

`test_opening_validates_each_retained_document_once` fails before the change and
passes after it. `test_index_check_rejects_a_rehashed_index_unless_it_is_skipped`
shows that the default open refuses an index that disagrees with its tables even
when the manifest hashes match, and that `check_index=False` still refuses a
changed file. Both are in `src/tests/test_bundle.py`.

## Remaining limits

A 1 vCPU server is about 2.5 times slower than this machine. The opening cost
on such a server is not measured here.
