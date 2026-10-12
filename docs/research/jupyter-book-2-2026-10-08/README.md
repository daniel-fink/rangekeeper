# Jupyter Book 2 local acceptance — 2026-10-08

The introduction and first DCF walkthrough now build as a Jupyter Book 2 static
site. The accepted site is served only on localhost. The public GitHub Pages site
and six deferred notebooks were not changed. The
[walkthrough guide](../../guides/walkthroughs.md#build-the-site) owns the current
execution and build procedure.

## Source and scope

Base: `acausal-modelling` at `60fd5b109408d6dc7830de5fc09aa661f7f6aa0b`, plus
the [recorded source changes](source-files.json). The seven notebook sources remain
the authoring files. `myst.yml` replaces the v1 configuration and lists only the
introduction and `basic_dcf.ipynb`. Later chapters enter that list after their own
code migration and acceptance.

The first notebook's 26 code cell sources are unchanged from the base. Its figure
now uses a standard Markdown image inside a MyST figure block. The original JPEG
is unchanged. Fresh execution outputs are saved in the source notebook. The
introduction uses a direct chapter link and native bibliography rendering.

The book builder stages only listed chapters and consumes supplied execution
outputs. It uses the v2 CLI and no longer imports Sphinx internals, filters Thebe
extensions or converts Plotly JSON into custom HTML. A small stylesheet keeps
native Polars labels on one line and allows horizontal scrolling within the page.

## Execution and build

- [Fresh execution](notebook-execution.json): **26 code cells**, **15 HTML tables**,
  no errors, with Python 3.12.12, Jupyter Book 2.1.7 and Polars 1.44.2.
- The kernel used the same installed Rangekeeper wheel as the preceding
  [native display acceptance](../native-polars-display-2026-10-08/README.md).
  Its source hashes and wheel SHA-256 are included in the execution capture.
- Results remain 11 forecast periods, 10 holding periods, 50 AUD first-year net
  cash flow, 1,218.9944199947572 AUD reversion and 999.9999999999997 AUD PV,
  displayed as **$1,000**. Annual transaction totals remain 300 and 200 AUD.
- [Strict static build](build.txt): **two pages**, using Node.js 24.15.0 and the
  downloaded standard book theme 1.4.1. The CLI is locked in `uv.lock`; the theme
  is downloaded by MyST and is not pinned by that Python lockfile. The build
  emitted a Node `url.parse()` deprecation warning, with no content errors.
- [Build input checks](guard-checks.json): missing notebooks, changed sources,
  missing execution counts and error outputs all fail before creating a stage.
- The downloadable notebook contains the same cell sources and outputs as the
  freshly executed source. All six deferred notebooks are byte-identical to HEAD.
- Dependency lock consistency, Python formatting and diff whitespace passed.
  Documentation checks passed for 65 pages and 39 current routes.

Commands used the isolated locked walkthrough environment, with the accepted
wheel reinstalled without changing its dependencies. The fresh kernel received
an explicit kernelspec pointing to that environment. The build command was:

```sh
python tools/docs/build_book.py <new-stage> <executed-notebooks>
```

The accepted staging directory and local URL are recorded in `source-files.json`.
The static server uses `python -m http.server 8769 --bind 127.0.0.1 --directory
<new-stage>/_build/html`. Kernel execution, dependency setup, the temporary MyST
build server and localhost serving used permitted host execution. An initial
sandboxed HTTP bind was denied; the permitted retry succeeded.

## Rendered inspection and limits

Browser review at 1280 × 720 covered the textbook figure and attribution,
resolved citations, the full proforma, final valuation, collapsed raw Movement
output, source download link and navigation between the introduction and chapter.
All 15 native tables are present. The proforma has all 11 year columns; horizontal
scrolling exposes the last years while preserving readable labels and numbers.
Both light and dark rendering were inspected during review.

A standard nbconvert HTML export also displayed the textbook image and plain-text
attribution. MyST directive markers and citation syntax remain visible in that
ordinary viewer. This establishes the fallback without claiming that GitHub's
remote notebook renderer was tested after these local changes.

Only this chapter was executed. Plotly, design artifact downloads and the other
six chapters need acceptance when they are migrated. Public deployment, legacy
URL redirects, launch links, PDF export and cross-platform checks remain open.
The tracked v1 site snapshot remains unchanged. No runtime package code changed;
the broad runtime suite was not repeated for this book-only migration.
