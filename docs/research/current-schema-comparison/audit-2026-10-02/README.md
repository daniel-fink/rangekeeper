# Independent audit of the CUE import probe

Date: 2026-10-02. Scope: review and reproduce the existing import-route probe,
then measure the cases its schema-level timeout cutoff left unmeasured.
This does not implement or evaluate the complete native CUE candidate.

## Conclusion

The original result is reproducible, including every case identity and outcome.
Its counts accurately describe the bounded experiment. They are not complete
corpus results or evidence that native CUE is unsuitable. The complete per-case
rerun strengthens the evidence that this unmodified JSON Schema import route
does not preserve the current structural contract.

| Outcome | Original and reproduced bounded probe | Every case attempted |
| --- | ---: | ---: |
| Same acceptance outcome | 476 | 572 |
| Different acceptance outcome | 21 | 28 |
| Validation exceeded five seconds | 3 | 106 |
| Unmeasured after first schema timeout | 208 | 0 |
| Non-finite input outside strict JSON | 5 | 7 |
| Total | 713 | 713 |

The full pass uses two worker processes and a separate five-second subprocess
deadline for every input. It never skips a case because another case timed out.
The bounded reproduction uses the original sequential script unchanged. These
are acceptance observations under specified limits, not a general performance
ranking. A timeout remains inconclusive.

## What was verified

- All 55 source fingerprints in the original manifest matched before the rerun.
- All seven schema suites passed again. Six instrumented suites recreated the
  same 713 unique schema/input pairs and 20 generated schema identities.
- Every baseline outcome was independently rechecked through uninstrumented
  `jsonschema` `iter_errors` with `FormatChecker`. All agreed. This addresses
  the capture wrapper's broad exception handler: no captured baseline rejection
  in this corpus depended on mistaking an unexpected exception for invalidity.
- The original bounded comparator reproduced every case's identity, schema,
  baseline, outcome, and CUE acceptance flag. Timing and diagnostic paths differ.
- The full pass retained return codes, complete stderr, and baseline rejection
  reasons. Completed CUE commands exited with 0 or 1; no other exit codes were
  observed. Exit 1 alone does not distinguish intended validation rejection from
  an evaluation problem.

## Findings

**The timeout cutoff hid useful evidence.** Of the 208 formerly skipped pairs,
96 matched, seven differed, 103 timed out, and two contained non-finite numbers.
The original five non-JSON cases were consequently a measured subset, not the
total present in the corpus. All seven non-finite inputs pass structural
validation; finite-content enforcement belongs to additional checks. They are
excluded from CUE comparison because they cannot be serialized as strict JSON.

**Sixteen invalid inputs are accepted by the imported schema.** All sixteen
baseline rejection reasons concern the same code/name pattern:
`^\S(?:[\s\S]*\S)?$(?![\s\S])`. Imported Entity, Formulation, Binding, and
Constraint declarations lose that restriction. An isolated import reproduces
the problem: empty, blank, padded, and newline-terminated strings are accepted.
The import exits successfully without reporting the dropped restriction.

CUE uses RE2 regular expressions, which exclude lookahead. A small native CUE
control using `^\S(?:[\s\S]*\S)?$` correctly classifies the seven tested ASCII
strings. This demonstrates that this specific requirement can be expressed
directly in CUE; it is not proof of complete Unicode or whole-contract parity.
See the [CUE language specification](https://cuelang.org/docs/reference/spec/)
and [RE2 syntax](https://github.com/google/re2/wiki/Syntax).

**Twelve accepted inputs are not accepted by the imported schema:** seven Query
records and five Expressions. The original bounded pass exposed seven and one,
respectively. Retained diagnostics include imported matching constraints and
structural cycles. A reduced forbidden-optional-field control behaved correctly;
it does not explain away the failures in the full Query/Expression schemas.

**Matching rejection is weaker than semantic parity.** There are 309 matching
acceptances and 263 matching non-acceptances. Of the latter, 27 contain CUE cycle
diagnostics: 19 Expression, six Domain, and two Provenance pairs. Some diagnostics
may coexist with legitimate validation errors. They are flagged for inspection,
not counted as proven false rejections or equivalent rejection reasons.

**Timeouts concentrate in three schemas:** Model (68), Formulation (32), and
Expression (6). Seventy timed-out inputs are structurally valid under the current
validator; 36 are invalid. They establish neither acceptance nor rejection.

All 28 differences reproduced in a subsequent sequential confirmation pass.
One valid timed-out case per affected schema was then retried sequentially with
a 30-second limit. The Model and Formulation examples still exceeded that limit;
the Expression example succeeded in 11.25 seconds. This directly demonstrates
why the five-second timeouts must not be described as rejected inputs. The table
above remains the complete five-second experiment, not a mixture of time budgets.

## Environment and reproduction

CUE is the same official macOS arm64 0.17.1 release, verified against archive
SHA256 `64921403f012a97f89494c03605db2fbf7d9daa77dc2631819ac4406cb2e8074`.
LinkML and linkml-runtime are 1.11.1; jsonschema is 4.26.0. Python is 3.10.19,
whereas the prior run recorded 3.10.21. The installed uv could not provision
3.10.21. The original environment was not transitively locked; this rerun's
complete package freeze is retained. Exact corpus/schema identities and outcomes
reproduced despite that environment difference.

The invocation is appropriate: imported constraints are placed at the root and
`cue vet -c schema.cue case.json` checks each input against that root. This agrees
with the pinned executable's help and the official
[import](https://cuelang.org/docs/reference/command/cue-help-import/) and
[vet](https://cuelang.org/docs/reference/command/cue-help-vet/) documentation.

The [evidence archive](evidence.tar.gz) contains captured inputs (including the
Python JSON encoder's nonstandard non-finite literals), generated JSON/CUE
schemas, individual strict-JSON case files, bounded and full results, baseline
logs, isolated controls, confirmation attempts, the dependency freeze, and exact
executed script snapshots. `manifest.json` inside the archive fingerprints its
contents. [summary.json](summary.json) provides the reviewable aggregate result.

The executed audit scripts are experiment snapshots with explicit local paths,
not library tooling. To reproduce, recreate the temporary environment and paths
recorded in those scripts (or consistently adapt them), use the existing README's
capture commands, run the original bounded comparator, then `full_audit.py`.
`minimal.py` performs the isolated controls and `confirm.py` repeats all
differences sequentially plus one valid timeout case per affected schema with a
30-second limit. Use a fresh output directory; do not overwrite retained evidence.

## Implication for continuation

**Subsequent decision, 2026-10-02:** Daniel chose to retain LinkML and proceed
without completing the native CUE comparison. The [decision record](../DECISION.md)
supersedes the audit-time continuation recommendation below. The measured evidence
and its limits remain unchanged.

At audit completion, the recommendation was to retain LinkML provisionally and
continue the native comparison. That recommendation was superseded by Daniel's
subsequent decision to retain LinkML for this stage. If CUE is explicitly
reconsidered later, these import failures remain regression cases; matching exit
statuses alone cannot establish equivalent diagnostics. No authoritative schema,
library runtime, or project dependency was changed by this audit.
