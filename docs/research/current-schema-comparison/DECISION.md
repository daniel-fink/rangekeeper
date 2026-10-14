# Schema decision: retain LinkML

Status: accepted by Daniel, 2026-10-02.

Retain LinkML as the authoritative Rangekeeper record schema. Close the CUE
comparison for the current implementation stage and proceed to the scalar
execution checkpoint. Native CUE implementation is not a prerequisite.

## Basis for the decision

The [independent audit](audit-2026-10-02/README.md) reproduced the original
import-route results case for case. Its full pass covered 713 schema/input
pairs: 572 matching outcomes, 28 differences, 106 five-second timeouts, and
seven non-finite inputs outside strict JSON. All seven existing schema suites
passed again. Original results and the audit evidence remain preserved.

Sixteen invalid inputs were accepted after import because code/name pattern
restrictions were dropped. Twelve valid Query/Expression inputs were not
accepted; their diagnostics include matching constraints and structural cycles.
Timeouts remain inconclusive. Twenty-seven matching rejections contain cycle
diagnostics and do not establish equivalent rejection reasons.

These observations concern LinkML-generated JSON Schema imported into CUE.
They do not establish that directly authored CUE is unsuitable. The complete
native candidate and its Python record boundary were not implemented. Daniel
decided that the potential benefits do not justify that further investment and
migration for the current project. This is a deliberate architectural trade-off,
not a claim that CUE failed a completed native evaluation.

## Benefits considered and costs accepted

| Native CUE opportunity | Cost or limitation for Rangekeeper |
| --- | --- |
| Directly executable definitions, alternatives, and cross-field constraints. | Requires a fresh design and conformance work; recursive correctness and performance remain unproven for the complete contract. |
| Potentially express more validation beside record structure. | Revision resolution, provenance-aware composition, units, execution, and publication still require explicit domain behavior. |
| Reusable constraints and optional CUE-based authoring. | CUE unification does not implement RK's rule that independent authoritative contributions conflict even when equal. JSON/YAML authoring can already continue with LinkML. |
| Avoid JSON Schema translation for authoritative validation. | Python must integrate CUE validation and obtain schema-derived typed records without a second handwritten field schema. That complete route has not been demonstrated here. |
| A flexible schema/constraint language. | LinkML already supplies a domain metamodel, Python record generation, and documentation/export tooling used by this project. Replacing these adds maintenance responsibilities. |

Retaining LinkML does not imply that its generated artifacts preserve every
schema rule. Existing generator limitations remain explicit. Structural
validation, semantic validation, numerical acceptance, and publication are
separate responsibilities. Generated Python construction alone is insufficient.

## Selected implementation boundary

- LinkML owns record shapes, identities, typed references, and schema metadata.
- Generate shared Python record machinery from the Model, Specification, and Run
  import bundle, plus pinned closed JSON Schemas. Do not hand-maintain a second
  authoritative set of Python field definitions.
- Perform structural preflight before loading records. Reuse and evolve the
  existing semantic validators for scope, ownership, composition, and Run rules.
- Contain generated record mutability behind immutable snapshot and revision-store
  boundaries. Preserve meaningful omission/null/zero/false and collection order.
- Fingerprint and reproduce generated artifacts; package them from the first
  schema-backed library implementation and verify installed-package behavior.
- Use the already selected Pyomo with HiGHS backend. CUE and LinkML are not the
  numerical execution backend.

## Next implementation step

The subsequent 2026-10-02 architecture revision replaces the temporary executor
and later promotion sequence. Step 1 is now complete: the
[domain migration map](../../history/DOMAIN_MIGRATION_MAP.md) specifies canonical ownership,
the generated immutable record boundary, APIs and consumer migration; its linked
baseline records observed checks. Next generate the shared record artifacts and
build the minimal core directly in the intended library
packages, including private generated artifacts, validation, codecs, and immutable
revision storage. Then probe and pin Pyomo/HiGHS and implement
`rangekeeper.execution` against that core, following the
[architecture acceptance boundary](../../LIBRARY_ARCHITECTURE.md#validation-and-execution).
Load the actual Model and composed Specifications, lower their declared affine
scalar mathematics, independently check candidates, and publish genuine Runs and
immutable output Models.

Required demonstrations include forward valuation (NOI 550,000 AUD/year and
capital value 11,000,000 AUD), inverse valuation (rent 27,500 AUD/dwelling/year
and NOI 500,000 AUD/year), and inverse reuse of a genuine forward output without
inheriting its solve roles. Changed-expression tests must establish that execution
uses the declared mathematics. Include units, bounds, unsupported capabilities,
inconsistency, underdetermination, resource limits, direct batch accounting,
settings, lineage, and provenance as specified in the architecture plan.

Migrate graph algorithms and existing consumers incrementally around the new
canonical Model. Temporal Values, policy optimization, and unrelated adapter
repair remain later work. The first scalar solve requires the minimal replacement
core, but not migration of every consumer. This decision adds no commit, push, or release
authorization.
