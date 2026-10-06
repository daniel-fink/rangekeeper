# Turn 3 — Remaining consumers, workbench and design integrations

Implemented against RK `b9de7fc` on `acausal-modelling`, Projects `5725cc0`, and
layout reference `4e5aec4`. This is an uncommitted candidate. No push, release or
external publication is included. [Acceptance evidence](research/full-migration/turn3/BASELINE.md)
records the actual environments, commands, results and remaining gates.

The canonical Model remains the domain authority. LinkML owns the fields for both
Python and C#. Source `WorkflowSpec`, mathematical `Specification`, workbench
`Attempt`, layout `Result` and mathematical `Run` remain distinct concepts.

## Implemented boundaries

```text
rangekeeper/
  workflow/
    runtime.py          run(): source execution, no implicit export
    progress.py         Progress, Observer, Reporter
    workbench.py        Inspection, Attempt, inspect(), build(), notebook_progress()
    layout_review.py    LayoutAttempt, build()
    _artifacts.py       atomic writes shared by both local bundle builders
    _review.py          canonical Claims, decisions and findings for presentation
  graph/projection.py   PropertyColumn; detached rich property content
  adapters/
    speckle/            transport, detached objects, canonical envelope mapping
    cytoscape/layout/   detached geometry, profile, seed, checks, saved viewer
    plotting.py         detached component and hierarchy figures
  migration/
    graph.py            explicit old Graph wire conversion
    speckle.py          explicit old design payload conversion
    layout.py           explicit profile v1/v2 -> v3 upgrade
  examples/design.py    author(), formulate(), specify(), values(), fixture()
grasshopper/
  Model/Generated/      72 generated wire record classes and shared schemas
  Model/Serialization/  presence, detached JSON, deterministic encoding
  Model/Authoring/      identity and composition
  Model/Validation/     structural and local reference checks
  Components/Canonical/ connector-independent Rhino 8 components
  Tests/                pure and cross-language checks; canonical example GHX
```

Domain validation imports no service SDK, Rhino, layout solver or dataframe code.
Layout solvers are optional presentation tools. Pyomo/HiGHS remains the sole
mathematical execution backend. The C# domain project has no Rhino or Speckle
reference; only the component project references the installed Rhino libraries.

## Public operation contracts

| Operation | Result and ownership | Errors, mutation and side effects |
|---|---|---|
| `workflow.run(spec, *, input_root, on_progress=None)` | `Outcome[WorkflowResult]`, with a canonical Model | Reads declared sources. No export. Expected unavailable input returns diagnostics. Observer exceptions are separate reporting diagnostics and do not change semantic fingerprints or Model content. |
| `workbench.inspect(spec_directory, *, input_root, output_root)` | `Inspection`, including current source/configuration state and previous successful bundle | Reads inputs and bundle metadata; creates no files. Missing/changed inputs and damaged previous output become diagnostics. |
| `workbench.build(spec_directory, *, input_root, output_root, on_progress=None)` | New `Attempt`; `result` exists only for this successful attempt | Writes a new checked local bundle. Failed attempts have diagnostics and no candidate. Prior success remains explicitly historical. It never substitutes for a failed build. |
| `layout.profile.prepare(model, profile)` | Detached `Problem` and signal report | Pure preparation. Invalid versions, selectors, units or geometry declarations fail. Missing evidence cannot establish a signal. No Model writes or solve. |
| `layout_review.build(attempt, *, profile, output_root)` | `LayoutAttempt` | Reads this successful attempt and profile, writes checked geometry/review/viewer bundle. Invalid layout or damaged/wrong Model bundle cannot advance the successful-layout pointer. |
| `speckle.transport.receive(client, *, project_id, version_id=None, object_id=None)` | Immutable detached `Received(payload, source)` | Explicit authenticated network read. Exactly one pin is required. `TransportError` for unavailable content. No latest fallback, conversion, store or publication. |
| `speckle.decode_model(payload)` | Immutable `Model` | Pure, strict canonical envelope decode. `MappingError` identifies path and identity. Does not infer domain membership from collection nesting. |
| `speckle.encode_model(model, *, associations=())` | Detached envelope dictionary | Checks revision and domain associations. No SDK construction, storage or publication. |
| `migration.speckle.convert_speckle(payload, *, mapping, revision_id=None)` | `ConversionResult(model, issues, associations, source_sha256)` | Pure explicit legacy conversion. Failure returns no partial Model. Conflicts, unsupported fields and unresolved references are reported. Inputs are unchanged. |
| `migration.layout.upgrade_profile(profile, *, model)` | Detached profile v3 dictionary | Only discovered v1/v2 formats. Missing/ambiguous classifications or Measures fail. No automatic codec upgrade. |
| `PropertyColumn(name, key)` with `graph.projection.to_table` | Detached table column | Selects an owner-local property Value. Does not expose mutable Model content or change quantity-column semantics. |
| `design.author` / `formulate` / `specify` | New authored Model / Model with finite declarations / Specification | Constructors do not execute. Missing geometry quantities and ambiguous use interpretation fail. `Executor.execute` and persistence remain explicit. |

Workbench and layout return records own derived presentation state, not persistent
field schemas. Their detached dictionaries may be edited by callers without
changing the Model. Model records themselves remain deeply immutable.

## Workbench and layout

Ported features include source inspection, progress, decisions and clarifications,
independent attempts, integrity-checked bundles, last-success navigation, and
`model.diff` comparison. Bundles contain `model.json`; their local `run.json` is
workbench metadata, not a mathematical Run. Shared atomic writes are in
`workflow._artifacts`, with no layout import of a workbench private helper.

Profile `rk-layout-profile-v3` resolves canonical Assemblies from
`System.assemblies`, classification UUIDs, property Value keys, and quantity keys
with explicit comparison units. The `stacked-compact-v1` rendering policy remains.
Code/name lookup occurs only during explicit profile authoring or upgrade and must
be unambiguous. Shared membership remains shared; unsupported constructive layouts
return a capability diagnostic while the ordinary graph viewer remains available.

Grid/stacked seeds, preferences, pins, arrangements, packed spacing, ordering and
similarity signals, independent geometry checks, saved fingerprints, dragging,
overlap warnings and restore behavior are ported with tests. Z3 is locally tested.
MiniZinc remains optional and unverified on this host because it is not installed.
Neither solver can publish a mathematical Run.

## Real source consumers

Mandarin and both East Whisman scenarios now use outer workflow documents v2.
Their extraction policies retain their own versions. Former Features become
property Values; every measurement has an owner-local key. Six Mandarin, two
December, and 34 November unresolved measurements are now explicit, alongside
preserved descriptive properties and findings. Zero remains distinct from missing.

Business UUIDs, source checksums, reviewed decisions and calculation scopes remain.
East Whisman keeps square-foot units and separate source scenarios. No tower
crosswalk, basement allocation, individual apartments or deletion from absence is
inferred. Projects remains an environment-only repository with YAML interpretation
and thin notebooks. The reference graph enters only a separate comparator.

Strict comparisons check canonical content, mapped Value identities, quantities,
units, membership, relationship endpoints, source cells, decision records and check
outcomes. Named representation changes are recorded, not broad ignored categories.
Mandarin also retains its separate older SOM-reference comparison.

## Design transport and financial behavior

The versioned envelope is `rk.speckle-model/v1`. Its property names are defined once
in `adapters/speckle/contract.json`: `rk_format`, `rk_model` (canonical JSON string),
and `rk_associations`. Associations require `model_revision` and `domain_id`;
`rhino_id`, `application_id` and `content_id` remain distinct optional identifiers.
The same contract generates the C# constants. Geometry stays outside the Model.

Legacy conversion preserves old domain UUIDs, merges identical repeats, permits an
Entity/Assembly duplicate only when shared content agrees, retains supported rich
properties and sourced Claims, and rejects conflicts rather than keeping the first.
The pinned object read succeeds with SpecklePy 3.0.7. The server currently returns
no object reference for the historical version; this is an explicit service-history
limitation. The adapter rejects it and never silently selects another version.
The independently recorded object pin is used for the live read acceptance.

Both design notebooks declare `RK_DESIGN_MODE`: `fixture`, `live`, or `canonical`.
They do not switch modes on failure. Fixture mode is the routine fresh-wheel check.
Live mode uses explicit pins and configured credentials; neither notebook publishes.
The financial notebook declares its execution budget: 30 seconds for the small
fixture and 300 seconds for live/canonical input, overridable through
`RK_DESIGN_TIME_LIMIT`. Authoring is a separate operation outside this budget.

Financial declarations retain efficiency, PGI, vacancy, EGI, facade area, signed
floor/facade operating expenses, floor/utility capital expenses, NOI, NACF,
reversion and discounted value. The legacy five-year capital payments occur at
2005-12-31 and 2010-12-31, with growth exponents 0 and 1 over those intervals.
Reversion uses 2011 NACF divided by capitalization rate, received at the 2010 sale;
it is not silently changed to NOI capitalization. Currency is explicit AUD.
Contributor IDs are deduplicated; parent totals are never added to constituents.
Expense-area figures use labelled magnitudes while the Model keeps negative flows.

## C# and Rhino 8

`tools/schema/generate_csharp.py` consumes the same resolved slot metadata and
structural schema as Python. Generated fields use UUIDs, typed records, `DateOnly`,
ordered collections and explicit `Optional<T>` presence. Omitted, null, false and
zero survive round trips, as do rich content and ordered mathematics. Exports and
nested record access are detached. Duplicate JSON keys fail before interpretation.

Handwritten C# owns composition, cloning, diagnostics and serialization behavior.
The generic Entity component uses its saved instance UUID when no ID is supplied.
An explicit ID reuses identity; a new component instance creates a new identity.
The Model component advances revision on changed content and retains predecessor
metadata through unchanged recomputation and save/reopen. Explicit revision input
puts revision selection under the author's control.

Components cover Definitions, Entity, Value, Relationship, Assembly, Provenance,
Value attachment, Model, validation and canonical export. The first authoring
surface accepts schema-compatible JSON plus explicit identity inputs. It is not a
second C# domain schema or a complete visual editor for every record field.

The new `Tests/exampleDesignCanonical.ghx` reads the unchanged Rhino source through
an example-specific component. It computes floor slices, volumes and reviewed
service relationships using native Rhino geometry. The five-component definition
needs no EleFront, old RK components or Speckle v2 types. Original
`exampleDesignConfig.ghx` remains historical evidence. Host checks cover recompute,
save/reopen, identity, revision lineage, 36 Entities, 14 Assemblies, 63 relationships
and 45 explicit Rhino associations. A separate semantic comparison verifies all
quantities, units and membership, with an explicit historical/new UUID map.

C# performs shared structural and local reference/identity authoring checks.
Python remains the full semantic acceptance boundary, including units and all
mathematical/provenance rules. A C# validation success alone is not publication
acceptance. The exported Model passes Python validation and canonical decoding.

## Completion and retirement

Use the [evidence report](research/full-migration/turn3/BASELINE.md) for the current
completion statement. Local implementation and acceptance are distinct from all
supported integrations being accepted. The Windows official connector publication
and receive gate remains open; no destination was selected or published to.
[Windows acceptance procedure](../grasshopper/WINDOWS_DEVELOPMENT.md) defines that gate.

Hypar was retired from supported consumers in this turn. Its local residue was
later [removed at the user's request](research/full-migration/hypar-removal/README.md);
the historical research remains. The future
Browser/outliner importer remains on hold. Turn 4 removes old code only according
to the [exact retirement register](research/full-migration/turn3/RETIREMENT.md),
including the Windows-dependent hold. This turn does not remove legacy modules.

Static typing includes the ported workbench, layout and Speckle modules, for
168 checked source files. The full-size design check also justified a local
Run-validation index: repeated
evidence references reuse the identity set for their exact revision within that
call. Validation checks and cross-revision isolation remain unchanged.
