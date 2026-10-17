# Independent notebook Geometry viewer — 14 October 2026

> Edited extract, 17 October 2026: external application references were removed.
> Retained RK results keep their original scope; this is not an unchanged capture.

Local changes based on `497b1e5a2ab9c1c1049a577792d7e06f38203bba`.
RK now owns the viewer source, locked dependencies and build in `tools/geometry`.
The [build guide](../../../tools/geometry/README.md) describes the complete output.
No [external application omitted] repository or Python package is required to build or use this viewer.
The earlier source location was [external application omitted]; this record changes ownership,
not the viewer behaviour or the advanced Package browser scope.

## Verification

- Node 24.15.0: `npm ci --prefix tools/geometry` and
  `npm run build --prefix tools/geometry` passed from the RK root.
- Rebuilt `viewer.js`, HTML and third-party notices matched the existing packaged
  bytes. Only `manifest.json` changed, to use `rangekeeper.local-geometry/v1` and
  record the current build source hash. Manifest/file hashes were verified.
- Viewer JS SHA-256: `c452edbfa739aa407d20b2b6340d36c15cfac1c0114ca3b153a58fcb2f9a1c05`.
- `rangekeeper.visualisation.geometry.write` passed with
  `examples/walkthrough/data/mixed_use_property` and a temporary output directory.
  The output used the independent asset manifest; no [external application omitted] module was imported.
- `PYTHONPATH=src .venv/bin/python -m pytest -q src/tests/test_owner_boundaries.py
  -p no:cacheprovider`: 3 passed.
- `python3 tools/docs/check.py`: passed after recording this result; 71 pages
  and navigation to 45 current pages checked.

Existing notebook outputs and unrelated Python dependency edits were preserved.
No new notebook render or WebGL acceptance is claimed; rendered assets are unchanged.
