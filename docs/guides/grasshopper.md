# Author Models in Grasshopper

The .NET solution lives at [`src/grasshopper/`](../../src/grasshopper). The active
projects target `net8.0` and Rhino 8. The Model project has no Rhino or Speckle
reference. LinkML generation owns persistent fields; handwritten code owns
presence-preserving serialization, authoring, composition and diagnostics. The
Components project uses the installed RhinoCommon, Grasshopper and GH_IO
assemblies. Dependencies are pinned in project files and lockfiles.

This independent source project is outside the Python package. Python adapters
remain under `src/rangekeeper/adapters/`. See the
[architecture](../concepts/architecture.md) for the repository map and
[design transport](../reference/design-transport.md) for the shared envelope.

## Build and round-trip

From the repository root, use the pinned schema environment to check generated
files. Build with a .NET 8 SDK:

```sh
python tools/schema/generate_csharp.py --check
dotnet restore src/grasshopper/Tests/Tests.csproj --locked-mode
dotnet build src/grasshopper/Tests/Tests.csproj --no-restore
dotnet restore src/grasshopper/Components/Components.csproj --locked-mode
dotnet build src/grasshopper/Components/Components.csproj --no-restore
```

The Tests project is a console fixture runner, not a `dotnet test` test project.
It and the Model project build without Rhino. The Components build needs the
Rhino assemblies. Its default `RhinoResources` location and subordinate paths
match the macOS Rhino 8 installation. Windows assembly-path configuration remains
part of the [Windows acceptance work](../contributing/windows-acceptance.md#prerequisites-and-open-host-work).
Do not interpret a portable Model/Tests build as a component-load pass.

Install the matching Python library and `./examples` with their calculation and
execution dependencies. From the repository root:

```sh
python tools/schema/cross_language.py prepare /tmp/rk-cross-language-001
dotnet src/grasshopper/Tests/bin/Debug/net8.0/Tests.dll /tmp/rk-cross-language-001/python.json /tmp/rk-cross-language-001/csharp.json
python tools/schema/cross_language.py check /tmp/rk-cross-language-001
```

This checks rich content, UUID references, dates, omission/null, zero/false,
separate collections, immutable access and ordered mathematics through both
language boundaries. Use a fresh output directory and record the source and
runtime versions.

## Check the Rhino example

The macOS Debug build produces
`src/grasshopper/Components/bin/Debug/net8.0/Rangekeeper.Components.gha` and its
adjacent dependencies. Load the current build into a fresh Rhino 8 process.
After replacing an assembly, fully close Rhino and restart it to avoid checking
an already loaded binary.

Run [`Tests/accept_rhino.py`](../../src/grasshopper/Tests/accept_rhino.py) with Rhino's
`RunPythonScript`. It builds, saves, reopens and recomputes
[`exampleDesignCanonical.ghx`](../../examples/grasshopper/exampleDesignCanonical.ghx).
It reads the original [`exampleDesign.3dm`](../../examples/grasshopper/exampleDesign.3dm)
without changing it. The current driver loads the Debug assembly and writes
acceptance artifacts under `/private/tmp`; those paths are macOS-specific.
Windows needs explicit local output paths before using this driver.

The canonical definition contains two input panels and three new RK components.
It needs no EleFront, old RK component, SDK object or service account. The example
interprets only the reviewed `complex::*` geometry and explicit floor elevations
in metres. It retains all 33 floor slices, three utility objects, nine space
volumes and the shared service scope. Context geometry stays external.

Compare canonical content and geometry associations against the retained
[design comparison](../research/full-migration/turn3/rhino-comparison.json), not
counts alone. New UUIDs derive from stable Rhino identities and coordinates.
Historical transport conversion retains its original domain UUIDs, so acceptance
must record their explicit correspondence. The old comparison scripts belong to
their captured checkpoint; do not treat them as current API examples.

## Authoring and identity

Generic components accept canonical field JSON. An omitted record ID uses the
saved component identity. Supply an explicit ID to reuse identity; cloning a
component without it creates a new object. Content changes create a new Model
revision and retain the predecessor through recomputation.

`Compose.Clone` changes only the selected record ID when `reuseIdentity` is false.
References and owned Value IDs remain explicit. Clone those Values separately
before combining both owners. Composition rejects conflicting ownership instead
of silently copying a graph. Export returns text and a checked envelope; it does
not write, authenticate, solve or publish.

`Validator.Check` overloads check structural records and local Model references.
`Validator.Require` rejects invalid authoring before composition or export.
Python remains the complete semantic acceptance boundary for units, expressions,
composition and Run trees. C# does not duplicate those full validators.

## External acceptance and retained source

Builds and record round trips are separate from host loading and connector
acceptance. A later Rhino generation requires its own host check. The official
connector's [Windows gate](../contributing/windows-acceptance.md) remains open;
a macOS authoring pass or offline envelope test cannot close it.

Old .NET Framework/Speckle-inherited source and resources remain in
`src/grasshopper/legacy/`, outside active compile/resource items. Follow
[legacy retirement](../contributing/legacy-retirement.md) before removing them.
The original [`exampleDesignConfig.ghx`](../../examples/grasshopper/exampleDesignConfig.ghx)
and Rhino source stay as evidence after that implementation is retired.
