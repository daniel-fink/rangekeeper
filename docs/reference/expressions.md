# Expression, Function, Query, and Constraint contract

This guide specifies representations and meaning. Structural and bounded semantic
checks enforce this contract. The [executor](execution.md) implements the
documented affine subset; representation alone does not promise execution support.

Write an equation as text on an entity handle:
`project.equations("noi = coverage * debt_service")` ([equation text](#equation-text)),
or in Python with `rx` ([the Python form](#the-python-form-rx)):
`project.equations(noi == coverage * debt_service)`. Both make the same records
from one [registry of equation functions](#equation-functions).

`rangekeeper.model.expression.authoring` has passive literal, reference and
operator constructors for records. It is provisional, not part of the 1.0 API
([#309](https://github.com/daniel-fink/rangekeeper/issues/309)): write equations
as text or with `rx` instead. `rangekeeper.model.formulation` owns equation
builders; these builders return declarations and do not read recorded amounts
or solve them.

## Composition and identity

An Expression is passive mathematical syntax. Each node has a stable UUID and
exactly one content variant. Nested nodes retain their own identities. References
identify Values within the applicable Model or composed Specification scope, independently of display
names and recorded amounts. Fixed and unknown roles belong to a Specification.
`ExpressionKind` distinguishes syntax forms and `Operator` names their
operators. Helper records use `Call`, `Parameter`, `Filter`, `Criterion`,
`ValueTest` and `Projection`; their fields refer to the relevant classes and
categorical enums. A query's `Filter` follows the
[declarative filter rules](system.md#declarative-filters): Classifications include
their sub-types unless `exclusive`, and a candidate with a missing tested value
does not pass.

| Form | Serialized kind and content |
| --- | --- |
| Numerical literal | `quantity`: embedded Quantity with magnitude and explicit units |
| Boolean literal | `boolean`: true or false |
| Date literal | `date`, with `date`: an ISO calendar date, such as `2027-01-01`; or with `never`: `never`, the event does not happen |
| Value reference | `reference`: target Reference (Value or Movement UUID) |
| Unary operation | `unary`: operator and one `operand` |
| Binary operation | `binary`: operator and two ordered `operands` |
| Function call | `call`: Function UUID, positional arguments, named arguments |
| Member or index selection | `selection`: base Expression and a typed selector |
| Graph query | `query`: scope, traversal, filter, projection, duplicate handling |

Arity follows the operation form. Negation and Boolean negation are unary;
arithmetic, comparisons, conjunction, and disjunction are binary. Longer operator
chains nest. Functions have their own signatures; aggregations accept collections
rather than an implicit variable number of scalar arguments.

Numerical literals embed the shared `Quantity` type from `measure.yaml`. Their
units are explicit, including `dimensionless` for unitless content. They do not
carry a Measure reference. A Measure defines domain meaning and canonical units;
a Quantity supplies magnitude and units. The containing Expression owns identity.
Zero and false are meaningful content. Missing or
null literal content is invalid. A reference to an unresolved Value is valid.
Optional list fields may be absent, null, or empty to denote no entries; canonical codecs preserve those distinctions. Required operation content cannot be null or empty.

String literal nodes are deferred until a concrete operation requires them.
This does not remove string result domains: a reference, selection, or call can
return such content under its declared contract. Selector names and
characteristic keys are schema fields, not string literal expressions.

## Equation text

An entity handle takes equations as text, one or several in a call
([Model reference](model.md#make-and-change-a-model)):

```python
project.equations(
    "total_cost = land_cost + works_cost",
    "noi = coverage * debt_service",
)
```

Equation text is the Python form of an equation inside a string, with four
changes ([ADR-015](../decisions/015-authoring.md),
[D32](../../examples/walkthrough/proposed/README.md#decisions)):

- `=` is equality. Python's `==` is an error that suggests `=`. A
  [rule's condition](market-paths-and-rules.md#declare-a-rule) is the reverse: `=`
  states an equation and `==` tests a value, so a condition writes `==`.
- `and`, `or` and `not` are the logical operators. `&`, `|` and `~` are errors
  that suggest them; `^` suggests `**`.
- A number followed by unit words is a quantity literal, with no quotes.
- `NEVER` is the constant `rk.duration.NEVER`.

A calendar date keeps its Python spelling, `date(2027, 1, 1)`: three whole
numbers, the year, the month and the day. It is a date literal, not a function.

The text becomes the Expression records of the [table above](#composition-and-identity),
with a new UUID for each node. They are the records that the record constructors
make: `"value = noi / cap_rate"` gives
`equal(reference(value), divide(reference(noi), reference(cap_rate)))`.

| Form | Text | Records |
| --- | --- | --- |
| Name | `land_cost` | `reference` to the Value with this key on the same entity, or to the value that an equation defines ([values that equations define](model.md#values-that-equations-define)) |
| Dotted name | `building_a.income` | `reference` to the Value `income` of the entity with the code `building_a` |
| Quantity literal | `0 AUD`, `2 years`, `7 % pa`, `750 AUD per sqm pa` | `quantity`: the Quantity that `rk.Quantity(text=...)` makes from the same text. A bare number, such as `1`, is `dimensionless` |
| Constant | `True`, `False`, `NEVER` | `boolean`; `never` |
| Date literal | `date(2027, 1, 1)` | `date` |
| Negation, `not` | `-a`, `not a` | `unary` |
| Arithmetic | `a + b`, `a - b`, `a * b`, `a / b`, `a ** b` | `binary` |
| Comparison | `a = b`, `a != b`, `a < b`, `a <= b`, `a > b`, `a >= b` | `binary`, Boolean |
| Logic | `a and b`, `a or b` | `binary`, Boolean |
| Brackets | `(a + b) * c` | No node of their own |

Operators bind as in Python. A higher level binds tighter:

| Level | Operators | Grouping |
| --- | --- | --- |
| 1 | `or` | Left |
| 2 | `and` | Left |
| 3 | `not` | — |
| 4 | `=`, `!=`, `<`, `<=`, `>`, `>=` | None: `a < b < c` is an error; write `a < b and b < c` |
| 5 | `+`, `-` | Left: `a - b - c` is `(a - b) - c` |
| 6 | `*`, `/` | Left |
| 7 | Negation `-` | — |
| 8 | `**` | Right: `a ** b ** c` is `a ** (b ** c)`, and `-a ** 2` is `-(a ** 2)` |

`rangekeeper.model.expression.text.render` writes records as equation text with
the fewest brackets that keep the meaning. `model.equations` gives the text of
each equation of a revision, with its key ([equations of a
revision](model.md#equations-of-a-revision)). Text that an entity handle reads
reads back to the same records. Diagnostics use the same text: an unsupported
equation in a solve is `"noi = coverage * debt_service"`. A date literal is
written `date(2027, 1, 1)` and NEVER is written `NEVER`, so both read back. A
date that is not a calendar date, such as `date(2027, 13, 1)`, or another form,
such as `date(2027, 1)`, raises `EquationError` with `EQUATION_SYNTAX`.

**Quantity literals.** A literal is a number and the words of its units, joined
by spaces: names, `%` and `per`. The literal ends at the first token that is not
a unit word. So `*` and `/` are never part of a literal: `1 year * rate` is
`(1 year) * rate`, and `1 AUD / year` divides by a value with the key `year`.
Brackets make a long literal easier to read: `nla * (750 AUD per sqm pa)`. Unit
words contain no numbers ([units](units.md)). The Model's unit system reads the
units when the equation is added.

**Reserved words.** A value key is a Python identifier that is not a Python
keyword. `rx`, `rk` and `NEVER` are also reserved. Equation text keeps Python's
own words `and`, `or`, `not`, `True` and `False`; another Python keyword, such as
`if` or `None`, is an error.

**Functions and methods.** A call parses with Python's rules for arguments:
positional arguments first, then named arguments, each name once. Equation
functions have names in the `rx.` namespace, such as `rx.max(a, b)`, and Flow
methods are written on a value, such as `operating.at(on=sale_date)`. The
[equation functions](#equation-functions) table lists them. Every argument is
named (D14), except the arguments of `rx.max`, as of Python's built-in `max`.
Text that writes `rk.` gets the suggestion `rx.`, because `rk.` computes on
values now, and a function name without `rx.` gets `rx.<name>`. A function that
makes a Flow from amounts, a profile or `rx.flow.event`, makes it over the
Periods of the Flow that the equation defines, which is declared with its
Periods. Each profile of `rangekeeper.profile`, also one that an extension
registers, is an equation function under its name in lower case:
`rk.profile.Compounding` is `rx.profile.compounding`. A growth profile of an
amount per year, such as `a_income` in `AUD pa`, gives a Flow in `AUD`: each
Period holds the amount times its length, as `Flow.from_profile` does
([amounts per year](calculations.md#amounts-per-year)). Keyed members such as
`rent[use]` are [#284](https://github.com/daniel-fink/rangekeeper/issues/284).

**Flow-valued equations.** An equation between Flows applies period by period
([D32](../../examples/walkthrough/proposed/README.md#decisions), G18):

```python
project.flow(key="land", units="AUD", periods=years)
project.equations(
    "land = -rx.flow.event(amount=land_cost, on=start_date)",
    "works = shared_works + a_works + b_works",
    "funding_need = -(net_cash_flow + loan_interest).cumulative()",
    "loan_principal = rx.max(0 AUD, funding_need - equity)",
)
```

- Arithmetic on Flows gives a Flow, and a value applies to every period:
  `cash * rate - fees`. A comparison of Flows holds when it holds in every
  period.
- A Flow takes its Periods from its declaration, `flow(key=, units=,
  periods=)`, or from its operands. Two Flows whose declarations give other
  Periods do not combine: the equation raises `EquationError` with the code
  `ALIGNMENT_DIFFER`.
- A Flow made from amounts, by a profile or `rx.flow.event`, takes the Periods
  of the Flow that its equation defines. That Flow must be declared with its
  Periods (D44); otherwise the equation raises `EquationError` with the code
  `EQUATION_FUNCTION`.
- A Flow method keeps the Periods of its Flow, and a periodwise function, such
  as `rx.max`, the Periods of its Flow arguments.

`commit()` checks the domains again: a Flow combines only with a Flow or a
numerical value, so a Flow plus a date, or a Flow as a condition of `and`, does
not commit. Inferring the Periods of a Flow that is not declared is
[#282](https://github.com/daniel-fink/rangekeeper/issues/282).

A call is a `call` Expression of the function's Function record
([functions and domains](#functions-and-domains)). An argument that a call can
give by position is a positional argument, in the order of the signature, and
every other argument is a named argument, so `rx.max(a, b)` and
`rx.max(left=a, right=b)` make the same records. A method's Flow is its first
positional argument. The draft adds the Function record of each function that
an equation calls to the Model's definitions; the record has the same UUID in
every Model.

**Errors.** The draft checks each equation when it is added. When one equation
of a call fails, the call adds none. Text that does not make an equation raises
`EquationError` ([errors](errors.md#errors)). `text[start:end]` is the part
that fails, and the message marks it:

```text
Value with key 'work_cost' not found in Entity project; nearest: works_cost, total_cost
  total_cost = land_cost + work_cost
                           ^^^^^^^^^
```

| Code | Cause |
| --- | --- |
| `EQUATION_SYNTAX` | The text does not parse: an unexpected or a missing token, a bracket that is not closed, a chained comparison, or a Python spelling such as `==`. `suggestions` gives the spelling of equation text |
| `REFERENCE_MISSING`, `REFERENCE_AMBIGUOUS` | A name matches no Value, or several. `suggestions` gives the nearest keys or codes |
| `UNITS` | The units of a literal are not valid, or an argument has units of another dimension than its parameter, such as a rate in `AUD`. The error marks the unit words or the argument |
| `EQUATION_FUNCTION` | An unknown function or method, or a member of a value. A call with an unknown or a missing argument, an argument given twice or by position where only a name is accepted, or an argument of the wrong kind, such as a Flow where a date is expected. The error marks the call or the argument; `suggestions` gives the nearest names |
| `PREDICATE` | The text is not Boolean, for example `total_cost + 1 AUD` |
| `ALIGNMENT_DIFFER` | Two Flows over other Periods in one operation |

`commit()` then validates the domains of every expression with the revision,
for example a date compared with an amount, or a Flow plus a date. Dimensional checks of equations are
[#151](https://github.com/daniel-fink/rangekeeper/issues/151).

## The Python form: rx

`rangekeeper.expressions`, imported as `rx`, writes equations in Python
([ADR-015](../decisions/015-authoring.md#equations),
[D32](../../examples/walkthrough/proposed/README.md#decisions)). A declaration on
an entity handle returns a value handle, and `project.ref(key=)` finds the
handle of a value declared earlier. Python's operators on handles build
equations, and `project.equations(...)` adds them as it adds text:

```python
import rangekeeper.expressions as rx

noi = project.ref(key="noi")
coverage = project.ref(key="coverage")
debt_service = project.ref(key="debt_service")
equation = noi == coverage * debt_service
assert equation.text == "noi = coverage * debt_service"
project.equations(equation, rx.max(noi, "0 AUD pa") >= debt_service)
```

| Python | Equation text |
| --- | --- |
| `a == b`, `a != b`, `a < b`, `a <= b`, `a > b`, `a >= b` | `a = b`, `a != b`, `a < b`, `a <= b`, `a > b`, `a >= b` |
| `a + b`, `a - b`, `a * b`, `a / b`, `a ** b`, `-a` | The same |
| `(a >= b) & (c >= d)`, `x \| y`, `~x` | `a >= b and c >= d`, `x or y`, `not x` |
| `"2 % pa"`, `rk.Quantity(text="2 % pa")`, `1` | `2 % pa`, `1` |
| `rk.duration.NEVER` | `NEVER` |
| `datetime.date(2027, 1, 1)` | `date(2027, 1, 1)` |
| `rx.max(a, b)`, `x.at(on=d)` | The same |

An operator or a function makes a `Term`. `term.text` is its equation text,
with each value written by its key; it reads back to the same records.
`term.kind`, `term.units` and `term.periods` give what it is, when the
declarations give them.
`==` on handles makes an equation, so compare handles by `id`; a Term has no
truth value, so `if` on a Term raises `TypeError`. A call is checked when it is
written, with the rules of equation text; an error is a `ContractError` with
the code and the `suggestions` in `values`. `rk.` functions compute on values
now; `rx.` functions build equations. `rk.finance.npv` and `rx.finance.npv`
each have one job, and neither checks which kind of argument it has.

## Equation functions

One registry declares each equation function once
(`rangekeeper.model.expression.catalogue`, ADR-015): its name, its parameters
with their kinds and units, its result, its evaluation stage, its availability
rule and the value function that it mirrors. The equation text parser, `rx`
and the table below are made from it.
[`tools/expressions/generate.py`](../../tools/expressions/generate.py) writes
`rx` and this table; a test fails when they differ from the registry.

- **Stage.** `affine`: the solve compiles the call into the affine problem.
  `after_affine`: the solve evaluates it after the affine stage, from
  determined values, and verification checks it (D4).
- **Availability.** When a result is known, from when its arguments are known:
  `periodwise` (each period from the same period), `running` (each period from
  the periods up to it), `shifted` (from the period `by` periods away) or
  `complete` (from every period). A rule reads only known values (G53).
- **Periodwise functions** take a Flow where a parameter takes a value, and then
  apply period by period: `rx.max(0 AUD, need)` is a Flow when `need` is one.
- **Piecewise functions.** `rx.max` and `rx.min` have the Function codes
  `rx.max` and `rx.min`, which the solve recognises: it picks the active side
  of each call and checks it after the solve (G77,
  [execution](execution.md)).
- **One row for each period.** `rangekeeper.model.expression.lowering.per_period`
  writes a Flow-valued equation as one scalar equation for each period, over
  the Movements of its Flows: a periodwise call becomes one call for each
  period, and `cumulative()`, `diff()`, `total()`, `first()` and `last()`
  become sums and differences of Movements. Other calls raise
  `UnsupportedError` there. A solve writes every call itself, with the
  coefficients that its value function gives
  ([Flow equations and equation functions](execution.md#flow-equations-and-equation-functions),
  [#276](https://github.com/daniel-fink/rangekeeper/issues/276)).

<!-- BEGIN GENERATED FUNCTIONS -->
| Function | Meaning | Stage | Availability | Mirrors |
| --- | --- | --- | --- | --- |
| `rx.finance.interest(balance=, rate=)` | The interest on a balance in each period. | `affine` | `periodwise` | `rangekeeper.finance.interest` |
| `rx.finance.irr(flow=)` | The internal rate of return of a Flow: the rate whose NPV is zero. | `after_affine` | `complete` | `rangekeeper.finance.irr` |
| `rx.finance.npv(flow=, rate=, on=)` | The net present value of a Flow on a date. | `affine` | `complete` | `rangekeeper.finance.npv` |
| `rx.flow.event(amount=, on=)` | A Flow with one amount, in the period that contains a date. | `affine` | `periodwise` | `rangekeeper.flow.Flow`, with the amount on its date and zero elsewhere |
| `rx.max(left, right)` | The larger of two values, period by period for Flows. | `after_affine` | `periodwise` | Python's built-in max, period by period |
| `rx.min(left, right)` | The smaller of two values, period by period for Flows. | `after_affine` | `periodwise` | Python's built-in min, period by period |
| `rx.profile.compounding(initial=, rate=, start=, every=, base=)` | A Flow made by the growth profile Compounding. | `affine` | `periodwise` | `rangekeeper.flow.Flow.from_profile` with `rangekeeper.profile.Compounding` |
| `rx.profile.constant(initial=, start=, every=)` | A Flow made by the growth profile Constant. | `affine` | `periodwise` | `rangekeeper.flow.Flow.from_profile` with `rangekeeper.profile.Constant` |
| `rx.profile.linear(initial=, rate=, start=, every=, base=)` | A Flow made by the growth profile Linear. | `affine` | `periodwise` | `rangekeeper.flow.Flow.from_profile` with `rangekeeper.profile.Linear` |
| `rx.profile.scurve(total=, start=, length=)` | A Flow made by the distribution profile SCurve. | `affine` | `periodwise` | `rangekeeper.flow.Flow.from_profile` with `rangekeeper.profile.SCurve` |
| `rx.profile.uniform(total=, start=, length=)` | A Flow made by the distribution profile Uniform. | `affine` | `periodwise` | `rangekeeper.flow.Flow.from_profile` with `rangekeeper.profile.Uniform` |
| `x.at(on=)` | The amount of the period that contains a date. | `affine` | `complete` | `rangekeeper.flow.Flow.at` |
| `x.cumulative()` | The running totals of a Flow. | `affine` | `running` | `rangekeeper.flow.Flow.cumulative` |
| `x.diff()` | Each amount less the amount before it. | `affine` | `running` | `rangekeeper.flow.Flow.diff` |
| `x.first()` | The amount of the first period. | `affine` | `complete` | `rangekeeper.flow.Flow.first` |
| `x.last()` | The amount of the last period. | `affine` | `complete` | `rangekeeper.flow.Flow.last` |
| `x.max()` | The largest amount of a Flow. | `after_affine` | `complete` | `rangekeeper.flow.Flow.max` |
| `x.min()` | The smallest amount of a Flow. | `after_affine` | `complete` | `rangekeeper.flow.Flow.min` |
| `x.shift(by=)` | Each period's amount from the period `by` periods away. | `affine` | `shifted` | `rangekeeper.flow.Flow.shift` |
| `x.since(on=)` | The same periods, with zero before a date. | `affine` | `periodwise` | `rangekeeper.flow.Flow.since` |
| `x.total()` | The sum of the amounts of a Flow. | `affine` | `complete` | `rangekeeper.flow.Flow.total` |
| `x.until(on=)` | The same periods, with zero after a date. | `affine` | `periodwise` | `rangekeeper.flow.Flow.until` |
<!-- END GENERATED FUNCTIONS -->

Equation text has no Span value and no enum value, so `flow.trim(span=)` and the
`day_count=` of `rk.finance.interest` have no equation form. In an equation, use
`x.since(on=)` and `x.until(on=)` to keep part of a Flow.

The equivalence tests check each entry: text and `rx` make the same records
and the same text, text reads back to the same records, and the call evaluated
on fixed data equals its value function.

## Dates and NEVER

A date literal, a reference to a date Value and a selected Span endpoint have
the `date` domain. A date literal has the shape of a date Value: `kind: date` with
`date: 2027-01-01`, or `kind: date` with `never: never`, never both
([#387](https://github.com/daniel-fink/rangekeeper/issues/387)). Unlike a Value,
a literal is never unresolved, so it has one of them.
`authoring.date_literal(value)` declares a date or `rk.duration.NEVER`. `NEVER`
means the event does not happen; it is not missing.
A date Value with no recorded content is unresolved, not NEVER. In equation text
NEVER is written `NEVER`; the word is reserved, so no Value key can be `NEVER`.
A calendar date is written `date(2027, 1, 1)`, as in Python. The functions treat
NEVER as "no Flow": `rx.flow.event(amount=, on=NEVER)` and `x.since(on=NEVER)`
are zero in every period, `x.until(on=NEVER)` keeps every amount, and a profile
with `start=NEVER` has no amounts.

| Operation | Result |
| --- | --- |
| date + length, length + date, date − length | A date. A length is a whole number of days, weeks, months, quarters or years, such as `1 year` |
| NEVER + length, NEVER − length | NEVER |
| `==`, `!=`, `<`, `<=`, `>`, `>=` on two dates | Boolean. NEVER equals NEVER and is later than every date |

A month, quarter or year step keeps the last day of a month: 31 January plus one
month is 28 February, and 28 February plus one month is 31 March
([calendar rules](calculations.md)). Validation rejects every other operation on a
date: the difference of two dates, a date and a number or an amount, negation,
multiplication and a comparison of a date with a Quantity.
`rk.duration.shift(on=, by=)` applies the same arithmetic in Python, and
`rangekeeper.model.expression.evaluation.evaluate_date` and `compare_dates`
evaluate date Expressions from supplied values. A solve determines the dates
that date equations give from fixed dates, and decides each equation over dates
exactly ([date equations](execution.md#date-equations)).

Comparisons produce Boolean expressions. A Constraint asserts that one must
hold. Equality is not assignment. Boolean operators require Booleans, without
numeric coercion. Conjunction and disjunction short-circuit during evaluation;
both operands remain in symbolic dependency analysis and must be well typed.

## Functions and domains

`function.yaml` describes Function identity, code, version, signature, result
domain, mathematical semantics, and unit rules. Function codes are unique within
the Model's Function collection. A call uses the UUID; the Model revision pins
the exact definition and version.

Positional arguments bind in signature order. Named arguments bind by name.
Duplicate bindings, unknown names, excess positional arguments, and absent
required parameters are errors. Optional arguments have explicitly documented
omission semantics; omission is not an unresolved argument. Named-only arguments
follow positional arguments, and optional positional arguments follow required
ones. Parameter names must be unique.

Functions are pure: no Model mutation or ambient session reads. All model inputs
are explicit arguments. The contract does not store Python import paths or grant
access to arbitrary runtime methods. Implementations and backend support belong
to a separate registry/compiler and execution record.

`Domain` describes permitted argument or result content. Its `kind` distinguishes
scalar, structured, and collection categories. `Parameter.domain` and
`Function.result` each contain a Domain; `Parameter.kind` separately determines
whether an argument can be supplied positionally or only by name.
`quantity` accepts numerical content with optional compatible-unit requirements;
`number` requires dimensionless content. `measurement` additionally requires
measurement meaning, optionally an exact Measure. A bare Quantity does not gain
that meaning solely by having compatible units. Arithmetic derives quantities;
it does not automatically assign a Measure to an intermediate result.
Collections specify one recursive `item_domain` and may require a set, bag, or sequence.
Units and function semantics are explicit prose contracts at this stage, not
executable unit formulas. A structured Domain describes a Function contract; it does not itself define
serialized Value content or executable members. Canonical Flow payloads exist;
general Stream member contracts remain a separate requirement. The `account`
Domain kind is only a category name: there is no Account class, because a
funding balance is the `cumulative()` sum of a Flow ([D2](../../examples/walkthrough/proposed/README.md#decisions)).

Member selection reads a declared public member of the base content. Index selection
uses the content's index convention. Sequences use zero-based nonnegative integer
indices; temporal indices need the temporal content contract. Sets and bags have no
positional indices. Missing members and out-of-range indices are errors. If an
Entity characteristic already has a Value UUID, reference it directly.

## Analysis and uncertainty

`model._scope` owns UUID-keyed declaration lookup over raw mappings, and
`model.targets` reads a Reference target in a typed Model. `model.formulation` collects
owner-local declarations with original paths. `model.expression.validation`
checks signatures, binds arguments and analyzes each expression once; its immutable
ExpressionAnalysis contains node, domain and path maps. Constraints and objectives
consume those results. `domains.py` contains local rules; numerical evaluation and
rule truth remain separate.

Domain comparison is directional and returns compatible, incompatible or unproven.
Missing units do not prove dimensionless content. A required Function argument,
predicate or objective cannot rely on an unproven domain. Passive reporting queries
may remain unproven, with normal structural and reference checks still applied.

Static query inference filters the permitted Value declaration inventory by key
and Measure without following graph edges. A nonempty homogeneous candidate set
can establish an item domain. Measurement, property and Flow candidates retain
their different kinds. Mixed or empty candidates do not prove a measurement type;
a Measure filter alone is insufficient because Flows also carry Measures. The
runtime result count and membership remain unknown to static validation.

## Queries and aggregations

A Query starts at an Entity UUID in the containing Model revision. It cannot
read a live CRM or external database. Apply these stages in order:

1. Traverse each listed step, in sequence. With no steps, start with the root.
2. Filter the resulting Entities using fixed classification and Label metadata.
3. Project Entity identities or matching Value identities.
4. Apply duplicate handling to the projected UUIDs.

Relationship steps identify an exact Relationship `classification` and direction.
Membership steps follow `Assembly.entities`. Neither implies the other.
Direct traversal follows one edge. Transitive traversal follows one or more
edges along simple paths: an Entity cannot repeat within a path for that step.
The starting Entity is excluded from that step's results. Different paths can
reach the same Entity; the duplicate policy handles the resulting occurrences.

Filters match exact Classifications; there is no implicit taxonomy expansion.
Label filters require the given owner-local key and an included Classification.
Filters are conjunctive and act after traversal, so a nonmatching intermediate
Entity does not prevent traversal to a matching descendant. Unknown numerical
values cannot determine query membership in this revision.

Value projection selects by either an owner-local key or an exact Measure UUID.
`cardinality: one` rejects multiple matches per Entity; `many` retains them.
No match follows the explicit `missing: error` or `omit` policy. An unresolved
Value is still a match; absence of its Quantity is never a reason to omit it.

`duplicates: distinct` produces a set of UUIDs. `preserve` produces a bag with
one occurrence per traversal path and projected match. Neither promises order.
A query matching no Entities produces an empty collection, independently of
missing-characteristic handling.

Aggregation is a Function call over that collection. Sum preserves unknown
members as symbols rather than substituting stored amounts. If any collection
argument is empty, the Function's `empty_collection` behaviour applies: reject
it, or return zero when a numerical result and its units can be established.
Unresolved members are neither dropped nor interpreted as zero. Multiplicity
affects the result when the Query deliberately retains it.

For example, the [graph aggregation fixture](../../examples/schema/query-aggregation.yaml)
expresses the sum of apartment rent within Building A. Apartment A is reachable
directly and via a floor. `distinct` retains its rent Value once; Workspace A
is excluded. All rent amounts are unresolved. The expected symbolic sum contains
Apartment A's and Apartment B's rent, not a numerical total. A separate Assembly
membership query demonstrates counting, without inferring containment.

## Constraints

`constraint.yaml` defines an identified assertion with a required Expression UUID
in `predicate`. Optional `code`, `name`, and `description` identify and explain the
requirement. A code is unique within its Constraint collection when supplied.
The referenced Expression can be a root or nested node; multiple Constraints can
reference the same node. The two valuation Constraints assert the existing NOI
and capitalization equations without duplicating their Expression trees.

An eligible predicate has a Boolean result domain. This is a semantic requirement,
not a restriction to one `Expression.kind`: comparisons, logical expressions, and
Boolean-returning calls qualify. Resolving an Expression UUID and establishing its
domain are separate from checking its serialized reference shape. A numerical
predicate is invalid; a Boolean `false` predicate is valid syntax but cannot satisfy
an assertion requiring it to be true.

All Constraints in Model and Specification Formulations are imposed together. Specification
additions cannot override or deactivate Model requirements. Fixed
and unknown Values, numerical settings, and Run diagnostics remain separate from
the Constraint. Equality does not specify an assignment direction. Constraint
validation neither evaluates its predicate nor proves feasibility or backend support.

## Validation and execution boundary

The schemas and checks establish:

- Variant structure, operator form, typed UUID syntax, and nested operand order.
- Function signatures, collection domains, traversal and projection options.
- Generated Python round trips, including false, zero, and date-valued selections.
- Date and NEVER literal nodes, date arithmetic and date comparisons; rejection of
  deferred string literal nodes.
- Bounded reference, argument-binding, coarse domain, and identity checks.
- Constraint predicate references and Boolean result domains, including nested
  and reused predicates, Boolean calls, and literal false predicates.

The [structured-expression fixture](../../examples/schema/function-expressions.yaml) includes
Flow total, annual IRR, a Span endpoint, the `transactions` member of a fixture-only
`account` domain, and indexed balances.
Its `input_domains` entries describe fixture-only domains, not serialized Value
records. The checker supplies illustrative member domains for these examples.
Canonical Flow Values already have a serialized payload. These fixtures do not
establish general executable member or Function contracts for Flow or Stream
content.

The checker does not evaluate Constraint satisfaction, traverse the graph, establish
query result cardinalities, validate dimensions, find IRR roots, or solve equations.
Function unit rules and mathematical behaviour still require implementations and
independent tests.
At signature boundaries, the bounded checker recognizes identical unit spellings
and the explicit `dimensionless` convention; it conservatively rejects other unit
matches. This is not a complete compatibility or conversion algorithm. The separate
graph fixture exercises compatible-unit conversion through the existing runtime.
Generated constructors enforce structure. Owning validators establish references,
content rules and complete mathematical roles before execution. A function being evaluable does not establish that a backend
can solve through it for the unknowns selected by a Specification.

Readable formula text can be parsed into these records and retained as authoring
or provenance material. It is not a second independently editable mathematical
authority. Loading any of these records does not execute code.

## Subsequent work

The scalar execution subset and its independent acceptance checks are described
in [scalar execution](execution.md). General symbolic graph-query execution
and aggregation with symbolic members require further adapters. Flow Value
payloads already exist. Define the missing structured Function/member
contracts and backend support before claiming general Flow expression
execution.
Conditionals, slicing, grouping, unknown-dependent query membership, unrestricted
graph query languages, and general-purpose code execution are outside this draft.

## Passive Flow and hierarchy builders

Builders use mathematical roles, not permanent calculation direction. A
Specification can fix a total and solve a summand. Each builder takes every
argument by name, also the Model: `flow.sum(model=, id=, summands=, total=)`
(D14). The signatures use:

| Builder | Quantity parameters |
| --- | --- |
| `expression.authoring.add_all` | `summands` |
| `flow.sum` | `summands`, `total` |
| `flow.scale` | `multiplicand`, `multiplier`, `product` |
| `flow.accumulate` | `increments`, `initial`, `accumulation` |
| `growth.compound` | `initial`, `rate`, `series` |
| `growth.linear` | `initial`, `increment`, `series` |
| `financial.discount` | `series`, `rate`, `discounted` |
| `financial.pv` | `sequence`, `value` |
| `financial.interest` | `principal`, `rate`, `interest` |
| `flow.aligned` | `members`, `reference` |
| `flow.resample` | `sequence`, `resampled` |

Binary expressions retain `left` and `right`. `flow.sum` accepts ordered Value IDs
or an original `Stream.from_values` selection from the exact Model revision.
Structural trims are supported; calculated Stream transformations require declared
intermediate Flow Values and relationships. `flow.aligned` uses the reference
Flow's order without reading its amounts.

`flow.resample` uses the resampled Flow's bounded periods. It supports SUM, MEAN
(fixed equal weights), ELAPSED_MEAN (fixed day weights), FIRST and LAST. All declared symbols participate,
including unknown amounts. SKIP and PROPAGATE policies are rejected for passive
authoring. Explicit ZERO permits an empty target group; it never replaces an unknown
symbol. MIN/MAX require solver capabilities outside the current affine slice.

`financial.pv` sums an already discounted sequence. Its saved operation name remains
`present_value`, so existing declaration identity fixtures do not change. Other
keyword renames also preserve expression order, binding order and declaration IDs.

There is no dedicated `financial.reversion` helper. Compose a capitalisation
relationship with ordinary expressions and an explicit Movement mapping:

```python
from rangekeeper.model.expression.authoring import equal, divide, reference
from rangekeeper.model.formulation import declare
from rangekeeper.model import Reference

capitalisation = declare(
    id=relation_id,
    name="capitalisation",
    equations=[
        (
            str(value_movement.id),
            equal(
                reference(Reference(target=value_movement.id)),
                divide(
                    reference(Reference(target=income_movement.id)), reference(rate)
                ),
            ),
        )
    ],
    values=[value_id, income_id, rate_value_id],
)
```

Select income timing explicitly, such as the following period's income supporting
a value at this period's end. Declare any sale event separately. With an explicit
nonzero-rate domain, a product equation can permit solving the rate when the value
is fixed. Do not rewrite saved quotient equations; an unknown divisor is outside
the current executor's supported slice.

`FlowRollup(...).formulate(hierarchy=..., id=..., aggregates=...)` declares SUM
relationships from the same original contributors used by the numerical rollup.
Aggregate Flow Values must already exist on their named entities. Use explicit
intermediate Flow equations when those intermediate quantities need individual
roles. See [Flow rollups](system.md#flow-rollups) and the
[executable example](../../examples/rangekeeper_examples/flux.py).
