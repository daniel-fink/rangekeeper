# Research and verification evidence

Subdirectories retain experiments, migration baselines, captured commands and
acceptance results. Each result applies to the source and environment recorded
with it. Old paths and dependency names in logs are evidence, not current APIs.
Do not rewrite captured output to match a later implementation.

Use [current guides](../README.md) for contracts and [verification](../contributing/verification.md)
for commands. [Historical plans](../history/README.md) explain earlier sequencing.
The [MiniZinc evidence](full-migration/minizinc/README.md) and
[strict layout procedure](../contributing/layout-acceptance.md) document solver acceptance.

- [Flux and Stream implementation acceptance — 2026-10-08](flux-stream-2026-10-08/README.md): numerical and acausal checks, installed wheel, performance and memory.
- [First walkthrough acceptance — 2026-10-08](basic-dcf-2026-10-08/README.md): legacy teaching fidelity, fresh notebook execution and rendered review, following [API acceptance](basic-dcf-2026-10-08/api.md) for direct Flow display and projection verbs.
