# Present and explore the schema

Open [the schema presentation](../schema-presentation.html) in a browser. The
HTML file contains its styles, scripts, schema data, and original LinkML text.
It works from a local file without a server or network connection. Share the
HTML file on its own when a recipient needs the same schema snapshot.

## Present

Use the eight view buttons, the bottom navigation, or the left and right arrow
keys when focus is outside a control. Use **Full screen** for a presentation.
Select a record to read its definition and notes. Select a connection to inspect
the field that defines it. The **Fields** tab includes inherited fields and local
slot overrides. **Source** shows the original class, enum, or type declaration;
for a field, it also shows its resolved definition.

Use **Browse schema**, or `/` outside a control, to find any local record, enum,
or custom type. The reference includes definitions outside the focused diagrams.
The URL fragment retains the view and selection. On narrow screens, a record
list replaces the diagram and the detail panel follows it.

The worked example uses stated illustrative amounts. Its two choices show
different assignment and unknown roles. It does not invoke an executor or claim
numerical acceptance. The full schema includes contracts beyond the supported
[execution slice](../reference/execution.md).

## Read the notation

- A stack represents a collection. It does not imply order or an exact count.
- A dashed record border marks an optional field in its base declaration.
  Conditional requirements are marked and retained in the detail panel.
- A filled diamond identifies an embedded record within the snapshot.
- An arrow identifies a UUID reference. Document pins name the intended document
  kind on the diagram; their declared field range is `Metadata`.
- A hollow triangle identifies inheritance.

Field presence is separate from explicit item-count constraints. The details
show both. A missing value, an empty collection, unresolved content, and a
numerical zero retain the distinctions stated in the source schema.

## Rebuild

From the repository root, activate an environment installed from
[`tools/schema/requirements.txt`](../../tools/schema/requirements.txt), then run:

```sh
python tools/schema/presentation.py
python tools/schema/presentation.py --check
```

The generator resolves the same LinkML imports as the record generator through
`SchemaView`. It embeds all local class, enum, and type definitions, complete
descriptions and notes, conditional rules, original YAML, and source locations.
The footer records a digest of the source YAML and import bundle. Module versions
in the Source panel identify the defining module; they are not document wire
versions. The header identifies the Model schema version.

The presentation source is in
[`tools/schema/presentation/`](../../tools/schema/presentation/). `views.json`
owns the selected views, positions, and short captions. LinkML owns the field
semantics and full explanations. `index.html`, `style.css`, and `app.js` own the
local browser interface. Edit these sources and rebuild; do not edit the
generated HTML directly. `--output PATH` writes a copy to another location.

This local presentation does not change or publish the walkthrough site.
