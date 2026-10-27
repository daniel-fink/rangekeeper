# Walkthrough geometry viewer

This folder holds the source and build of the standalone Speckle viewer for the
walkthrough lessons. The viewer reads the retained source records of the data
package and shows them locally. It needs no live Speckle account.

From the repository root, with Node 24.15.0:

```sh
npm ci --prefix examples/walkthrough/viewer
npm run build --prefix examples/walkthrough/viewer
```

The build writes `examples/walkthrough/viewer/dist/`. Copy all five output files
into `examples/walkthrough/helpers/assets/geometry/`: `viewer.js`,
`viewer.js.LEGAL.txt`, `viewer.html`, `SPECKLE-LICENSE` and `manifest.json`.
Keep the hashes and third-party notices, including `SPECKLE-LICENSE`. Check them
with `python examples/walkthrough/viewer/check_manifest.py`; the walkthrough CI
job runs the same check. The helpers use the copied assets and do not run npm.
The Rangekeeper wheel does not contain the viewer.

`helpers.geometry.write` checks the source and asset hashes and writes a local
page. `helpers.plot.show_geometry` serves the page and the data package under one
local HTTP root. Browser rendering needs WebGL and DecompressionStream.
