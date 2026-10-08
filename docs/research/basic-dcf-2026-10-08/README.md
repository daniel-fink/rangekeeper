# First walkthrough acceptance — 2026-10-08

The revised [basic DCF notebook](../../../examples/walkthrough/basic_dcf.ipynb)
retains the legacy teaching sequence and reproduces the original $1,000 present
value. It has 59 cells, including 26 code cells and 15 HTML table outputs. Every
code cell executed in order in a fresh kernel, using an installed candidate wheel.

## Sources and environment

- Legacy baseline: `main:walkthrough/basic_dcf.ipynb` at
  `6732e83d277c8de81f3dec2906e06d0e75d3b6fa`. The `develop` version had the same cell
  sources. The title, book citation and Table 1.1 image remain in the walkthrough.
- API commit: `9db2c82a330316e8b49839c2c9a0c5f23b01e7f0`. The
  [API acceptance](api.md) records the full suite, schema, typing and installed
  wheel checks. Those source hashes remained unchanged during notebook authoring.
- Candidate: `rangekeeper-0.8.71-py3-none-any.whl`, SHA-256
  `debf952a8d81f68bfcd6ff69146911326b0ae39abce2a5e7603a6af5027632c9`.
- Local environment: macOS, Python 3.12.12, Polars 1.44.2, NumPy 2.3.5,
  nbclient 0.10.2, nbformat 5.10.4 and Jupyter Book 1.0.4.post1. Dependencies came
  from the walkthrough lockfile; the matching example package was installed.
- [Execution capture](notebook-execution.json) records the interpreter, installed
  package path, versions, elapsed time, values and final notebook hash. The kernel
  imported Rangekeeper from `site-packages`, outside the source checkout.

## Teaching fidelity

| Legacy lesson | Current expression |
| --- | --- |
| Introduce a Flow through dated transactions, then inspect it | `Flow.from_events(...)`, bare Flow rich display, Movement and date inspection, units and `display(name=...)` |
| Define the period being modelled | Explicit ten-year holding Span and eleven-year forecast Span; named `frequency` arguments; first and last period inspection |
| Explain extrapolation and distribution | `projection.extrapolate()` and `projection.distribute()` retain these concepts; `Distribution.uniform()` supplies the distribution |
| Build growing gross income, then vacancy | Extrapolate 100 at 2%; scale by 5% and `negate()` to represent the deduction |
| Group lines and combine them | A labelled Stream displays constituent Flows; `sum()` produces the combined Flow |
| Coordinate frequencies | A short example resamples the initial dated transactions into annual amounts of 300 and 200 |
| Complete operating and capital cash flows | Scale gross income by 35% and 10%, negate deductions, and combine successive subtotals |
| Capitalize the next year's cash flow and receive the sale proceeds | Capitalize year 11 cash flow after capital expenditure at 5%; distribute the total into the final holding period |
| Trim ownership cash flows and show a proforma | Resample with explicit zero handling for empty sale periods, trim by holding Span, and display the labelled report with `transpose=True` |
| Discount and collapse to property value | Discount ten annual receipts at 7%, starting at period one, then `collapse(on=valuation_date)` |

The prose changes where the contracts differ: records are immutable, Flow content
has no display name, period coverage is distinct from a payment date, and absence
is distinct from an unknown amount. The report distinguishes components from
subtotals to prevent double counting. Holding and forecast Spans replace the
less clear selection of the penultimate forecast period.

The notebook uses three short checks: ten receipt periods, sale proceeds in the
last holding period, and the original present value. It ends with a short bridge
to Model equations and Specification roles. It does not claim that direct Stream
calculations create acausal equations. Model authoring helpers, manual dataframe
joins and pandas are unnecessary for this first lesson.

## Numerical and rendered results

| Check | Observed result |
| --- | --- |
| Forecast / holding periods | 11 / 10 |
| First-year net cash flow | 50.00 AUD |
| Following-year net cash flow | 60.94972099973786 AUD |
| Sale proceeds in 2010 | 1,218.9944199947572 AUD |
| Final receipt, including sale | 1,278.7490484258728 AUD |
| Present value | 999.9999999999997 AUD, displayed as 1,000.00 |
| Event resampling | 300.00 AUD in 2019; 200.00 AUD in 2020 |

The source notebook retains all fresh outputs, with execution counts 1–26 and no
errors. A temporary audit cell verified the wheel import and intermediate values;
it is excluded from the teaching notebook. The raw Movement output is collapsed
by default. Obsolete execution timestamps were removed; current kernel timestamps
remain. Notebook format 4.5 adds stable cell IDs.

A scoped Jupyter Book preview built successfully with warnings treated as errors.
It used the current configuration, introduction, bibliography and resources, plus
only the freshly executed first chapter. Execution was disabled for the build;
the unused Thebe extension was disabled as in the maintained book procedure.
The [build log](book-preview.txt) records the result.

The preview was inspected in the local browser at a 1280 × 720 viewport. Checks
covered the reference figure and citation, direct Flow table, collapsed record
inspection, complete proforma, final valuation and book navigation. The proforma
cell uses the book's `full-width` tag so all eleven forecast columns and the line
labels fit at this size. Narrower output containers retain horizontal scrolling.
No custom display code is required in the lesson.

## Reproduction and scope

Follow the [walkthrough acceptance procedure](../../guides/walkthroughs.md) using
the candidate wheel, its matching example package and a kernel registered for that
environment. Execute `basic_dcf.ipynb` alone in a fresh directory. For example,
from that directory, with the environment active:

```sh
python -m nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=120 --ExecutePreprocessor.kernel_name=rk-basic-dcf basic_dcf.ipynb
```

Register `rk-basic-dcf` for the candidate environment before this command. For a
scoped book preview, copy the current book configuration and resources into a
fresh stage, set the temporary table of contents to `intro` and `basic_dcf` only,
and set `execute_notebooks: off`. Build with `jupyter-book build STAGE --all
--warningiserror`, using the same Thebe exclusion as the maintained book builder.

This result covers only the first walkthrough. The other six notebook files and
the tracked `_build` snapshot are unchanged. Full-book migration, full-book
execution and site publication remain separate work. This is local acceptance;
it does not establish remote CI or other-platform results.
