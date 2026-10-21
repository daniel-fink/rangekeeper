# Further validation cost: generator review

Status: read-only analysis and a possible new amendment. This document releases
no implementation, schema generation, tests, profiling or dependency work.
Scope A remains separate. Scope B's public lookup work does not change these
findings.

## Finding

There are provable generated redundancies, but the evidence does not establish a
generator change large enough to meet the five-second growth read requirement.
Do not treat the candidates below as a complete performance repair. If exact
ordered diagnostics must remain unchanged, most of these transformations need a
new explicit diagnostic-contract decision before implementation.

The parent measured scope A's growth codec read at 7.576713541 seconds cold and
7.206845458 seconds warm, against approximately 9.491 and 9.232 seconds for the
same-environment baseline. This is useful improvement of about 20–22%, while the
initial read remains outside five seconds before Core's other request work. A
further reduction of more than 34% of the measured cold codec time would be
needed just to get that codec call below five seconds.

The retained scope A primary profile is
`.runtime/graph-read-cost-2026-10-21/a-profile-primary-1/read.txt`, with its `.prof`
and `source.json`. It records 7.119 seconds with profiling overhead. Structural
validation is 3.745 seconds cumulative; `anyOf` is 1.539, validator `evolve` is
0.908, `if_` is 0.835, `copy_json` is 0.860 and Model semantic validation is 1.976.
The semantic figure includes the cold unit registry's 0.824 seconds. These
figures overlap. They must not be added, converted into service timings, or used
to claim the savings from a specific generated rule.

The profiled production file is `schema/validation.py` SHA-256
`f2e434b1522d08096e4a4f02455d395bc14f2aeb3c1435ce1629ded02af1a8f3`.
The packaged schema is SHA-256
`0556785eeb9feb50dec695034ac40240ad925cd9747a2b76875c42a3e3b8f53f`.
No new performance test or profile was run for this review.

## Existing rule and remaining forms

[`simplify_conjunctions`](../../../tools/schema/generate.py) at lines 83–101
implements `A AND (A OR B) = A` when A is an identical direct `$ref` or an
`allOf` member. It does not remove a repeated direct `$ref` from `allOf`, or
recognise equivalent literal sibling constraints. The generator applies the
rule at line 140, then checks the resulting schema at line 141.

A static scan of the packaged JSON Schema found these forms. Counts describe
schema locations, not executions or measured savings.

| Form | Locations | Relevance to the frozen Models |
| --- | ---: | --- |
| Direct `$ref` plus identical single `allOf` member | 11 | Mostly expression, function, query, Specification and Run fields. Model Metadata occurs once. |
| Sibling assertion keys exactly include an `anyOf` branch | 26 | Mostly expression, function, query, Specification and Run fields. These include all 16 single-member `anyOf` cases. |
| One-reference `allOf` wrapper with no conflicting sibling key | 17 | Mostly expression/query fields. Model has three section wrappers. |
| Duplicate `anyOf` members | 1 | Fact target has five identical UUID alternatives. Valid targets already stop at the first successful branch. |
| Broad Content reference beside a narrower union | 2 | Claim source items and Fact targets occur throughout both fixtures. |
| Explicit `additionalProperties: true` | 1 | Content; it imposes no rejection in the current schema but incurs keyword dispatch and extra-property scanning. |

The frozen Models have no system Formulations or definition Functions. General
expression simplification can be useful, including repeated recursive Expression
references under Argument and Selection, but it does not address this fixture's
load cost. Deduplicating Fact target alternatives alone saves no successful
branch checks because jsonschema's `anyOf` stops at the first success.

## Narrow candidate and proof obligations

The relevant generated locations are in
[`schema.json`](../../../src/rangekeeper/schema/schema.json):

- Claim sources, lines 370–383: each item requires Content and also Location or a
  UUID string. Location requires an object. Both permitted alternatives therefore
  imply Content's type restriction.
- Fact target, lines 1669–1693: every alternative is the same UUID string schema,
  which also implies Content.
- Content, lines 525–535: this is **not an empty schema**. It permits null,
  boolean, object, number and string, and rejects arrays. Its explicit
  `additionalProperties: true` does not restrict object fields.

Thus removing only the Content reference at the two union sites preserves their
accepted JSON language. Do not remove Content from Claim.content: that would
admit arrays previously rejected by structural validation. Do not reorder the
Claim source alternatives or infer semantic reference validity from UUID shape.

A static read of the unchanged fixtures gives:

| Input | Claim source items | Fact targets | Redundant Content checks at these sites |
| --- | ---: | ---: | ---: |
| Primary | 11,310 | 3,770 | 15,080 |
| Growth | 30,720 | 10,240 | 40,960 |

These are additional checks on existing data, not additional records. There are
also 11,310 and 30,720 Claim content values, whose Content constraint must remain.
The data and provenance density must not change.

Removing Content's explicit `additionalProperties: true` is a smaller possible
cleanup. In this packaged graph there are no `unevaluatedProperties` or
`unevaluatedItems` consumers. A generic generator rule must nevertheless account
for those annotations: removing an apparently vacuous applicator is not safe in
an arbitrary schema that relies on evaluated-property tracking. Restrict a proof
to this closed, inspected form and fail closed on unsupported forms.

These changes remove dispatch and shallow type checks. They do not remove the
full record traversal, most property validation, Claim conditional requirements,
JSON copies, UUID normalisation, identity indexing, recorded-unit traversal or
semantic provenance checks. The retained profile does not attribute enough cost
to these exact sites to predict a useful number of seconds. Expected benefit is
incremental; there is no evidence that it closes the remaining growth gap.

## Diagnostic and verification boundary

Acceptance equivalence is not diagnostic equivalence. For example, an array at
Fact.target currently produces Content's type error as well as the union error.
Removing the redundant reference removes the former. Deduplicating alternatives
changes nested error multiplicity; removing repeated conjunctions changes error
counts and schema paths. Flattening an applicator changes schema paths even when
public issue paths remain the same.

The current
[`verify_simplification.py`](../../../tools/schema/verify_simplification.py)
compares `is_valid` results at lines 74–87. It does not compare ordered public
issues or nested error contexts. Scope A's independent ordered-error tests must
remain intact; running them only against the newly generated schema would not
compare old and new diagnostic contracts.

If the coordinator wants to evaluate this candidate, first release a separate,
exact generator experiment. Its minimal source scope is:

- `tools/schema/generate.py`, with only proved, closed-form simplifications;
- `tools/schema/verify_simplification.py` and focused simplification tests, with
  the old packaged schema retained as an independent oracle;
- generated `src/rangekeeper/schema/schema.json` and `manifest.json` through the
  normal generator; other Python generated outputs must remain byte-equal unless
  a separately reviewed reason is found;
- generated `src/grasshopper/Model/Generated/schema.json` and `manifest.json`
  through the C# generator, which copies and fingerprints the Python schema;
- the dated evidence report and its research-index link.

No YAML field, schema version, runtime validation bypass, dependency, model data,
service deadline or alternative validator is part of that proposed experiment.
A new schema version cannot be ruled out merely because accepted JSON is equal;
first review whether the intended diagnostic change affects the declared public
contract. Do not silently broaden into general implication checking.

Compare old/new accepted results across all definitions and canonical examples,
plus nested invalid arrays, nulls, booleans, UUIDs, locations, recursive records
and all semantic rejection families. Record each intended diagnostic difference
explicitly. Run the required seven conformance suites, generation and typing
checks, C# checks and installed-wheel verification if the candidate proceeds.
Measure the unchanged primary and growth cold codec reads serially against the
frozen A checkpoint in the same environment. Keep failed and insufficient results.
Only a material observed improvement can justify taking this candidate into a new
reviewed wheel and the separate Core dependency handoff.

If exact ordered diagnostics are required without amendment, defer the redundant
constraint removals. The small explicit-true cleanup alone has no measured basis
as a growth deadline repair. The current evidence supports retaining A as an
incremental improvement and keeping the capacity gate open.
