# Windows development and acceptance runbook

This runbook provisions and operates the dedicated Windows host used to build
and accept Rangekeeper's Rhino 8/Grasshopper/Speckle v3 authoring path. It is the
operational companion to Phase 6 of
[`GRAPH_REFACTOR_IMPLEMENTATION_PLAN.md`](../GRAPH_REFACTOR_IMPLEMENTATION_PLAN.md).

The C# projects are still Rhino 7/.NET Framework/Speckle v2 at the time this
runbook is introduced. Commands marked **target** become authoritative when the
Phase 6 retargeting lands. Do not record a successful version manifest until the
new component assembly has passed the complete acceptance procedure.

## Responsibilities by host

| Capability | macOS development host | Windows acceptance host |
|---|---:|---:|
| Python graph/Table/adapter tests | Yes | Yes |
| Speckle-independent C# domain tests | Yes | Yes |
| Cross-language Snapshot fixture tests | Yes | Yes |
| Grasshopper assembly build | Optional | Required |
| Rhino 8 component loading and GHX recomputation | No | Required |
| Official Speckle v3 connector conversion/publication | No | Required |
| Published-package receive and notebook regression | Optional | Required |

Use native Windows and PowerShell for the repository and agent. WSL is useful
for unrelated Linux tooling, but it is not the acceptance environment because
Rhino, Grasshopper, their plugin paths, and the Speckle connector are native
Windows applications.

## Security and access

- Use a dedicated, non-administrator Windows account for normal development and
  acceptance work.
- Authenticate SSH with a key. Disable password authentication when practical.
- Restrict SSH to the trusted LAN or a private VPN/mesh network. Do not expose
  Codex app-server transports or an unrestricted SSH listener to the internet.
- Keep the repository in a separate Windows checkout, for example
  `C:\src\Rangekeeper`. Do not operate the same Git checkout through a VM-shared
  folder from both operating systems.
- Keep the Windows desktop session unlocked while using Rhino, Grasshopper, or
  Computer Use. SSH remains usable when the desktop is unavailable, but it
  cannot click or inspect GUI applications.
- Never commit Speckle tokens, SSH keys, account databases, `.env` contents, or
  screenshots containing private model/account information.

## Required software

Install and configure:

1. Windows 11 x64 with current security updates.
2. Rhino 8 with a valid licence.
3. Grasshopper supplied with Rhino 8.
4. The official Speckle v3 connector for Rhino/Grasshopper.
5. Git.
6. The .NET SDK selected by the retargeted C# projects.
7. Python and `uv` compatible with `src/pyproject.toml`.
8. Codex, authenticated and available as `codex` on the SSH user's login
   `PATH`.
9. The ChatGPT/Codex Windows desktop app with Computer Use enabled if Codex will
   operate Rhino interactively.

The Windows desktop app can be installed with the current official installer or
with:

```powershell
winget install --id 9PLM9XGG6VKS -s msstore
```

Follow current official OpenAI instructions when installing the Codex CLI; then
verify it from a fresh SSH login rather than only from an interactive desktop
terminal. See the official documentation for
[Windows](https://learn.chatgpt.com/docs/windows/windows-app) and
[remote connections](https://learn.chatgpt.com/docs/remote-connections).

Follow the official Speckle documentation for the supported
[connector installation](https://docs.speckle.systems/connectors/installation)
and
[Grasshopper workflow](https://docs.speckle.systems/connectors/grasshopper/grasshopper).

## Pin the accepted environment

Record these values in the acceptance result for every published test version.
Do not use `latest` as a recorded value.

| Dependency | Accepted version/build |
|---|---|
| Windows | Pending first acceptance run |
| Rhino | Pending first acceptance run |
| Grasshopper | Pending first acceptance run |
| Speckle Rhino/Grasshopper connector | Pending first acceptance run |
| .NET SDK | Pending C# retarget |
| Rangekeeper commit | Pending acceptance run |
| Python | Pending acceptance run |
| `uv` | Pending acceptance run |

After upgrades, rerun the entire acceptance procedure before changing the
accepted version manifest.

## SSH and Codex connection

Configure the Windows OpenSSH server, start it automatically, and authorize the
Mac's public key for the dedicated user. From the Mac, define a concrete host
alias in `~/.ssh/config`:

```sshconfig
Host rangekeeper-windows
  HostName <private-lan-or-vpn-address>
  User <windows-user>
  IdentityFile ~/.ssh/id_ed25519
```

Verify both the shell and Codex path:

```bash
ssh rangekeeper-windows
ssh rangekeeper-windows codex --version
```

In the Mac Codex app, open **Settings -> Connections -> SSH**, add the concrete
`rangekeeper-windows` alias, and save the Windows Rangekeeper checkout as a
remote project. Matching saved Git projects allow a task and its Git state to
be handed between the Mac and Windows hosts.

## Repository setup

Use a normal Windows-native checkout:

```powershell
New-Item -ItemType Directory -Force C:\src
Set-Location C:\src
git clone <rangekeeper-remote-url> Rangekeeper
Set-Location C:\src\Rangekeeper
git switch feat/entity-area-core
```

Configure repository access using the dedicated user's normal Git credentials.
Do not copy the Mac `.git` directory or share one worktree across hosts.

Speckle connector authentication is performed interactively on Windows. Python
live tests may use a separately provisioned `src\.env`, but its values must be
transferred through a secure channel and must never appear in Git, terminal
transcripts, task messages, or acceptance results.

## Target build and test commands

Phase 6 must make these commands succeed from the repository root:

```powershell
dotnet restore .\grasshopper\Rangekeeper.sln
dotnet build .\grasshopper\Rangekeeper.sln --configuration Release
dotnet test .\grasshopper\Tests\Tests.csproj --configuration Release

Set-Location .\src
uv sync
uv run pytest -q
```

The C# suite must include Speckle-independent domain tests and canonical
Snapshot fixtures shared with Python. Grasshopper-specific tests may require a
separate Windows-only target, but it must be callable without manually editing
project files.

The Release build must produce one clearly named Rangekeeper `.gha` plus only
its required runtime dependencies. The implementation must add a repeatable
PowerShell install action that copies those artifacts into a dedicated
Grasshopper Libraries subdirectory. Do not document a guessed output path;
record the exact command here when the retargeted project establishes it.

After replacing an installed `.gha`, fully close Rhino before copying the new
assembly, then restart Rhino to avoid testing a previously loaded binary.

## Connector-boundary spike

Before rebuilding the complete GHX, create the smallest possible Rhino 8
Grasshopper definition that proves this supported path:

```text
one Rhino geometry
    -> ordinary Rangekeeper entity metadata
    -> official Speckle Data Object
    -> official Collection carrying the Snapshot envelope
    -> explicit Publish
    -> Python receive and Snapshot reconstruction
```

Use the spike to freeze:

- the stable entity/application-ID mapping;
- the Data Object property names and supported value shapes;
- the exact root Collection property nesting;
- the canonical Snapshot payload encoding;
- the received Python `Base` shape; and
- connector behavior for empty, null, nested, and non-ASCII metadata.

Commit a sanitized fixture and contract test. Do not couple Rangekeeper to the
connector's internal Goo/wrapper classes.

## Interactive acceptance procedure

1. Record the environment version manifest and Rangekeeper commit.
2. Build, test, and install the Release `.gha`.
3. Start Rhino 8 and confirm the official Speckle connector is authenticated to
   the intended account.
4. Open `grasshopper\Tests\exampleDesign.3dm`.
5. Open the rewritten
   `grasshopper\Tests\exampleDesignConfig.ghx`.
6. Confirm that Grasshopper reports no missing components, obsolete components,
   plugin load errors, or unexpected runtime warnings.
7. Keep the Publish run input false. Recompute the definition and inspect the
   Rangekeeper validation output.
8. Confirm the expected source selection and entity-to-geometry associations.
9. Confirm the pre-publish graph baseline: 50 entities and 63 relationships,
   split into 49 `spatiallyContains`, 3 `contains`, and 11 `services`.
10. Confirm deterministic Snapshot output across a second recomputation.
11. Select the explicitly authorized Speckle v3 project/model.
12. Trigger Publish once and record only the non-secret project/model/version
    identifiers required for the acceptance result.
13. Reset the Publish run input to false.
14. Receive the published root through Python and run the live adapter contract
    and graph-baseline tests.
15. Execute `walkthrough/load_design.ipynb` and
    `walkthrough/drive_model_from_design.ipynb` top-to-bottom.
16. Compare all documented graph and financial regression anchors.

Publication is never an incidental recomputation side effect. If any validation
or count check fails, do not publish merely to inspect the failure remotely.

## Acceptance result

Keep a sanitized, reviewable result containing:

- UTC timestamp;
- Windows, Rhino, Grasshopper, connector, .NET, Python, and `uv` versions;
- Rangekeeper Git commit;
- C# and Python test summaries;
- `.gha` file version/hash;
- GHX missing/obsolete component count;
- entity and relationship counts by classification;
- deterministic Snapshot hash;
- Speckle project/model/version identifiers that are safe to retain;
- Python receive/round-trip result;
- notebook execution result and regression differences; and
- the operator or Codex task that performed the run.

Exclude tokens, credentials, private URLs, raw account databases, and
unsanitized model payloads.

## Failure boundaries

- **SSH succeeds, GUI unavailable:** continue builds and unit tests; defer Rhino
  interaction until an unlocked desktop session is available.
- **Codex exists interactively but not over SSH:** fix the dedicated user's
  login `PATH`, then rerun `ssh rangekeeper-windows codex --version`.
- **Rhino loads an old assembly:** close every Rhino process, reinstall the
  Release artifacts, restart, and verify the assembly version/hash.
- **Missing GHX components:** stop and inventory plugin/component GUIDs. Do not
  silently replace nodes with behaviorally different components.
- **Connector envelope changes after an upgrade:** rerun the boundary spike and
  adapter fixture tests before changing production code or the accepted version
  manifest.
- **Published graph differs from the baseline:** compare the pre-publish
  Snapshot first. This separates source/component errors from connector or
  receive-adapter errors.
