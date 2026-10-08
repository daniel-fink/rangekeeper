# Legacy isolation evidence — 6 October 2026

The held predecessor is relocated, not deleted. See the
[namespace contract](../../../contributing/legacy-retirement.md) and
[remaining Windows gate](../turn4/RETIREMENT.md).

Starting HEAD is `305f3ff6d460834ea803bae2fa6ad5c48a1627c9`, with the accepted
Turn 4 changes already uncommitted. `baseline.json` records that state and 520
input hashes. The relocation preserves that work and all 91 protected files.
No commit, push, release, service call or external publication occurred.

## Scope and preservation

`moves.json` records 51 direct moves: 19 Python implementation files, seven whole
Python test files, and 25 C#/resource files. It also records original hashes.
Two mixed test files were split; their canonical checks remain outside `tests/legacy`.
The old graph initializer was split into canonical and predecessor exports.
Graph errors were split by domain; their predecessor class/function bodies are
unchanged. The redundant nested `graph/legacy/__init__.py` was removed after its
View and reduction modules moved directly into `rangekeeper.legacy.graph`.

`move-proof.json` and `final-state.json` verify that all 19 moved Python
implementation bodies are unchanged except imports. All 25 C#/resource moves
preserve their bytes. Active C# source/project files, canonical algorithms,
schema records and original host inputs are unchanged. Original `.gitignore`
edits, Syncthing conflict copy, workbooks and archives remain protected.

The synthetic `src/tests/fixtures/migration/graph-v1.json` was captured before
relocation. Its expected identities and hash are recorded beside it. Canonical
conversion tests use this fixed historical wire document without importing any
predecessor implementation. Python module paths changed; persistent JSON tags did not.

## Acceptance

One wheel was built and used for installed checks:

```text
rangekeeper-0.8.71-py3-none-any.whl
SHA-256 3df68252e3ed4dc9c654091ec248fe0fe8de32ac00685aae50d4d99af468fcc8
```

| Check | Result | Evidence |
|---|---|---|
| Full local suite | **1,063 passed; 24 skipped** | `full-suite.txt`, `full-suite.xml` |
| Focused relocation, conversion and mixed-test checks | 265 passed | `focused.txt` |
| Python/C# generation freshness | Passed | `generation.txt`, `csharp-generation.txt` |
| Static typing and intended negative calls | Passed | `typing.txt` |
| Installed core, units, stores, optional financial/execution and source workflows | Passed | `installed.txt` |
| Installed explicit legacy Graph/Measure/API, JSON and table checks | Passed without service calls | `legacy-installed.txt` |
| C# .NET 8 solution build | Passed; zero warnings/errors | `csharp-build-retry.txt` |
| Python → C# → Python content and presence | Passed | `cross-language-*.txt` |
| Canonical-to-legacy import audit | Zero such imports; zero old-path imports | `audit-final.txt`, `imports.json` |
| Current locations for all frozen symbols | 671 assigned | `ledger.json` |
| Protected files, moved bodies and tested-wheel/source identity | Passed | `final-state.json` |

The five additional tests enforce absent old paths, canonical graph exports,
source dependency direction and conversion without predecessor imports. The 24
MiniZinc skips are the same optional environment gap. The three live tests now at
`src/tests/legacy/test_api.py` remain excluded and unverified.

The first focused run found two test-migration mistakes: a stale expected export
list and a remaining dynamic fixture call. Both were corrected, then the focused
and full suites passed. The first C# build was interrupted after prolonged lack
of progress; its zero exit code is not treated as acceptance because it had no
completed-build summary. The serial build with shared build servers disabled
completed. The preservation helper initially included updated host documentation
in its unchanged-code list; the corrected check names those two document changes.
These are retained verification/setup records, not changes to expected financial results.

The seven schema suites, seven walkthrough executions, three real project rebuilds
and Mac UI acceptance are the earlier Turn 4/Turn 3 evidence. They were not rerun
for this file relocation. Current checks include fresh installed canonical
execution/workflows and cross-language serialization. All schemas, canonical
algorithms and active host source remain unchanged. No fresh Windows acceptance
or new Rhino UI recomputation is claimed.

## Reproduction

`commands.jsonl` records exact commands, working directories, selected environment,
exit status and duration. It does not retain credentials. Run Python tests from
`/Volumes/Data/Projects/Rangekeeper/src`:

```sh
MPLBACKEND=Agg MPLCONFIGDIR=/private/tmp/rk-legacy-isolation-mpl PYTHONDONTWRITEBYTECODE=1 /private/tmp/rk-full-runtime/bin/python -m pytest -q --ignore=tests/legacy/test_api.py
```

The runtime is Python 3.10.19. Schema generation uses the unchanged LinkML 1.11.1,
linkml-runtime 1.11.1, jsonschema 4.26.0 interpreter at
`/private/tmp/rk-probe-audit-venv/bin/python` and the existing isolated PYSTOW cache.
Typing uses mypy 1.18.2 through the retained `tools/schema/typecheck.py` harness.
The earlier full dependency manifests are in `../turn4/environment-final.json`.
Dependencies were not changed by this relocation.

From the repository root, run `audit.py` and `verify_final.py` in this directory.
The latter expects the recorded wheel under `/private/tmp/rk-legacy-isolation-wheel`.
Build a new wheel in a fresh directory with the Turn 1 isolated build helper; use
that same artifact for every installed check. `verify_installed.py` runs outside
the checkout with `PYTHONPATH` pointing to the unpacked wheel. The normal installed
core and solver/workflow checks use `tools/schema/verify_install.py`.

Build C# with the explicit command in `csharp-build-retry`:

```sh
DOTNET_CLI_HOME=/private/tmp/rk-dotnet-home NUGET_PACKAGES=/private/tmp/rk-nuget /opt/homebrew/bin/dotnet build grasshopper/Rangekeeper.sln --no-restore --disable-build-servers -m:1 -p:UseSharedCompilation=false
```

Run the Turn 3 cross-language fixture helper with the candidate wheel, then the
rebuilt `Tests.dll` with Rhino's .NET 8 arm64 host and the prepared JSON paths,
then the Python check. Those exact paths and commands are logged. Do not execute
or enable the files in `grasshopper/legacy` to verify the canonical projects.
