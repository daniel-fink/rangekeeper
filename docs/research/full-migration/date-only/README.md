# Date-only Flow correction

Implemented 2026-10-04 on `acausal-modelling`, HEAD
`90c2e00ba7b942a8830960e3df3f3ff616f30fa1`. This corrects the uncommitted Turn 1
contract after review. It does not advance Turns 2–4 or retire old consumers.
The [original verification](../turn1/README.md) is retained unchanged except for
its supersession note. Model version remains the unreleased **0.4.0**.

The subsequent [financial-library correction](../financial-library/README.md)
retains this date contract and replaces handwritten finance/day-count arithmetic
and the mandatory IRR bracket with PyXIRR. Results below are this earlier checkpoint.

## Contract

- `TimePoint` and its kind enum are removed. Period/Span boundaries are calendar
  dates, with a minimum resolution of one day. Intervals are half-open `[start,end)`.
- Generated date fields accept and expose `datetime.date`; serialization uses
  ISO date strings. No timestamp, timezone or DST interpretation is applied to Flows.
- A FlowSample needs a date or a Period. `from_periods` stores only the Period
  unless an independently known payment/observation date is supplied in `dates=`.
  That date may lie outside its coverage period. Period ordering uses coverage.
- `resolve_date(sample, timing=...)` derives a date only when required. `start`,
  `last_day` and `end` mean first included day, final included day, and exclusive
  boundary. Recorded dates take precedence. Resolution does not mutate content.
- Dated valuation and pandas Series projection require explicit timing for undated
  Periods. Index-based PV retains its explicit `first_period` convention. Trimming
  and resampling use coverage; partial-period allocation is never assumed.
  Period aggregates do not claim one payment date for their contributing samples.
- Source date fields now expose Python dates. Their timestamp alternatives retain
  strings, and their wire format is unchanged. Rich PropertyContent and provenance
  timestamps retain their separate supported meanings.

See [implementation interfaces](../../../history/FULL_MIGRATION_TURN1.md),
[API catalog](api.json), and the [upgrade guide](../../../LEGACY_UPGRADE_GUIDE.md).

## Verification

| Check | Result | Evidence |
|---|---|---|
| Full local regression | **899 passed**, seven existing legacy pandas frequency warnings | [Log](pytest-final.log), [XML](pytest-final.xml) |
| All seven schema suites | Passed | [Commands](commands.jsonl), `final-schema-*.log` |
| Native/public date round trips | Three coordinate forms passed | [Probe](native_dates.py), [log](final-native-dates.log) |
| Reproducible generation | Five artifacts, 56 schema classes match | [Log](final-generation.log) |
| Static checks | 105 source files pass; intended negative cases rejected | [Log](final-typecheck.log) |
| Isolated installed wheel | Dates/timestamp alternatives, lightweight imports, stores, workflows and real scalar solves pass | [Log](final-installed.log) |
| Fresh built-wheel DCF notebook | 23 code cells, no errors; independent PV oracle remains 1000 | [Notebook](basic_dcf_final.ipynb), [HTML](basic_dcf_final.html), [inspection](notebook-inspection.json) |
| Current upgrade-guide examples | Passed outside checkout against built wheel | [Script](guide_example.py), [log](final-guide.log) |

The full regression excludes the three live-service tests in `tests/test_api.py`.
They remain unverified. New tests cover date constructors/wire formats, rejection
of datetimes, date/Period presence, explicit timing, payment outside coverage,
payment order, partial trim rejection, alignment conflicts, detached dataframe
round trips, and Source date/timestamp unions. Existing tests also verify full
Model JSON/YAML/store round trips with date-bearing Flows.

The initial full run recorded **897 passed, 1 failed**: an existing provenance
assertion expected a source date string. The assertion now checks a Python date
and unchanged ISO wire content. The resulting union test also protects timestamp
alternatives from date-only parsing. Earlier type-check and test-fixture failures
are retained in `typecheck.log` and `date-union.log`; the corrected runs passed.
The initial focused run had 102 passes, and the narrow date/provenance correction
had 16 passes. These overlap the full suite; do not add their counts.

## Environment, inputs and reproduction

[Before](before.json) captures the starting dirty files and input hashes.
[Final state](final-state.json) captures 316 inputs, interpreter/import paths and
dependency versions. It confirms that the unrelated `.gitignore` is unchanged
and the Git index is empty. The [schema environment](schema-environment.json)
confirms LinkML **1.11.1**, linkml-runtime **1.11.1**, jsonschema **4.26.0**.
Runtime is Python **3.10.19**, Polars **1.44.2**, pandas **2.3.2**, NumPy **2.2.6**,
SciPy **1.15.3**, Pint **0.24.4**, Pyomo **6.10.1**, and HiGHS **1.15.1**.

From the repository root, with the recorded temporary environments available:

```sh
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python \
  docs/research/full-migration/date-only/verify.py checks
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python \
  docs/research/full-migration/date-only/verify.py tests
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python \
  docs/research/full-migration/date-only/verify.py install
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python \
  docs/research/full-migration/date-only/verify.py notebook \
  --wheel-dir /private/tmp/rk-date-only-final
PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python \
  docs/research/full-migration/date-only/capture.py
```

Choose a fresh `--wheel-dir` when repeating the notebook phase and update the
capture script's `WHEEL_SITE` accordingly. The runner sets `MPLBACKEND=Agg`,
`MPLCONFIGDIR=/private/tmp/rk-mpl-cache`, and a writable temporary `PYSTOW_HOME`.
Type checks use `PYTHONPATH=/private/tmp/rk-record-typecheck`. Notebook/guide runs
use the unpacked wheel's `site` directory as `PYTHONPATH` and `/private/tmp` as cwd.
Exact subprocess arguments, working directories, exit codes and times are in
[commands.jsonl](commands.jsonl). [Wheel build](final-wheel.log) records its hash.
The source and wheel differ only in one clarified resampling docstring; the
capture script checks their Python syntax trees with docstrings removed.

The notebook was executed in a fresh local kernel with approved local socket
access. Outputs, tables, import path and independent result assertions were
inspected programmatically. Visual browser review remains unverified after the
earlier file-URL policy block. No alternate browser route was used. The executed
notebook is copied back to `walkthrough/basic_dcf.ipynb`; old book build outputs
remain historical.

No commit, push or release occurred. External Projects, host/service consumers,
temporal governing equations, scenario/policy contracts and final legacy
retirement retain their existing acceptance gates.
