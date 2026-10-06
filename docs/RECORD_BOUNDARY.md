# Generated records and domain methods

LinkML owns each record's fields, types, inheritance and wire format. The Python
generator emits one immutable class for each concrete schema class. It also emits
typed constructors, properties, `replace` methods and docstrings from schema
descriptions. The bundle contains 72 schema classes: 71 record classes and opaque
`Content`, represented as JSON data.

Use the [domain API](DOMAIN_CORE.md) for complete Model and Specification revisions,
[Run and storage](RUN_AND_STORAGE.md) for execution evidence and persistence, and the
[upgrade guide](LEGACY_UPGRADE_GUIDE.md) when migrating callers. This page defines
the shared record layer and its method ownership.

## Ownership

| Location | Responsibility |
| --- | --- |
| `schema/*.yaml` | Authoritative field, enum, inheritance and description definitions |
| `tools/schema/generate.py` | Explicit constructors, properties, typed replacement signatures and selected behaviour inheritance |
| `rangekeeper/_schema/records.py` | Canonical immutable classes, including the registry used for nested decoding |
| `rangekeeper/_records.py` | Shared field encoding, strict JSON copying, freezing, replacement and field presence |
| `rangekeeper/_behaviors/` | Handwritten methods for Flow, Movement, Period and Distribution; no field declarations |
| `rangekeeper/_schema/{schema,slots,manifest}.json` | Structural checks, conversion metadata and reproducible generation fingerprints |
| `model`, `specification`, `run` | Document-wide validation, references and revision rules |
| `calculations` | Operations that combine records or require an explicit financial or temporal interpretation |

The generator explicitly attaches field-free behaviour mixins. It does not patch
classes after import. Direct construction, `from_data`, `from_json` and nested
property decoding therefore return the same class with the same methods. Schema
inheritance remains intact: `Assembly` is an `Entity`; `Span` is a `Period`.
Workflow computation fingerprints include the behaviour modules, so changes to
these methods affect recorded computation identity.

Handwritten methods use local imports for schema constructors and optional
numerical libraries. Importing records does not load a solver, dataframe, plotting
library or random generator. SciPy and NumPy load when a Distribution calculation
needs them. Polars loads when an alignment or resampling operation needs it.

## Construction and replacement

```python
from datetime import date
from rangekeeper.model.flow import Flow, Movement

movement = Movement(key="delivery", date=date(2026, 1, 1))
assert not movement.has_field("magnitude")
resolved = movement.replace(magnitude=10, claims=())
assert resolved.number == 10.0
assert movement.magnitude is None
flow = Flow(units="m", movements=(resolved,)).check(resolved=True)
assert flow.total().magnitude == 10
```

Constructors, `from_data` and `replace` validate structure. Generated signatures
let type checkers reject unknown fields, wrong record types and invalid enum
values. Runtime checks reject nonfinite numbers, cyclic data and invalid field
shapes. Python `bool` is a subtype of `int`, but runtime numerical fields still
reject it.

`replace` returns a new record. It uses the same field encoder and structural
validation as construction. An omitted argument, or `UNSET`, retains the old
field's presence and value. Explicit `None` records null where the schema permits
it; `()` records an empty collection. A no-argument replacement preserves omitted,
null and empty fields exactly. Replacement does not remove a present field;
construct from an explicitly edited data mapping when that is required.

Replacement does not mint a document revision or certify document-wide semantics.
Use `Model.revise` or `Specification.revise` to check lineage and meaningful change.
Both facades use the same revision comparison rules, but retain their own domain
validation. A new UUID alone is not a meaningful revision.

`to_data` returns detached JSON-compatible data. Dates use ISO strings on the wire
and `datetime.date` in typed fields. Datetimes are not truncated into dates. Source
fields that also permit timestamp strings retain those strings. UUID conversion
applies only to schema-declared references, never to opaque content.

## Method contracts

```text
Movement
  number -> float                         finite magnitude; unresolved raises
  coordinate -> tuple                     alignment identity
  resolve(*, timing=None) -> date          recorded date, or explicit period rule
  replace(*, ...) -> Movement              typed, immutable structural replacement

Flow
  from_events(dates, magnitudes, *, units, keys=None)
  from_periods(periods, magnitudes, *, units, dates=None)
  check(*, resolved=False, units=None) -> Flow
  convert(*, units, unit_system=None) / scale(factor) / negate()
  total(*, missing="error") -> Quantity | None
  trim(*, start, end) / clean(*, remove_zeroes=False)
  difference(*, initial=None) / collapse(*, on=None, timing=None, missing="error")
  extent(*, include_zeroes=False) / trim_empty()

Period (also inherited by Span)
  check() -> Period
  resolve(*, timing) -> date

Distribution
  uniform(...) / triangular(...) / pert(...) / symmetric(...)
  check() -> Distribution
  sample(*, size, generator) -> tuple[float, ...]
  cdf(values) / mass(boundaries) -> tuple[float, ...]
```

`check` raises on invalid content and otherwise returns the same object. It does
not repair data. `Flow.check(resolved=True)` additionally requires a finite number
for every Movement. `Movement.number` provides a nonoptional float for arithmetic.
`Flow.clean` is a transformation: it removes unresolved movements and, when
requested, zeroes. It is not a validation step.

Periods use `[start, end)`. Movement dates can record independent payment or
observation dates outside their coverage period. Recorded dates take precedence;
undated period movements require `start`, `last_day` or `end` when resolving a date.
Flows carry units and coordinates. The calling model determines whether operations
such as summation or integration express the intended quantity.

`Distribution.cdf` is the cumulative distribution function. `mass` returns interval
probabilities. Samples use the declared units and advance only the supplied NumPy
generator. Point masses retain the existing deterministic sampling convention.

## Operations across records

`series.align(flows, join=..., missing=...)` returns `Alignment`, which retains
aligned Flows, original known-value coverage and the selected missing policy.
`Alignment.reduce(reducer="sum" | "min" | "max", units=...)` shares unit conversion,
Claim collection and coverage calculation. `series.aggregate(...)` combines these
two steps. Each reduction returns `Aggregation(flow, coverage)`.

Exact alignment is the default. Union and intersection are explicit. Zero filling
applies to absent coordinates; an explicitly unresolved movement remains unresolved.
Skip can reduce a partly known group; an entirely unknown group remains unresolved.
Coverage reports the original known fraction, including after zero filling.

`series.multiply`, `integrate` and `resample` retain explicit calculation contracts.
`Account.calculate(...)` returns opening, closing, overdraft and interest Flows.
Financial valuation remains in `calculations.financial`, with explicit timing and
PyXIRR conventions. Calendar grids remain in `duration.period`.

A Model facade builds its ownership index once and reuses it for validation and
lookup. Scalar execution composes a Specification once, then passes that exact
Composition to preparation. These changes avoid repeated work without caching
across revisions or skipping validation.

## Generation and verification

Use the pinned `tools/schema/requirements.txt` environment. Run
`python tools/schema/generate.py`, then `python tools/schema/generate.py --check`.
Generated files must not be edited by hand. LinkML is not a runtime dependency.
Run `tools/schema/typecheck.py` with mypy 1.18.2 for valid consumers and deliberate
static rejection cases. `tools/schema/verify_install.py` checks a wheel outside the
checkout, including lazy imports and nested record behaviour.

The stock LinkML 1.11.1 loader still cannot load a single-field terminal policy
Action. Production immutable records and codecs handle that contract. The
[recorded native-tooling probe](research/full-migration/turn2/final-notebooks/native-boundary.json)
documents this separate limitation.
