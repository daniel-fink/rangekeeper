# ADR-019: Walkthrough direction for 1.0

Status: accepted for 1.0; walkthrough plan v2 is ADR-020. Recorded: 2026-10-26.

## Problem

- **Lessons on different branches.** Lessons 01–03 exist on the walkthrough
  branch. The legacy notebooks on `develop` use an API that no longer exists.
- **Lessons do not show the library.** Lesson 03 uses plain Python for most of
  its finance and writes equations with nested constructor calls. A reader
  could conclude that the library adds ceremony.
- **No pedagogy or execution rules.** The curriculum has no reader types,
  learning outcomes or rules for showing the developer experience.
- **No CI execution.** CI does not run the notebooks.

## Choice

- **Scope.** All lessons are rebuilt for 1.x: lessons 01 to 06, and any further
  lessons that plan v2 adds. The [ADR-006 curriculum](006-walkthrough-curriculum.md)
  stays the base. Plan v2 revises it. [ADR-020](020-walkthrough-plan-v2.md)
  records plan v2 and supersedes ADR-006.
- **Release.** Version 1.0.0 waits for the full walkthrough. This includes the
  sequential-decision and design-variant capabilities that lessons 05 and 06
  need ([ADR-013](013-execution-and-extensions.md) and [ADR-014](014-market-paths.md)).
- **Plan v2** defines:
  - the reader types and book outcomes;
  - the goals, prerequisites and time estimate of each lesson;
  - the developer-experience principles.
- **Proposed cells first.** Write the code a reader should type for each lesson.
  Each helper or plain-Python workaround that a common task needs goes onto the
  API gap list. Implement the gaps, then author the lessons. This pass settles
  the builder shape in [ADR-015](015-authoring.md).
- **Helpers.** The walkthrough helpers own the adapters that leave the core
  library: the Speckle envelope, the geometry viewer and charts
  ([ADR-010](010-layers-and-packages.md)). The walkthrough CI job tests them.
- **Execution.** Notebooks have no outputs in git. CI runs each lesson from a
  fresh kernel. The docs site build renders the results
  ([ADR-018](018-release-and-engineering.md)).
- **Sources.** Third-party sources are cited by link, not copied. Figures are
  redrawn, or used with written permission and attribution.
- **Location.** The walkthrough moves onto `develop` under `examples/walkthrough`
  by the [branch procedure](../guides/walkthroughs.md#branches-and-publication).
  The legacy `walkthrough/` folder is retired when its replacements are accepted.
- **Usability test.** Readers who have not seen the book complete the lessons in a
  usability test before 1.0.0rc1.

## Alternatives and consequences

- **Ship 1.0 with lessons 01–03 only.** The API would be frozen before the
  lessons that test it exist.
- **Design the lessons only, and author them in 1.x.** This protects the API,
  but 1.0 would ship without its main tutorial.

The release date depends on the sequential-decision work. Pre-releases give
downstream users stable versions to pin to in the meantime.

## Sources and related decisions

- [ADR-006: walkthrough curriculum](006-walkthrough-curriculum.md), amended by
  this record.
- [Walkthrough guide](../guides/walkthroughs.md) and
  [mixed-use project brief](../guides/mixed-use-project.md).

Supersedes: none. Amends: ADR-006. Superseded by: none.
