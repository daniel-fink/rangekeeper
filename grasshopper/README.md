# Canonical Rangekeeper authoring for Rhino 8

The active projects target `net8.0`. The Model project has no Rhino or Speckle
reference. Generated fields come from RK's resolved LinkML bundle; handwritten
code owns presence-preserving serialization, authoring, composition and diagnostics.
The Components project uses the installed RhinoCommon, Grasshopper and GH_IO
assemblies. Package dependencies are pinned in project files and lockfiles.

The active target is Rhino 8 on .NET 8. Build and record round-trip checks run
separately from host loading and connector acceptance. A later Rhino generation
needs its own host check. See the [Windows procedure](WINDOWS_DEVELOPMENT.md).

```sh
python tools/schema/generate_csharp.py --check
dotnet restore grasshopper/Components/Components.csproj --locked-mode
dotnet build grasshopper/Components/Components.csproj --no-restore
dotnet build grasshopper/Tests/Tests.csproj
```

Run Python fixture preparation with `docs/research/full-migration/turn3/cross_language.py
prepare DIRECTORY`; run `Tests.dll DIRECTORY/python.json DIRECTORY/csharp.json`
with a .NET 8 host, then run the Python `check` command. This verifies rich content,
UUID references, dates, omission/null, zero/false, separate collections, immutable
access and ordered mathematics through both language boundaries.

Load the built Components assembly and its adjacent dependencies into a fresh
Rhino 8 process. `Tests/accept_rhino.py`, run with Rhino's `RunPythonScript`, builds,
saves, reopens and recomputes `Tests/exampleDesignCanonical.ghx` and writes temporary
acceptance output. It reads `Tests/exampleDesign.3dm` without changing it. The
canonical GHX contains two input panels and three new RK components. No EleFront,
old RK component, SDK object or service account is required.

The example interprets only the reviewed `complex::*` geometry and explicit floor
elevations in metres. It retains all 33 floor slices, three utility objects, nine
space volumes and the shared service scope. Context geometry remains external.
Compare the exported Model with the historical design using the separate
`compare_rhino.py`; counts alone are insufficient. The new UUIDs derive from stable
Rhino object identities and coordinates. The historical transport converter keeps
its original domain UUIDs; acceptance records their explicit correspondence.

Generic components accept canonical field JSON. Omitted record IDs use the saved
component identity. Supply an explicit ID to reuse identity; cloning a component
without that input creates a new object. Model content changes create a new
revision and preserve its predecessor through recomputation. `Compose.Clone`
changes only the selected record ID when `reuseIdentity` is false. References and
owned Value IDs remain explicit; clone those Values separately before combining
both owners. Composition rejects conflicting ownership instead of silently
copying a graph. Export returns text
and a checked envelope; it does not write, authenticate, solve or publish.

Python validation remains the full semantic acceptance boundary. C# authoring
checks cover the shared structural contract and local identity/reference rules;
they do not duplicate the complete Python units and mathematics validators.

The old .NET Framework/Speckle-inherited source and resources are isolated in
[legacy/](legacy/README.md), outside the active compile/resource lists, pending
the Windows retirement gate. The
original `exampleDesignConfig.ghx` remains unchanged.

The official current Speckle connector is a separate Windows gate. See
[the procedure](WINDOWS_DEVELOPMENT.md) and the [integration contract](../docs/INTEGRATIONS.md).
Mac authoring and offline envelope tests do not claim Windows connector acceptance.

`Validator.Check` overloads check structural records and local Model references.
`Validator.Require` rejects invalid authoring before composition or export.
