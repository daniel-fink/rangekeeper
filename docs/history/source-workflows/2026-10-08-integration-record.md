# Integration observations retained on 8 October 2026

Status: historical extract. These statements came from the former
`INTEGRATIONS.md` and `ingestion-workflow.md` pages. They record their authors'
observations, not a new execution or current external acceptance. The former pages
did not assign a separate date to every observation. Host and service behavior
must be checked through the current [Windows acceptance procedure](../../contributing/windows-acceptance.md).

Current contracts: [source workflows](../../reference/workflow.md),
[design transport](../../reference/design-transport.md) and
[Grasshopper](../../guides/grasshopper.md).

## Real source consumers

Mandarin and both East Whisman scenarios now use outer workflow documents v2.
Their extraction policies retain their own versions. Former Features become
property Values; every measurement has an owner-local key. Six Mandarin, two
December, and 34 November unresolved measurements are now explicit, alongside
preserved descriptive properties and findings. Zero remains distinct from missing.

Business UUIDs, source checksums, reviewed decisions and calculation scopes remain.
East Whisman keeps square-foot units and separate source scenarios. No tower
crosswalk, basement allocation, individual apartments or deletion from absence is
inferred. Projects remains an environment-only repository with YAML interpretation
and thin notebooks. The reference graph enters only a separate comparator.

Strict comparisons check canonical content, mapped Value identities, quantities,
units, membership, relationship endpoints, source cells, decision records and check
outcomes. Named representation changes are recorded, not broad ignored categories.
Mandarin also retains its separate older SOM-reference comparison.

## Earlier pinned-service observation

The pinned object read succeeds with SpecklePy 3.0.7. The server currently returns
no object reference for the historical version; this is an explicit service-history
limitation. The adapter rejects it and never silently selects another version.
The independently recorded object pin is used for the live read acceptance.


## Earlier source-adapter migration

Mandarin is the proving project. Its JLL and GFA/MGP adapters now feed RK Evidence
into source review, graph composition and reconciliation. The duplicate Excel
decoder was removed; review records are presentation views. A captured baseline
checks source values, graph identities, topology, characteristics and review
meanings, while handoff tests check the intentionally richer Claim lineage.
The reviewed `NumberSpec`, `tabular.numbers`, `tabular.select` and `tabular.concat`
operations now provide reusable table transformations; see
[their API contract](../../reference/evidence.md). Project interpretation remains local.
Further promotions require explicit user review of the contract, existing
ownership and demonstrated reuse.
