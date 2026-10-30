# ADR-016: Safety defaults for units, outcomes and diagnostics

Status: accepted for 1.0; curated units, structured diagnostics and errors implemented in 1.0.0a2 (#149, #154, #155, #156, #312); missing values in filters and rollups implemented (#121, #157); dimensional checks of Model equations and Specification assignments implemented (#151); the underdetermined outcome pending. Recorded: 2026-10-26.

## Problem

A usability test found traps that give no warning:

- **Unit strings.** The unit registry accepts every Pint unit and SI prefix.
  So `"AUD pa"` becomes AUD × picoyear, `"pct"` becomes picocarat, and `"$"`
  raises an empty assertion.
- **Underdetermined solves.** A solve with fewer independent equations than
  unknowns reports a feasible solution. It publishes zero values, and only a
  warning shows the rank problem.
- **Late unit checks.** A unit mismatch inside an equation is found only during
  execution. It is reported as an unsupported capability.
- **Diagnostics without context.** A message such as `/: missing solve role
  for required Value` names no Value. Solver evidence is JSON text inside a
  message. One validator searches message text.
- **Silent or bare lookups.** Some lookups return an empty result for an
  unknown code. Others raise an error that shows only a UUID.

## Choice

### Units

The unit registry is curated. It contains:
- ISO 4217 currencies;
- length, area and volume, with SI prefixes;
- time, without prefixes;
- count, dwelling, percent and ratio;
- the aliases `sqm`, `sqft` and `pa`. `pa` means per annum, so `"AUD pa"`
  means AUD per year.

An unknown or ambiguous string fails with suggestions. The registry follows
the extension pattern in [ADR-013](013-execution-and-extensions.md). A Model
records its unit system. `Model.unit_system` is public, and derived operations
use it by default.

### Dimensions

Dimensional analysis runs on each equation when a Model is created or revised.
It runs on each assignment when a Specification is validated. A mismatch has
the code `incompatible_units`. It names the equation and both units. Execution
never reports a unit mismatch as an unsupported capability.

### Solution outcomes

- **Underdetermined is its own outcome.** The solution status `underdetermined`
  names the free unknowns. No output is published by default.
  `allow_underdetermined=True` publishes the candidate, and the Run marks it
  as underdetermined.
- **A false fixed predicate is infeasible,** the same as a false constraint.

### Diagnostics

- An enum gives the code for each diagnostic. It is `rangekeeper.errors.Code`
  (walkthrough decision D26), not `DiagnosticCode`.
- Diagnostics carry structured fields: targets, values and evidence.
- Messages name objects by code or key and by UUID.
- The library never parses message text.

### Errors and lookups

- `rangekeeper.errors` defines a `RangekeeperError` base class. Subclasses also
  inherit a matching built-in type where useful, for example
  `ValidationError(RangekeeperError, ValueError)`.
- Exception names end in `Error`.
- A lookup by UUID or code raises `MissingReferenceError`. The error names what
  was requested and where.
- A `find_*` search can return an empty result.

### Missing values

Filters and rollups never treat a missing value as zero. A record whose tested
value is missing does not pass a filter. Results count missing values in their
coverage.

## Alternatives and consequences

- **Keep Pint's full catalogue and reject only known traps.** This option is
  broader, but other surprises remain.
- **Always fail an underdetermined solve.** This option is strict, but some
  investigations accept one candidate on purpose. With the opt-in, that choice
  is explicit.
- **Check units at execution only, with the correct code.** Errors would still
  appear late and far from their cause.

Every diagnostic and error test changes to use codes and fields, not message text.

## Sources and related decisions

- [ADR-013: execution and extension points](013-execution-and-extensions.md).
- [ADR-017: public API and data formats](017-api-and-formats.md) for the query
  `Filter` extension.

Supersedes: none. Superseded by: none.
