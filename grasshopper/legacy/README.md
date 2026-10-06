# Windows-gated C# predecessor

These old Speckle-inherited classes, components, tests, icons and exploratory
Grasshopper definition are retained for the Windows connector retirement gate.
Their bytes are unchanged by relocation. They are outside all active compile and
resource items; there is no legacy build project or runtime alias here.

The active `Model`, `Components` and `Tests` projects remain in their existing
locations and target .NET 8. Do not add this directory to those projects. The
canonical Model fields still come from LinkML generation.

Original `Tests/exampleDesign.3dm` and `Tests/exampleDesignConfig.ghx` remain at
their original paths as preserved source evidence. The active definition is
`Tests/exampleDesignCanonical.ghx`. The historical files are not candidates for
automatic deletion when this implementation is retired.

The current [Windows procedure](../WINDOWS_DEVELOPMENT.md) governs the gate.
Offline fixtures and a Mac build do not close it. No publication is authorised
by this relocation. See the [move map](../../docs/research/full-migration/legacy-isolation/moves.json)
and [byte-preservation proof](../../docs/research/full-migration/legacy-isolation/move-proof.json).
Follow the [cleanup checklist](../../docs/research/full-migration/turn4/RETIREMENT.md#cleanup-checklist-after-the-windows-gate-closes)
to remove this tree with the Python predecessor and its tests after the gate closes.
Keep the active projects and original Rhino/GHX evidence listed in that checklist.
