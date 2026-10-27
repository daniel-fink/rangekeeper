# Grasshopper example

This folder is an unsupported example: a portable C# Model library and generic
Grasshopper components for Rhino 8 ([ADR-010](../../docs/decisions/010-layers-and-packages.md)).
It has no stability promise. CI generates its C# records, builds the Model library
and the fixture runner, and round-trips the cross-language fixtures, so the
example cannot drift from the schema.

| Path | Contents |
| --- | --- |
| `Rangekeeper.sln`, `Directory.Build.props` | The solution and its shared version |
| `Model/` | Generated records, serialization, authoring and validation. No Rhino or Speckle reference |
| `Components/` | Generic Grasshopper components. Needs the installed RhinoCommon, Grasshopper and GH_IO assemblies |
| `Tests/` | The cross-language fixture runner, the Rhino driver and the connector fixture |
| `*.3dm`, `*.ghx` | The original Rhino source and Grasshopper definitions |

The projects target `net8.0`. LinkML generation owns persistent fields;
handwritten code owns presence-preserving serialization, authoring, composition
and diagnostics. Dependencies are pinned in project files and lockfiles. Canonical
IO is in the Python package's `io`; the design envelope is a
[walkthrough helper](../walkthrough/helpers/README.md#canonical-design-transport).
See the [architecture](../../docs/concepts/architecture.md) for the repository map.

## Build and round-trip

From the repository root, use the pinned schema environment to check generated
files. Build with a .NET 8 SDK:

```sh
python tools/schema/generate_csharp.py --check
dotnet restore examples/grasshopper/Tests/Tests.csproj --locked-mode
dotnet build examples/grasshopper/Tests/Tests.csproj --no-restore -p:Version=$(python tools/version.py --dotnet)
dotnet restore examples/grasshopper/Components/Components.csproj --locked-mode
dotnet build examples/grasshopper/Components/Components.csproj --no-restore
```

The Tests project is a console fixture runner, not a `dotnet test` test project.
It and the Model project build without Rhino. The Components build needs the
Rhino assemblies. Its default `RhinoResources` location and subordinate paths
match the macOS Rhino 8 installation; on Windows, pass verified assembly
locations with `-p:RhinoResources=...`. Do not interpret a portable Model/Tests build as a component-load pass.

Install the matching Python library and `./examples` with their calculation and
execution dependencies. From the repository root:

```sh
python tools/schema/cross_language.py prepare /tmp/rk-cross-language-001
dotnet examples/grasshopper/Tests/bin/Debug/net8.0/Tests.dll /tmp/rk-cross-language-001/python.json /tmp/rk-cross-language-001/csharp.json
python tools/schema/cross_language.py check /tmp/rk-cross-language-001
```

This checks rich content, UUID references, dates, omission/null, zero/false,
separate collections, immutable access and ordered mathematics through both
language boundaries. Use a fresh output directory and record the source and
runtime versions.

## Check generic authoring in Rhino

Set `RK_COMPONENTS` to the current RK component assembly and `RK_ACCEPTANCE_OUTPUT`
to a new output directory. Run [the generic driver](Tests/accept_rhino.py)
inside a fresh Rhino 8 process. It checks stable identity, changed revisions, previous
revision links and save/reopen behaviour. It loads the RK authoring assembly.

The current [generic authoring definition](genericAuthoring.ghx)
uses only RK 0.9.0 components. Source-specific extraction is a consumer concern.
The original `.3dm` and GHX files here remain source evidence; their old assembly
metadata is not an installed compatibility contract.

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

## Host acceptance and retained source

Builds and record round trips are separate from host loading and connector
acceptance. A later Rhino generation needs its own host check. The Windows
connector gate is retired with the move of this solution out of the package; its
[procedure](../../docs/history/windows-acceptance.md) is kept as history. A macOS
authoring pass or an offline envelope test is not a connector pass.

The original [`exampleDesignConfig.ghx`](exampleDesignConfig.ghx), the other
definitions and the Rhino source stay as evidence. Follow
[legacy retirement](../../docs/contributing/legacy-retirement.md) before you
remove them.
