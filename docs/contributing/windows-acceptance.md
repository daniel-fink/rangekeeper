# Windows connector acceptance

**Status: open.** This procedure owns the remaining official Windows connector
publication/receive gate. Portable builds, macOS authoring, offline envelopes and
an earlier pinned Python receive are separate evidence. They do not close this
gate or authorize removal of the [held predecessor](legacy-retirement.md).

## Prerequisites and open host work

Use a native Windows checkout and an available Rhino 8 desktop session. Record
actual versions of Windows, Rhino, Grasshopper, the official connector, .NET,
Python and Rangekeeper. Use a .NET 8 SDK for the current projects. Verify connector
support and installation requirements against its official documentation during
the host run; an old support statement is not an accepted environment manifest.

The current [Grasshopper build](../guides/grasshopper.md#build-and-round-trip) has
two host-specific details to resolve before Windows acceptance:

- `Components.csproj` defaults to the macOS Rhino resource directory and its
  subordinate Grasshopper assembly paths. Supply verified Windows assembly
  locations through an explicit build configuration; a guessed replacement of
  the base directory is insufficient if its internal layout differs.
- `Tests/accept_rhino.py` loads the Debug assembly and writes `/private/tmp`
  artifacts. Use explicit Windows output paths and the intended assembly build
  before executing this driver on Windows. Record the actual load/install command
  and assembly hash once established.

Do not reuse the superseded `dotnet test` instructions. The current Tests project
is a console round-trip runner. The
[historical provisioning notes](../history/windows-provisioning.md) retain older
setup assumptions and do not define current acceptance.

Use a separate Windows checkout; do not share a working tree between operating
systems. Keep credentials and private payloads outside Git and acceptance output.
Authenticate through the host's normal connector workflow. Publication requires
a concrete destination and explicit authorization.

## Acceptance procedure

1. Record the environment and source revision. Build the active .NET 8 projects
   with verified Rhino reference paths. Do not load the excluded predecessor
   components. Close all Rhino processes before replacing an assembly; then load
   it in a fresh process and verify its version/hash.
2. Use [`connector-envelope.json`](../../src/grasshopper/Tests/Fixtures/connector-envelope.json)
   as the small public boundary fixture. It includes membership and property
   null/false/zero/ordered content. Create simple native Rhino geometry and record
   its actual Rhino UUID separately in the association. Preserve the Model
   revision and domain UUIDs.
3. Pass `rk_format`, `rk_model` and `rk_associations` through the official
   connector's supported ordinary metadata/data-object route. Record actual
   component names and property types. Do not infer this route from older Speckle
   v2 Goo. Use the [transport reference](../reference/design-transport.md) for
   envelope and identity rules.
4. Before publication, confirm validation, the intended content and an explicitly
   authorized destination. Publication must be an explicit action, not a side
   effect of recomputation. Record the project/model/version/content identifiers
   after publication. Authentication and destination choice remain external to RK.
5. Receive the pinned object through `rangekeeper.adapters.speckle.transport.receive`
   and decode it with `decode_model`. Compare all Model content and the separate
   geometry associations. Check IDs, revision, omission/null, zero/false, shared
   membership, units and property order; counts or visual nesting are insufficient.
6. Change the Model, recompute and publish it as a new revision within the
   authorized scope. Receive both pins. Check historical stability and updated
   geometry, application and content identities.
7. Repeat with [`exampleDesignCanonical.ghx`](../../examples/grasshopper/exampleDesignCanonical.ghx)
   and the two design [walkthroughs](../guides/walkthroughs.md). Compare the reviewed
   Model content, associations and financial regression results. Retain commands,
   hashes and redacted diagnostics.

If the connector changes after an upgrade, repeat the small boundary fixture
before changing the accepted environment. If published content differs, compare
the pre-publication Model first to separate authoring errors from transport errors.
Missing components, load failures or unexpected semantic changes keep the gate open.

## Close and record the gate

Keep a dated result with the source revision; all host, SDK and package versions;
assembly hash; build and round-trip results; component loading/recomputation result;
fixture and Model hashes; safe publication/receive pins; complete semantic
comparisons; notebook results; and any remaining differences. Exclude tokens,
private URLs, account databases and unsanitized payloads.

Close this gate only when the actual host and authorized publication/receive
checks pass. Link the result from this page and
[legacy retirement](legacy-retirement.md) before removing the held implementation.
Preserve any failed attempts as dated evidence. A completed local code change
cannot substitute for this external acceptance.
