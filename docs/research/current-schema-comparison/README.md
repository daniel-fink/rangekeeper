# Current schema comparison and first probe

Status: schema decision accepted, 2026-10-02. Daniel chose to retain LinkML and
proceed through domain replacement and a minimal library core to scalar execution.
The [domain migration map](../../DOMAIN_MIGRATION_MAP.md) now completes Step 1;
shared generated records and structural artifacts are next. See the [decision record](DECISION.md) for the
trade-off, selected Python record boundary, and next implementation step. The
complete native CUE candidate was not implemented; this comparison is closed for
the current stage rather than claimed complete as a native-language evaluation.

The first probe uses the current Model, Specification, Run, and supporting
record contracts. It finds that importing the generated JSON Schemas into
CUE 0.17.1 does not preserve all observed validation behavior. This rules out
treating that import route as a drop-in replacement. It does not establish
whether a schema authored directly in CUE would be preferable.

This work follows the [library architecture plan](../../LIBRARY_ARCHITECTURE.md).
The [earlier comparison](../schema-tooling/README.md) tested a smaller vocabulary;
its retained evidence is unchanged. No executor or solver has been implemented.

**2026-10-02 audit:** an independent rerun reproduced the bounded results below
case for case. A further pass attempted every input without the schema-level
cutoff: 572 matches, 28 differences, 106 five-second timeouts, and seven non-JSON
numerical inputs. See the [audit and retained evidence](audit-2026-10-02/README.md)
for diagnostic qualifications and environment details. The original evidence
below is preserved as the record of the first bounded experiment.

## Baseline and shared inputs

All seven existing schema suites passed at commit
`c91a76c941bac0a26fa18ad5a3105ab4641f22f0`, with the current local documentation
changes. The environment uses Python 3.10.21, LinkML 1.11.1, and jsonschema 4.26.0.
The CUE 0.17.1 macOS arm64 download was verified against its SHA256 digest in the
official release metadata. Exact source fingerprints and download information
are retained in [the manifest](observed/manifest.json).

| Suite | Current baseline |
| --- | --- |
| `validate.py` | 13 generated schemas, both graph examples, 80 structural rejection cases. |
| `native_roundtrip.py` | Native identifiers, typed reference fields, and both graph example round trips. |
| `expressions.py` | 71 valid records, 103 structural and 31 bounded semantic rejections, native round trips. |
| `formulations.py` | 10 valid scopes, 32 structural and 20 bounded semantic rejections, 10 native round trips. |
| `models.py` | 6 valid Models, 26 structural and 24 bounded semantic rejections, 6 native round trips. |
| `specifications.py` | 17 valid Specifications, 46 structural and 37 bounded semantic rejections; 13 composition/batch acceptance checks and 35 composition rejections. |
| `runs.py` | 18 valid Run/tree cases, 28 structural and 45 bounded semantic rejections, 31 native round trips. |

[capture.py](capture.py) observes the original structural validators without
changing their outcomes or semantic checks. Six suites supplied 713 distinct
schema/input pairs across 20 distinct generated structural schemas. The corpus
includes valid declarations, malformed records, structurally valid semantic
errors, and serialized round-trip outputs. It is a record validation corpus,
not 713 independent end-to-end investigations.

## Direct CUE import results

[compare.py](compare.py) imports each generated JSON Schema using `cue import
jsonschema`, then attempts concrete validation using `cue vet -c`. Each command
has a five-second limit. After a validation timeout, remaining inputs for that
same schema are left unmeasured rather than consuming repeated timeout periods.
All 20 schema imports completed successfully.

| Outcome | Schema/input pairs |
| --- | ---: |
| Same acceptance outcome | 476 |
| Different acceptance outcome | 21 |
| Validation timeout | 3 |
| Unmeasured after a timeout for that schema | 208 |
| Non-finite Python numerical input outside strict JSON | 5 |
| Total captured | 713 |

The 21 differences comprise 13 inputs rejected by the current validator but
accepted through the CUE import route, and eight inputs accepted by the current
validator but not accepted through CUE. The rejected-input differences include
blank or improperly padded Entity codes, Binding names, Constraint codes, and
a Formulation code. For example, an Entity code of `" A"` passes this imported
CUE schema despite failing the current contract. The imported declarations do
not retain the effective code/name pattern restrictions.

The accepted-input differences include seven Query records and one Expression.
The CUE diagnostics include structural cycles or unsatisfied imported matching
constraints. The three five-second timeouts concern Model, Formulation, and
Expression schemas. An earlier diagnostic attempt on the same Model input also
exceeded 30 seconds. Neither a timeout nor a schema evaluation error establishes
that the input violates the intended record contract.

The outcome counts describe acceptance behavior. Matching rejection outcomes
alone do not prove that both validators rejected an input for the same reason.
Likewise, these timings include process startup and apply only to this import
route; they are not a general performance comparison of LinkML and native CUE.

Observed rows and bounded diagnostics are retained in [results.json](observed/results.json)
and [summary.json](observed/summary.json). The seven original suites separately
passed their semantic checks. Those checks have not been reimplemented in CUE.

## Deferred native comparison criteria

The following criteria are retained for a future explicit reconsideration of CUE;
they are no longer the next task or a prerequisite for execution. A directly
authored candidate would need to be assessed on its own merits rather than
inheriting the import-route results. The accepted decision retains LinkML.

| Boundary | Evidence required before adopting CUE |
| --- | --- |
| Structure and recursive records | Match the complete current structural corpus, including required fields, closed records, tagged variants, and mutually recursive Expression/Selection shapes. |
| Identity and ownership | Preserve UUID identity across revisions while rejecting repeated ownership within one snapshot; keep Claim content opaque where the current contract does. |
| Content states | Preserve omission, permitted nulls, unresolved quantities, zero, and false; reject non-finite content before portable JSON serialization. |
| Specification composition | Deduplicate the same pinned contribution in a diamond; reject independent authoritative contributions even when their content is equal. Ordinary unification alone is insufficient evidence. |
| Run accounting | Preserve scoped references, direct case accounting, output unions, status conventions, and trace ordering. |
| Python records | Demonstrate schema-derived typed records and an immutable snapshot boundary without maintaining a second handwritten field schema. |
| Serialization and exports | Preserve actual input content and meaningful ordering through Python and CUE; check exported schemas against the same corpus. |
| Diagnostics and maintenance | Identify the owning document/record for errors and specify which rules belong in CUE versus shared Python semantics. |
| Performance and packaging | Measure representative native validation and verify an installed Python distribution with its required schema artifacts and validation bridge. |

The tested Python-to-CUE boundary is a subprocess carrying strict JSON. CUE's
[official integration documentation](https://cuelang.org/docs/integration/)
describes its JSON/YAML and Go integration. A supported schema-derived Python
record route has not yet been demonstrated here. Keeping dictionaries and
handwriting another set of authoritative Python field definitions would not
satisfy the architecture plan.

Dimensional analysis, mathematical feasibility, and solving remain outside this
comparison. Whichever schema is chosen, the runtime still needs domain semantics,
compilation, independent numerical acceptance, and immutable publication.

## Reproduce without changing retained evidence

Use a disposable output directory, the pinned LinkML/jsonschema environment,
and an explicitly selected CUE 0.17.1 executable. Set `PYSTOW_HOME` to a writable
temporary location if the Python environment otherwise writes to the user home.
From the repository root:

```sh
python docs/research/current-schema-comparison/capture.py schema/checks/validate.py /tmp/rk-cue-study/captured
python docs/research/current-schema-comparison/capture.py schema/checks/expressions.py /tmp/rk-cue-study/captured
python docs/research/current-schema-comparison/capture.py schema/checks/formulations.py /tmp/rk-cue-study/captured
python docs/research/current-schema-comparison/capture.py schema/checks/models.py /tmp/rk-cue-study/captured
python docs/research/current-schema-comparison/capture.py schema/checks/specifications.py /tmp/rk-cue-study/captured
python docs/research/current-schema-comparison/capture.py schema/checks/runs.py /tmp/rk-cue-study/captured
python docs/research/current-schema-comparison/compare.py /tmp/rk-cue-study/captured /tmp/rk-cue-study/compared --cue /absolute/path/to/cue --bounded-raw
```

The comparator creates schemas and case files in the supplied output directory.
Use a fresh directory for each run. Its diagnostic limits, source fingerprints,
and dependency versions are part of the recorded experiment. Do not interpret
unmeasured inputs as successes or failures.
