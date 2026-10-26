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

Do not edit the source capture or the derived files by hand. A change to a file
in this folder needs a matching change to its manifest entry. The test
`src/tests/test_example_data.py` checks the manifest and the origins.
