# Hypar directory removal — 6 October 2026

The user requested removal of the repository-root `hypar/` directory after
retiring Hypar support in Turn 3. The directory is now absent.

The inspection found no Git-tracked files, no unignored untracked files, no
symlinks and no nested Git repository. Its 831 files occupied 121,697,944 bytes.
All were under ignored `bin`, `obj` or `.idea` directories, apart from a root
`.DS_Store`. All 24 C# files were generated files under `obj`; no maintained
source project was present. A tracked-content search found Hypar references
only in documentation outside historical research and generated walkthrough output.

[The removal manifest](removed-files.json) records the starting HEAD, capture
time, relative paths, sizes and SHA-256 hashes before deletion. It records what
was removed; it is not a backup of those files. Earlier research and verification
records remain unchanged. This request supersedes the earlier instruction to
retain the local Hypar residue as historical files.

Checks used, from the repository root:

```sh
git ls-files -- hypar
git ls-files --others --exclude-standard -- hypar
git grep -Il -i hypar -- ':!docs/research/**' ':!walkthrough/_build/**' ':!src/rangekeeper/adapters/cytoscape/assets/**'
```

A filesystem inventory included ignored files and verified their location and
hashes. Deletion was limited to the inspected repository-root directory. The
directory's absence and the unchanged `.gitignore` and Syncthing conflict file
were checked afterward. No production code, dependency declarations or test
expectations changed. Runtime tests were not needed for this residue removal.

Current architecture and migration documents now identify Hypar as removed,
with no migration or acceptance task. The separate
[Windows connector gate](../turn4/RETIREMENT.md) still holds the isolated Python
and C# predecessor directories. No commit or push was performed.
