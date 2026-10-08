# Maintain the documentation

Agents and developers update affected documentation in the same change as the
code. Follow this procedure without waiting for a separate documentation request.
The [main index](../README.md) provides the navigation; the
[architecture](../concepts/architecture.md) owns the repository and package maps.

## Choose the owner

| Content | Home |
| --- | --- |
| Intent, concepts and architectural boundaries | `docs/concepts/` |
| Current inputs, results, errors, constraints and side effects | `docs/reference/` |
| Steps to perform a user task | `docs/guides/` |
| Development, documentation and acceptance procedures | `docs/contributing/` |
| Enduring choices, rationale and active implementation plans | `docs/decisions/` |
| Superseded narratives and completed, superseded or withdrawn plans | `docs/history/` |
| Captured experiments, logs, outputs and source snapshots | `docs/research/` |
| Complete runnable examples and reusable wire examples | `examples/` |

Give each contract one authoritative page. Extend that page when the new behavior
belongs to its responsibility. Add a page only for a distinct contract or reader
task. Link to shared rules instead of copying them. Reference pages may contain
small illustrations; link complete examples to their maintained source.

Maintained prose lives in `docs/`. Root `README.md`, root `CONTRIBUTING.md` and
`examples/README.md` are short navigation entrypoints. Notebook narrative and the
book introduction stay with their executable example. Generated schemas and
record documentation retain their source and package locations.

Use repository-relative links and descriptive headings. State the working
directory and prerequisites before each command. Apply ASD-STE100 principles;
retain exact API names and domain terms when they make the text more accurate.

## Routine upkeep for agents and developers

Maintain the docs as part of each authorized change. Do not wait for a separate
documentation request to correct affected instructions, links or plan status.
This procedure runs during development; it does not imply a scheduled background
service.

1. Read the documentation index and the page that owns the changed capability.
   Identify affected APIs, schema fields, imports, file paths, commands, examples,
   dependencies and acceptance requirements. Search for their names and old paths
   across source, docs, examples, tools and build configuration.
2. Update the authoritative current page in the same change. Update its callers,
   example instructions, migration notes and navigation links. Extend an existing
   page before creating another one. Update schema descriptions in YAML and use
   the generator for generated fields and API documentation.
3. Check the affected plans and decisions against the actual result. Update only
   statuses supported by implementation and verification evidence. Record any
   incomplete work, failed checks and external acceptance gates explicitly.
   Do not infer completion from file age, a proposed design or a passing subset.
4. Apply the lifecycle rules below. Before archiving a plan, put its useful current
   contracts in maintained guides. Transfer each outstanding item to an active
   plan or acceptance procedure and link it. Preserve stable RF/decision IDs,
   rationale, original scope and recorded results.
5. Update incoming links, outgoing relative links and section anchors after a
   move. Update the main docs index and the history or decision index. Use links
   to a verified Git revision for source that existed only at the old checkpoint.
   Do not leave duplicate active copies or forwarding pages by default.
6. Run `python tools/docs/check.py` from the repository root, then run the
   commands/examples affected by the edit. Run generation
   checks when generated material changes. If book sources or configuration
   change, build the book and inspect its navigation. Preserve captured logs,
   notebook outputs and historical source snapshots; add new dated evidence.
7. Review the diff for contradictory status, duplicate contract definitions and
   orphan pages. Report which docs changed, which plans moved, the checks run and
   the remaining work. Include the documentation changes with the implementation
   when that implementation is committed.

## Plan and decision lifecycle

| Record and trigger | Required action |
| --- | --- |
| Proposed or active plan | Keep it in the current plan/decision index, with its scope and unresolved items visible. |
| Plan fully implemented and verified within its stated scope | Mark it `implemented`; move it to `docs/history/plans/` after current guides and evidence are updated. Do not call it superseded merely because it is complete. |
| Plan replaced by an agreed successor | Mark it `superseded`; link both directions and transfer unfinished work before moving it to `docs/history/plans/`. A proposal alone does not supersede an agreed plan. |
| Plan partly replaced | Mark the affected sections and link their successor. Keep the plan active while it owns unresolved work. |
| Plan explicitly abandoned | Mark it `withdrawn`, record the reason, and archive it. Do not abandon work merely to tidy the docs. |
| Enduring architectural decision | Keep its stable identity in the decision index. When replaced, mark it `superseded` and link both directions; retain the decision record for rationale. |
| Dated narrative or verification result | Keep it under `history/` or `research/` respectively. Add a dated status note or successor link without rewriting the original evidence. |

Keep an archived plan's filename where possible. Add a small dated header with
its status, implementation revision or successor link, current guide links and
any carried-forward work. Preserve its original body and identifiers. Archive
navigation, relative links and status headers can change; preserve the original
narrative and captured evidence.

Use this completion check for every change: **current guides match the code;
examples and commands use current paths; superseded plans are archived and linked;
unfinished work remains visible; verification claims match the checks run.**

## Verification records

Record the date, source revision, command, environment and limits of a result.
Current guides contain repeatable procedures; dated records contain observed
counts and outcomes. Do not turn a local test pass into a claim about remote CI,
a live service or a Windows host. Keep each open gate linked from its current
acceptance procedure.

Captured evidence is immutable. When a result changes, add a new dated result and
link the earlier one. Update navigation around old evidence, not the recorded
output, source snapshot or historical command. A moved plan may receive a status
header and corrected links; retain its original rationale, identifiers and result
narrative.

See [verification](verification.md) for repository checks and
[the decision index](../decisions/README.md) for current decisions and plan status.
