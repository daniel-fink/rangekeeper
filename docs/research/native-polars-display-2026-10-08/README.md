# Native Polars display acceptance — 2026-10-08

Flow and Stream display now use Polars' native HTML and text renderers. The public
display methods, labels, units, orientation, precision and missing-value meanings
are retained. The refreshed first walkthrough reproduces the $1,000 present value.
The [table reference](../../reference/tables.md#flow-and-stream-display) owns the
current contract; [ADR-005](../../decisions/005-flux-and-stream-implementation.md)
records the decision.

## Source and implementation

Base: `acausal-modelling` at `e4e961f55cb0f1fb4e891729624c452506b0ac44`, plus the
changes identified by [source hashes](source-files.json). This follows the
[first walkthrough acceptance](../basic-dcf-2026-10-08/README.md), whose captured
evidence remains unchanged.

`StreamTable` prepares a detached presentation DataFrame and delegates rendering
to Polars. Its object columns hold formatted strings. Native Polars HTML adds
quotation marks to String columns; object columns let it render these prepared
values directly while retaining native HTML escaping. This presentation frame is
not used by calculations or numeric exports.

The change removes handwritten table/footer markup, manual HTML escaping and
plain-text padding. Scoped Polars settings show the full selection, preserve full
labels and hide types and shape. The caller's configuration is restored after
success or failure. Display remains lazy and needs no additional dependency.
An empty Flow displays its headers; a Stream with no Flows retains its existing
alignment error. The marker legend now appears in the notebook and reference.

## Verification

- [Full Python suite](pytest.txt): **1,489 passed, 24 skipped** in 182.93 seconds,
  using Python 3.10.19 on macOS. The predecessor live-service module
  `src/tests/legacy/test_api.py` was excluded as required by the local procedure.
- [Typing](typing.txt): all 215 valid source files and seven groups of deliberate
  invalid fixtures passed their expected checks.
- [Installed-wheel checks](installed-wheel.txt): minimal imports, records, codecs,
  stores, membership/reduction, native Flow/Stream display and Polars/CSV checks
  passed. The isolated table environment had no pandas. This invocation selected
  the runtime and table slices; it did not select the optional solver slice.
- Display tests cover both orientations, HTML escaping, full labels, 80 periods,
  negative amounts, decimal precision, absent/unknown/zero values, empty content,
  unchanged numeric exports and records, and configuration restoration after a
  native rendering error. The initial empty-Stream test assumption was corrected
  to preserve the existing alignment contract.
- Documentation links and navigation passed: 65 pages and 39 current routes.
  Formatting and whitespace checks passed for the changed files.

The candidate wheel was built in a separate staging directory:
`rangekeeper-0.8.71-py3-none-any.whl`, SHA-256
`35a086f6d72f469cae33ba009343d8bc62c1c711546e8bef79c1bb47d3aaa5fd`.
The same wheel was installed for the fresh notebook kernel. No canonical schema
fields or generated files changed.

Commands from the repository root:

```sh
MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/rangekeeper-acausal-mpl .venv/bin/python -m pytest -q --ignore=src/tests/legacy/test_api.py
PYSTOW_HOME=/private/tmp/rk-005-pystow /private/tmp/rk-005-schema/bin/python tools/schema/typecheck.py
.venv/bin/python tools/docs/check.py
.venv/bin/python -m black --check src/rangekeeper/adapters/presentation.py src/tests/test_flux_stream.py tools/schema/verify_install.py
```

The wheel checker used `tools/schema/verify_install.py --wheel` with the candidate
above, `--runtime-python` and `--tables-python` both pointing at the root
`.venv/bin/python`. The notebook used the existing isolated Python 3.12.12
walkthrough environment with the new wheel installed and a fresh kernel. A uv
macOS configuration lookup failed in the sandbox; its offline installation
succeeded with the permitted host execution.

## Notebook and rendered review

The [execution capture](notebook-execution.json) records the interpreter, package
versions, installed import path, source hashes, wheel hash and final notebook hash.
All 26 code cells executed in order with no errors. The notebook retains 59 cells
and 15 HTML table outputs. No code cell source changed in this follow-up; only the
marker guidance and fresh outputs changed.

Observed values: 11 forecast periods, 10 holding periods, 50.00 AUD first-year net
cash flow, 1,218.9944199947572 AUD sale proceeds, and 999.9999999999997 AUD present
value, displayed as 1,000.00. The dated transaction example still resamples to
300.00 and 200.00 AUD.

The [scoped book build](book-preview.txt) used the current introduction,
bibliography and resources, plus this freshly executed chapter. Execution was
disabled during the build and warnings were treated as errors. Native Polars
tables were inspected in a local browser at 1280 × 720: direct Flow display,
the full eleven-year proforma and final valuation were readable, without literal
quotes around values. The existing full-width proforma tag remains effective.
Sidebar navigation between the introduction and chapter also passed.

Only the first notebook was executed and refreshed. The other six notebooks and
tracked site snapshot remain unchanged. Full-book acceptance and site publication
remain separate work. These checks do not establish remote CI, strict optional
layout-engine acceptance, other platforms or live services.
