# Walkthrough Geometry viewer

Rangekeeper owns this standalone Speckle viewer for walkthrough notebooks.
It has no build or runtime dependency on any Whirlwind repository or package.
It reads retained source records; it is not the Whirlwind Package browser.

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
