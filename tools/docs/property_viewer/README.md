# Local Speckle viewer for notebook 02

This small host uses the official `@speckle/viewer` 2.31.14 package. It reads the
complete pinned `transport.json.gz` next to the chapter, checks its manifest hash,
and supplies the original root followed by its detached records to
`ObjectLoader2Factory.createFromObjects`. Speckle performs geometry conversion,
rendering, camera navigation, selection and filtering. No access token, server
API or model upload is involved.

The SDK's `SpeckleOfflineLoader` is a stub in this pinned release. Our small
`SpeckleLoader` subclass supplies its in-memory loader. It does not rewrite source
objects or implement a replacement mesh renderer. Use-colour overlays are display
choices. Restrict them to visible objects because this SDK applies user colours
after visibility filters. The web page adds a small toolbar and property panel;
it does not reproduce the hosted Speckle application's full interface.

Build from the repository root with Node.js 24:

```sh
npm ci --prefix tools/docs/property_viewer --ignore-scripts
npm run --prefix tools/docs/property_viewer build
```

The generated bundle, HTML and legal notices live in
`examples/walkthrough/resources/mixed-use/`. Serve the walkthrough directory or the
built book over localhost; opening the HTML with `file://` cannot fetch its archive.
The bundle is local, including Speckle's embedded lighting environment. Geometry
requires WebGL and a browser with `DecompressionStream`. Source calculations do not.

The `context`, `property`, `floors` and `utilities` URL views replace the historical
saved views for this chapter. Source geometry and original content IDs are kept.
Object selection shows source properties and the Rangekeeper identity. The other
notebook widgets have independent selections.

The hosted legacy model reported **Model expired** under the workspace's version
history limit on 12 October 2026. Re-uploading was not needed for local reading.
The captured data is the source, not a request to retrieve an inaccessible version
through the hosted viewer.

References: [Speckle viewer documentation](https://docs.speckle.systems/developers/viewer/introduction)
and [Speckle source](https://github.com/specklesystems/speckle-server/tree/main/packages/viewer).
The viewer and object loader use Apache-2.0. Preserve the generated third-party
notices when redistributing the bundle. Recheck SDK compatibility before changing
the pinned versions; Speckle's current documentation flags a new 2026.9 data format.
