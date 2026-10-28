# Generated records and domain methods

LinkML owns each record's fields, types, inheritance and wire format. The Python
generator emits one immutable class for each concrete schema class. It also emits
typed constructors, properties, `replace` methods and docstrings from schema
descriptions. Opaque `Content` remains JSON data, outside schema-directed declaration
traversal.

Use the [domain API](model.md) for complete Model and Specification revisions,
[Run and storage](run-and-storage.md) for execution evidence and persistence, and the
[upgrade guide](../guides/upgrading.md) when migrating callers. This page defines
the shared record layer and its method ownership.

## Ownership

| Location | Responsibility |
| --- | --- |
| `schema/*.yaml` | Authoritative field, enum, inheritance and description definitions |
| `tools/schema/generate.py` | Explicit constructors, properties, typed replacement signatures and the owner table |
| `rangekeeper/schema/enums.py` | Canonical plain Enum classes; typed fields decode members and wire data retains strings |
| `rangekeeper/schema/records.py` | Data-only immutable classes and the owner module of each value type |
| `rangekeeper/schema/kinds.py` | The kind registry: the owner class that each kind constructs and decodes to |
| `rangekeeper/schema/runtime.py` | Shared field encoding, strict JSON copying, freezing, replacement, field presence and schema equivalence |
| `rangekeeper/flow`, `rangekeeper/duration`, `rangekeeper/finance/_distribution.py` | Owner subclasses with the methods of Flow and Movement, Period and Span, and Distribution; no field declarations |
| `rangekeeper/schema/{schema,slots,manifest}.json` | Structural checks, a packaged copy of the slot metadata and reproducible generation fingerprints |
| `model`, `specification`, `run` | Document-wide validation, references and revision rules |
| `flow`, `finance` | Operations that combine records or require an explicit financial or temporal interpretation |

Generated records contain data only ([ADR-011](../decisions/011-records-and-validation.md)).
The owner of a value type subclasses its generated record, for example
`class Flow(records.Flow)` in `flow`, and registers it with
`rangekeeper.schema.kinds.register`. Direct construction (also of the generated
class), `from_data`, `from_json`, nested property decoding and traversal
therefore return the owner class with its methods. The generated `_OWNERS` table
names each owner module, so a decode loads the owner on first use. An owner keeps
`__slots__ = ()` and the generated constructor, and does not shadow a field.
Schema inheritance remains intact: `Assembly` is an `Entity`; `Span` is a
`Period`. Workflow computation fingerprints include the owner modules, so changes
to these methods affect recorded computation identity.

The generator selects the encoder and decoder of each field and gives each class
its slot metadata (`_SLOTS`). The runtime does not read `slots.json`. A record
decodes each child record field once and keeps the result, so `flow.movements` is
the same tuple at each read.

Handwritten methods use local imports for schema constructors and optional
numerical libraries. Importing records does not load a solver, dataframe, plotting
library or random generator. SciPy and NumPy load when a Distribution calculation
needs them. Polars loads when an alignment or resampling operation needs it.

## Construction and replacement

```python
from datetime import date
from uuid import uuid4
from rangekeeper.flow import Flow, Movement

movement = Movement(id=uuid4(), key="delivery", date=date(2026, 1, 1))
assert not movement.has_field("magnitude")
resolved = movement.replace(magnitude=10, claims=())
assert resolved.number == 10.0
assert movement.magnitude is None
flow = Flow(units="m", movements=(resolved,)).check(resolved=True)
assert flow.total().magnitude == 10
```

Validation runs in tiers ([ADR-011](../decisions/011-records-and-validation.md#when-validation-runs)):

| Tier | Where | What |
| --- | --- | --- |
| Node checks | Typed constructors and `replace` | The record's own fields and class rules, generated from the JSON Schema. Child records are already checked |
| Structural | `from_data`, `from_json`, the codecs (`rk.io.json`, `rk.io.yaml`) and `DirectoryStore` reads | jsonschema over the whole tree |
| Semantic | `Model`, `Specification` and `Run` construction, so `create`, `revise` and `from_data`; composition before execution; Run publication | Document rules, references, units and dimensions |

Record data (a mapping) passed to a typed constructor for a record field is
untrusted and gets the structural tier. Generated signatures
let type checkers reject unknown fields, wrong record types and invalid enum
values. Typed constructors and `replace` require canonical Enum members; raw wire
strings belong at `from_data`/`from_json`. Runtime checks reject nonfinite numbers, cyclic data and invalid field
shapes. Python `bool` is a subtype of `int`, but runtime numerical fields still
reject it.

`replace` returns a new record. It uses the same field encoders as construction.
It checks only this record: its changed fields and its class rules. Unchanged
fields and child records keep their frozen, already checked content, so a
replacement costs about the same for a Flow of 12 or 120 Movements. The checks
are generated from the JSON Schema; a contract test keeps them equal to
jsonschema for every class. Record data (a mapping) passed for a record field is
validated in full. An omitted argument, or `UNSET`, retains the old field's
presence and value. `rangekeeper.OMIT` removes an optional field. Explicit `None`
records null where the schema permits it; `()` records an empty collection. A
no-argument replacement preserves omitted, null and empty fields exactly.

Replacement does not mint a document revision or certify document-wide semantics.
Use `Model.revise` or `Specification.revise` to check lineage and meaningful change.
Both facades use the same revision comparison rules, but retain their own domain
validation. A new UUID alone is not a meaningful revision.

`to_data` returns detached JSON-compatible data. Dates use ISO strings on the wire
and `datetime.date` in typed fields. Datetimes are not truncated into dates. Source
fields that also permit timestamp strings retain those strings. UUID conversion
applies only to schema-declared references, never to opaque content.

`repr` gives a one-line summary: scalar fields, `{...}` for a child record and
`[n]` for a collection. Use `to_data` for the complete content.

Equality and revision comparison use the [identity contract](identity.md#comparison-rules).
Neither operation converts units.

## Method contracts

```text
Movement
  number -> float                         finite magnitude; unresolved raises
  coordinate -> tuple                     alignment coordinate, independent of UUID
  resolve(*, timing=None) -> date          recorded date, or explicit period rule
  replace(*, ...) -> Movement              typed, immutable structural replacement

Flow
  clone() -> Flow                         independent Movement UUIDs
  from_events(dates, magnitudes, *, units, keys=None)
  from_periods(periods, magnitudes, *, units, dates=None)
  check(*, resolved=False, units=None) -> Flow
  convert(*, units, unit_system=None) / scale(factor) / negate()
  total(*, missing=MissingValueHandling.ERROR) -> Quantity | None
  trim(*, start, end) / clean(*, remove_zeroes=False)
  difference(*, initial=None) / collapse(*, on=None, timing=None, missing=MissingValueHandling.ERROR)
  extent(*, include_zeroes=False) / trim_empty()
  display(*, name=None, transpose=False, precision=2) -> StreamTable

Period (also inherited by Span)
  check() -> Period
  resolve(*, timing) -> date

Span
  from_duration(*, name, start, frequency, count, month_roll=None) -> Span
  periods(frequency, *, include_partial=False, month_roll=None) -> tuple[Period, ...]

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

Periods use `[start, end)`: `start` is included and `end` is excluded. Movement dates can record independent payment or
observation dates outside their coverage period. Recorded dates take precedence;
undated period movements require `PeriodTiming.FIRST`, `LAST` or `END` when resolving a date.
Flows carry units and coordinates. The calling model determines whether operations
such as summation or integration express the intended quantity.

`Flow.display()` and notebook rich display use the shared Stream table renderer.
The optional `name` labels the table only; it does not add a field to the Flow.
See [table display](tables.md) for formatting and missing states.

`Distribution.cdf` is the cumulative distribution function. `mass` returns interval
probabilities. Samples use the declared units and advance only the supplied NumPy
generator. Point masses retain the existing deterministic sampling convention.

## Operations across records

Use [calculations](calculations.md) for alignment, aggregation, accounts and
financial valuation; [Model](model.md) for document lookup and revision;
and [Specification](specification.md) for additive composition.
These operations have no single nested record owner. They do not add another
field schema or change a record's intrinsic methods.

## Generation and verification

Generated files must not be edited by hand. Change the LinkML source and run the
[schema generation procedure](../contributing/schema.md). LinkML is not a runtime dependency.
The [verification procedure](../contributing/verification.md) covers native loading, typed
constructors, deliberate rejection cases, installed wheels and lazy imports.
