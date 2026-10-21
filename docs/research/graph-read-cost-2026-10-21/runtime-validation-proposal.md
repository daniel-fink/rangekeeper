# Runtime validation cost: supported options and limits

Status: read-only proposal. No experiment or implementation is released here.
The generator proposal was declined; no schema or diagnostic change is proposed.
Scope B is active on other paths and must finish before any overlapping runtime
window. This review read dependency code and the retained scope A profile; it did
not run validation, tests or a new profile.

## Evidence and ranking

Evidence is `.runtime/graph-read-cost-2026-10-21/a-profile-primary-1/read.prof`,
`read.txt` and `source.json`. The profiled schema validation file has SHA-256
`f2e434b1522d08096e4a4f02455d395bc14f2aeb3c1435ce1629ded02af1a8f3`.
The package source paths below refer to that captured implementation; scope B
can add lines while this read-only proposal is prepared.

The profile records 7.119 seconds with profiling overhead. This table ranks
specific functions by **exclusive** time, not their overlapping cumulative time.
Rows are diagnostic leads, not quantities that an optimisation can remove in full.

| Function | Calls, including recursive calls | Exclusive seconds | Feasibility under the current constraints |
| --- | ---: | ---: | --- |
| jsonschema `Validator.descend` | 306,348 | 0.499163 | Highest lead, but no supported injection of an already prepared validator. Do not copy this framework method into RK. |
| RK `schema.runtime.copy_json` | 516,758 | 0.437715 | RK-owned strict-copy implementation can receive exact-builtin fast paths while retaining every check. Removing whole copies needs a separate ownership proof. |
| jsonschema `Validator.evolve` | 324,925 | 0.431987 | Most calls come from stock descend. Only a small explicit-evolve subset can plausibly be reused through supported composition. |
| jsonschema validator `__attrs_post_init__` | 324,926 | 0.212807 | Repeated keyword selection is a small supported preparation candidate; it does not remove instance construction. |
| RK `schema.index.walk` | 331,240 | 0.180249 | Two full traversals occur: identity indexing and recorded-unit checks. Preserve indexing; prune only unit-irrelevant branches with schema-derived reachability. |
| RK `Record._field` | 106,421 | 0.129809 | Includes field decoding during both walks. Reducing the second walk also reduces this work; do not count that benefit twice. |
| RK field `decode` | 137,361 | 0.087928 | Same overlap with field access and traversal. |
| RK `_freeze` | 175,343 | 0.079569 | Mandatory publication boundary; no removal proposed. |
| RK `_normalize` | 36,596 | 0.077065 | Mandatory canonical UUID behaviour; no removal proposed. |

Other notable exclusive costs are jsonschema type checking (0.274377 seconds),
UUID construction (0.191757), and built-in `isinstance` across the entire process
(0.257381). None is an independent savings estimate for one RK change.

Scope A's same-environment growth cold codec read remains 7.576713541 seconds,
with a 7.206845458-second warm read. These supported leads do not establish a
further reduction sufficient to meet Core's unchanged five-second request limit.

## Validator preparation: what the supported API can and cannot do

The installed jsonschema 4.26.0 source is under the isolated runtime environment.
Its `validators.py` documents `create(..., applicable_validators=...)` at lines
136–207, `evolve` at 339–347, and implements `descend` at 396–447. The supported
`Validator` protocol includes `evolve`, `iter_errors` and the keyword mapping.
The class explicitly warns against subclassing at lines 250–260.

Stock `descend` creates a subresource/resolver, evolves a validator, invokes the
keyword functions, fills missing error metadata, and prefixes both instance and
schema paths. It has no argument for an already prepared validator. Stock
`properties`, `items`, `allOf` and `anyOf` call this method directly. Preparing
more inline validators does not make those callers use them.

Do not override or copy `descend`, patch `_resolver`/`_validators`, subclass a
validator, or rewrite applicator callbacks to reproduce its error bookkeeping.
Using `extend` would not make those copied mechanics a supported dependency API.
Likewise, replacing inline schemas with synthetic references would be a schema
transformation with possible diagnostic effects, and is outside this proposal.

Two smaller, separately measurable preparation experiments are plausible:

1. **Prepared keyword selection.** In `schema/validation.py`, use the public
   `create` hook to retain an immutable, identity-keyed tuple of recognised
   keyword/value pairs for each private packaged subschema. Keep original order,
   original schema objects, the stock keyword functions, type checker, format
   checker, ID function and explicit Draft 2020-12 choice. Unknown schema objects
   use the ordinary selection path. Keep A's whole-graph scope/reference guards.
   A proposed helper is `_prepared_keyword_items`; it must contain no instance
   data. This avoids some repeated keyword filtering, but still constructs the
   evolved validator and runs every stock assertion. The dependency also repeats
   some checks after this hook, so lookup overhead can erase the saving.
2. **Prepared explicit evolution, leaving descend unchanged.** A proposed
   `_PreparedEvolution` composition adapter can wrap the validator argument
   passed to the original stock `if` callback. Its only specialised operation is
   `evolve(schema=...)`: for an exact known inline guard in A's single-scope graph,
   return a validator prepared once by the public `evolve`; delegate every other
   operation and evolution argument unchanged. Call the original public
   `VALIDATORS['if']` function, not a copied implementation. In particular its
   `descend` must remain the stock bound method. The same mechanism could later
   cover stock `not`/`oneOf`, but those are not material in these fixtures and
   should be excluded from the first experiment.

The second option is a composition hypothesis, not an established implementation
contract or performance result. It needs review of the exact stock callback and
protocol use. The adapter must never identify a target by schema equality alone:
resolution scope, root, dialect, checker and exact schema identity must match.
Any unknown form delegates unchanged; A's nested-resource/dialect guards still
fall back to the original validator. No validation result is cached. Every
`is_valid(instance)` still executes the stock guard against that input.

The retained callers identify only 30,160 direct `evolve` calls from `if_`, with
0.044165 exclusive seconds in evolve and 0.090792 cumulative seconds including
construction. Stock descend accounts for 294,661 other evolves. Thus the adapter
cannot be credited with the full 0.431987 seconds of evolve self time. Guard
validation and subsequent then/else descent remain. Its expected benefit is
small; it is not a plausible complete growth repair on the present evidence.

For either experiment, the proposed package scope is only
`src/rangekeeper/schema/validation.py`, with tests in
`src/tests/test_structural_validation_equivalence.py`. Require the existing
ordered public diagnostics and full nested error-context oracle, plus nested
`if`/`then`/`else`, `anyOf`, recursive records, date formats, dialect selection,
unknown references/scopes, repeated inputs and concurrent use. No change to
schema artifacts, error construction or branch order is permitted.

## Copying and semantic work within RK

These are separate amendments, not extensions of the validator experiment.

**First practical candidate: exact-builtin strict-copy fast paths.**
[`copy_json`](../../../src/rangekeeper/schema/runtime.py) at lines 44–66 checks
`Mapping` through the ABC path for every mapping and uses general sequence
checks. An exact `dict`/`list`/`tuple` branch can avoid general ABC dispatch for
ordinary parsed JSON, while preserving the current fallback for mapping and
sequence subclasses. It must retain encounter order, key checks, cycles,
nonfinite numbers, bool/int distinctions, signed zero, alias detachment and the
same error messages and order. This still visits and copies the whole input; it
is not a trust flag or a validation shortcut.

Proposed scope: only `schema/runtime.py:copy_json` and a focused new
`src/tests/test_json_copy_equivalence.py`, using the frozen original function as
an independent oracle. Include custom Mapping implementations, dict/list/tuple
subclasses, cycles through each container type, shared noncyclic aliases,
non-string keys, overflowed JSON numbers and opaque content. Do not infer the
saving from the process-wide `isinstance` total. This is the lowest-risk first
runtime experiment, with unknown benefit.

**Second candidate: avoid the full internal semantic export.**
`model/validation.py:_validate` line 83 calls `record.to_data()` after structural
validation, normalisation and freezing. That single call costs 0.312426 seconds
cumulative in the retained profile. This is distinct from the public export
contract; the public `to_data()` must continue to return a detached mutable copy.
A narrow experiment could let RK's internal, nonmutating `check_model` consume
the record's existing immutable mapping. No Core code gains private access.

This is not a one-line safe assumption. Every reached semantic helper must accept
Mapping/tuple representations and preserve its original diagnostics and order.
Do not change opaque content meaning or publish borrowed mutable input. Existing
`scope_for_model` already uses frozen RK mappings internally, but that is not proof
for all initial Model validation paths. If a helper needs a mutable list or plain
JSON representation, retain a local conversion or stop and propose its exact
additional scope. Do not broadly rewrite all semantics.

Initial proposed scope: `src/rangekeeper/model/validation.py:_validate` and a new
`src/tests/test_model_validation_equivalence.py`; any additional helper change
requires an identified amendment. Compare complete Models, errors and input
nonmutation for all existing reference, ownership, provenance, expression,
scenario, geometry, unit, identity and version families. Raw mapping entry points
still perform full structural validation first. The original check order and
publish-only-after-success rule stay unchanged.

**Third candidate: prune the second recorded-unit traversal.**
The profile's two `walk` callers are `RecordIndex.build` and
`recorded_unit_issues`, each visiting 34,334 records plus iterator termination.
Their walk subtrees cost 0.372519 and 0.380974 seconds cumulative respectively;
these are attribution figures, not additions to the table's self costs.
`recorded_unit_issues` at `model/validation.py:117` only acts on Domain, Measure,
Quantity, Flow and Value. Most provenance records cannot contribute a unit check.

Prepare immutable per-kind/per-field reachability from the packaged slot graph.
A proposed private `schema.index._walk_kinds` should visit only branches that can
reach one of those five kinds, using a fixed-point calculation for recursive
schema edges. It must preserve the exact sequence obtained by filtering today's
walk, including parent Value before nested Quantity, original paths, and union
fields. Prune a field only when no declared record option can reach a target.
Never treat opaque Claim content or UUID links as embedded records. Do not skip
all Provenance by name: schema-declared realization branches can contain units.

Proposed scope after B releases overlapping paths: `schema/index.py` for the
private selective walker and immutable reachability helper;
`model/validation.py:recorded_unit_issues` for consumption; and new
`src/tests/test_unit_validation_traversal.py`. Compare the selected sequence and
ordered unit issues with the exhaustive walker on the same immutable root,
including nested scenarios/formulations, anonymous records, invalid units,
multiple simultaneous failures, explicit null/empty fields and opaque apparent
records. Identity indexing and prerequisite reference checks still run in full.
No input-result cache or second all-record index is introduced.

## Lower-priority repeated construction and cold units

`model/scope.py:validate_values` reconstructs PropertyContent/Flow via generated
`from_data` at lines 230 and 244. The retained profile attributes 2,262 record
constructions from this function, costing only 0.099661 seconds cumulative;
these are not 2,262 additional full Model loads. Property content decoding then
exports those records, costing 0.012850 seconds cumulatively in `to_data`.
Do not cite the 4.438761-second cumulative total for all record construction as
avoidable repetition: it includes the one mandatory full Model construction.

A later experiment could use the same construction's existing immutable Value
records from its identity index, and pass their generated content/Flow children
to the unchanged semantic checks. Raw conformance envelopes must retain ordinary
construction. Exact scope would include `model/scope.py:validate_values`,
`model/formulation/preparation.py:prepare_formulations`, and
`model/validation.py:check_model`, plus the semantic equivalence test. This is
lower priority because its observed contribution is small and its routing crosses
three semantic operations. No unchecked raw record factory is proposed.

The codec also has two strict-copy passes: `io/json.py:_parse` and
`Record._set_data`. Their copy subtrees cost 0.255890 and 0.279653 seconds
cumulatively. The parse pass catches nonfinite results such as `1e999` and produces
DecodeError before Model construction. Deleting it would change the boundary.
Do not add a prepared/trusted flag or an alternate Core loader. A future
allocation-only parser experiment would need a shared strict JSON traversal that
checks without allocating, while retaining all parse errors and the ordinary
record constructor. Its exact scope would be `io/json.py:_parse`, a private
strict-traversal helper in `schema/runtime.py`, and codec/copy equivalence tests.
This is broader and less attractive than the builtin fast path.

The cold Pint registry is separate. `_registry` at `shared/units.py:20` has only
0.000326 seconds of exclusive time but 0.824340 cumulative seconds, including
Pint/NumPy imports and registry definition loading. Unit parsing/compatibility
cannot be removed. Warming the registry merely moves initial cost and does not
prove the cold-read requirement. No registry cache, dependency change, reduced
unit catalogue or environment prewarm is proposed here.

## Experiment and acceptance gates

The coordinator should select one exact experiment at a time. A proposed new
ignored helper is
`.runtime/graph-read-cost-2026-10-21/runtime-experiments/measure-runtime.py`, with
separate immutable baseline and candidate source inventories, fresh output names
and the unchanged primary/growth artifacts. It would run the existing public
codec and report cold/warm times, memory and exact results. A separate keyword
selection microbenchmark may use stock schemas and stock validation, but cannot
replace the codec measurement. Do not run any helper before a new release.

Freeze source before verification and avoid contention with B. Preserve A's
174-test result, original timings/profile and the declined generator proposal.
For each selected experiment, require independent exact acceptance, diagnostic,
identity, presence, provenance and nonmutation comparisons, then the repository's
applicable conformance, typing and installed-wheel checks. Keep all validation
stages and their order. A material isolated gain still needs a reviewed new wheel
and separate matched Core/browser verification under existing deadlines.

There is no demonstrated supported change that removes the main stock descent
cost while retaining its mechanics unchanged. If the small preparation options
and RK-owned copy/traversal experiments are insufficient, stop and keep the growth
gate open. A supported upstream jsonschema prepared-execution API would be a
separate dependency project and reviewed handoff; it is not an implied local
runtime override or an approved alternative validator.
