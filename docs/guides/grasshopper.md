# Author Models in Grasshopper

The .NET solution lives at [`src/grasshopper/`](../../src/grasshopper). The active
projects target `net8.0` and Rhino 8. The Model project has no Rhino or Speckle
reference. LinkML generation owns persistent fields; handwritten code owns
presence-preserving serialization, authoring, composition and diagnostics. The
Components project uses the installed RhinoCommon, Grasshopper and GH_IO
assemblies. Dependencies are pinned in project files and lockfiles.

This independent source project is outside the Python package. Canonical IO and simple local display remain in `io` and `visualisation`. See the
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

## Check generic authoring in Rhino

Set `RK_COMPONENTS` to the current RK component assembly and `RK_ACCEPTANCE_OUTPUT`
to a new output directory. Run [the generic driver](../../src/grasshopper/Tests/accept_rhino.py)
inside a fresh Rhino 8 process. It checks stable identity, changed revisions, previous
revision links and save/reopen behaviour. It loads the RK authoring assembly.

The current [generic authoring definition](../../examples/grasshopper/genericAuthoring.ghx)
uses only RK 0.9.0 components. Source-specific extraction is a consumer concern.
The original `.3dm` and GHX files here remain source evidence; their old assembly
metadata is not an installed compatibility contract. Windows host checks remain open.

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
