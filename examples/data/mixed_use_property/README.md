# Mixed-use property data

This folder is the data package for walkthrough lessons 02–07. The
[project brief](../../../docs/guides/mixed-use-project.md) describes the property
and the files.

## Licence and attribution

The property data is licensed under
[Creative Commons Attribution 4.0 International](LICENSE) (CC BY 4.0). The
mixed-use property design is the Rangekeeper author's own work. When you share
or adapt this data, give this attribution:

> Mixed-use property data by Daniel Fink, from Rangekeeper
> (<https://github.com/daniel-fink/rangekeeper>), licensed under CC BY 4.0.

The Rangekeeper code is licensed separately, under MPL-2.0.

## Provenance

- [`manifest.json`](manifest.json) gives the source pins and capture details. For
  each file, it gives the size, the SHA-256 hash, the origin, a description and
  the licence.
- [`origins.json`](origins.json) gives the origin of each teaching assumption in
  `assumptions.json` and `development.json`: a legacy notebook cell, a book
  method or the author's choice.
- On 31 October 2026 the rents of `assumptions.json` became 10 % higher and its
  floor and facade OPEX rates 10 % lower than the legacy rates, so that the dated
  plan of walkthrough lesson 03 can pay for its costs and its loan
  ([#205](https://github.com/daniel-fink/rangekeeper/issues/205)). `origins.json`
  records the author's change against the legacy cell; `totals_2032.json` is
  derived again from the new rates.

- `totals_2032.json` gives the property's totals in the stabilised year 2032
  for walkthrough lesson 02, each with its origin.
  [`../derive_totals.py`](../derive_totals.py) derives it from `inventory.csv`,
  `assumptions.json` and `development.json`, and documents each total. Run
  `python examples/data/derive_totals.py` from the repository root to recreate
  it, then update its manifest entry; `--check` compares the file with a new
  derivation.

- `base_plan.json` gives the dated plan of walkthrough lesson 03, at 2027 prices,
  each value with its origin: dates, budgets, incomes, operating costs, renewals,
  funding, the areas by package and use, and the construction rates. Its loan limit
  is the plan's bridge limit, and its budgets leave out the construction finance
  allowance. [`../derive_base_plan.py`](../derive_base_plan.py) derives it from
  the same three files, and documents each value. Run
  `python examples/data/derive_base_plan.py` from the repository root to recreate
  it, then update its manifest entry; `--check` compares the file with a new
  derivation.

- `03_base_plan.model.json` and `03_base_case.specification.json` give the Model
  of walkthrough lesson 03, with the commitments of its optional cell 21, and its
  `funded` Specification on that Model. Lesson 04 loads them.
  [`../derive_lesson_documents.py`](../derive_lesson_documents.py) derives them from
  the cells of lesson 03 and `base_plan.json`. Run
  `python examples/data/derive_lesson_documents.py` from the repository root to
  recreate them, then update their manifest entries. Each derivation gives new
  random IDs, so `--check` reads each ID as the order of its first use, and the
  script keeps the files when only their IDs differ.

- `04_base_plan_on_paths.model.json`, `04_base_case.specification.json`,
  `04_rent_index.paths.json` and `05_histories.paths.json` give lesson 04's Model with
  the rent index, its `base` Specification on that Model, its 500 market paths with
  seed 1, and the three readable histories of lesson 05. Lesson 05 loads them. The same
  script derives them. The ID of Paths is a digest of their content, which includes the
  Python and numpy versions of the capture, so the same seed on another version gives
  another ID. The stored files keep their IDs. `--check` leaves the versions out, and
  rounds the amounts to nine decimal places.

Do not edit the source capture or the derived files by hand. A change to a file
in this folder needs a matching change to its manifest entry. The test
`tests/walkthrough/test_example_data.py` checks the manifest and the origins.
