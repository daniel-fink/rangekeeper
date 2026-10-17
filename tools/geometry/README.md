# Walkthrough Geometry viewer

Rangekeeper owns this standalone Speckle viewer for walkthrough notebooks.
Its source and build are contained in this repository. It reads retained source
records and provides local notebook display.

From the Rangekeeper repository root, with Node 24.15.0:

```sh
npm ci --prefix tools/geometry
npm run build --prefix tools/geometry
```

The build writes `tools/geometry/dist/`. To update the Python distribution, copy
all five output files into `src/rangekeeper/visualisation/assets/geometry/`:
`viewer.js`, `viewer.js.LEGAL.txt`, `viewer.html`, `SPECKLE-LICENSE`, and
`manifest.json`. Preserve the hashes and third-party notices. Python installation
uses these packaged assets and does not run npm.

`rangekeeper.visualisation.geometry.write` checks source and asset hashes and
prepares a local page. Serve the page and retained source under one local HTTP
root, such as Jupyter. No live Speckle account is required. Browser rendering
requires WebGL and DecompressionStream.
