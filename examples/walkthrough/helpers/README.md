# Walkthrough helpers

The lessons import these helpers to load data and to show charts, graphs and
geometry. They are not part of the Rangekeeper package and have no stability
promise ([ADR-010](../../../docs/decisions/010-layers-and-packages.md)). The
[walkthrough environment](../README.md#run-the-lessons) installs their
dependencies. Helpers never select financial contributors, supply rates or hide
an equation ([ADR-020](../../../docs/decisions/020-walkthrough-plan-v2.md),
principle 10).

| Module | Contents |
| --- | --- |
| `data` | `load_property(year=)`: the totals of the mixed-use property in a stabilised year, each with its origin, and `load_base_plan()`: the dates, budgets, incomes, operating costs, renewals and funding of the development, with its areas, rates and phases, from the [data package](../../data/mixed_use_property/README.md), and `data_path(name=)`: the path of one file of the package, for `rk.io.load` |
| `plot` | Notebook display: `show_plot`, `show_flows`, `plot_cash_flows`, `plot_flows`, `plot_paths`, `plot_target_curve`, `show_graph`, `show_sunburst`, `show_timeline`, `show_equations`, `show_relations` and `show_geometry` |
| `theme`, `theme.js` | The shared Plotly style and the light/dark bridge |
| `chart` | Plotly charts of Flows, hierarchies and distributions |
| `graph` | PyVis graph display of a View |
| `local` | `LocalDisplay`, a read-only loopback file server for notebook iframes |
| `speckle`, `speckle_contract.json` | The canonical design envelope, below |
| `geometry`, `assets/geometry/` | The local geometry viewer and its verified assets, with `SPECKLE-LICENSE`; the [viewer build](../viewer/README.md) makes the assets |

The lessons import `load_property`, `load_base_plan`, `data_path`, `show_equations`,
`show_geometry`, `show_timeline`, `plot_cash_flows`, `plot_flows`, `plot_paths` and
`plot_target_curve` from `helpers` directly. `load_property` reads the derived totals file of the data package and
does no arithmetic; [`derive_totals.py`](../../data/derive_totals.py) derives the
file and documents each total. The works cost includes the plan's soft costs,
contingency and construction finance allowance. `load_base_plan` reads the derived
base plan file in the same way, and
[`derive_base_plan.py`](../../data/derive_base_plan.py) derives it: its budgets
leave out the allowance, because lesson 03 calculates the loan interest.
`show_equations(of=)` draws a Model's equations, or a Specification's fixed and
free values, with no calculation direction. `show_timeline(of=)` draws the phases
of a plan as the plan gives them. `plot_cash_flows(outcome=, key=)` and
`plot_flows(outcome=, keys=)` draw solved Flows of an Outcome and calculate
nothing; `plot_flows(flows=)` draws Flows that the lesson labels and calculates.
`plot_paths(paths=)` draws each series of each market path.
`plot_target_curve(outcomes=, key=, markers=)` draws the share of the cases of a
batch at or below each value, and each marker as a vertical line.

The [walkthrough guide](../../../docs/guides/walkthroughs.md#shared-chart-style)
describes the chart style and the local display. The helper tests are in
[`../tests`](../tests).

## Canonical design transport

`helpers.speckle` encodes and decodes the canonical design envelope. It is a pure
codec. It does no authentication, network access, storage, conversion or solving.
Geometry remains outside the Model. The codec does not infer domain membership
from a service collection hierarchy.

Rangekeeper contains no service transport and no legacy source conversion. A
consumer that receives design content from a service, or converts a historical
payload, does that work outside Rangekeeper and creates canonical records through
the public library API. See the
[upgrade guide](../../../docs/guides/upgrading.md) for the removed APIs and the
[Grasshopper example](../../grasshopper/README.md) for native authoring.

### Canonical envelope

The versioned envelope is `rk.speckle-model/v1`. Its fields are declared once in
[`speckle_contract.json`](speckle_contract.json). The same file generates the C#
constants of the Grasshopper example.

| Field | Contract |
| --- | --- |
| `rk_format` | `rk.speckle-model/v1`. |
| `rk_model` | Canonical Model JSON as a string, not a service object hierarchy. |
| `rk_associations` | External geometry associations scoped to that Model revision. |

Each association requires `model_revision` and `domain_id`. The revision must
match the Model and the domain UUID must resolve to an Entity or Assembly.
Optional `rhino_id` is a UUID; optional `application_id` and `content_id` are
nonempty opaque strings. These identities remain distinct. Geometry content IDs
and application IDs never substitute for canonical identity or membership.
Duplicate identical associations are removed; unknown fields and invalid
associations fail.

### Operations

| Operation | Result |
| --- | --- |
| `encode_model(model, *, associations=())` | A detached envelope dictionary. It validates association scope. It creates no SDK object, network request, store write or publication. |
| `decode_model(payload)` | An immutable canonical `Model`. It strictly decodes the envelope and validates its associations. It does not convert a legacy payload. |
| `validate_associations(model, associations)` | A copied list of valid associations, with duplicates removed. The [geometry display](geometry.py) uses it to check retained associations. |

Each operation raises `MappingError` for invalid content. The error carries the
envelope `path` and, where available, the domain `identity`. A payload without the
canonical `rk_format` value fails; it needs an explicit source reader outside
Rangekeeper.

Domain validation imports no service SDK or Rhino library. A successful fixture
or canonical decode is not evidence that a live service or host connector route
works.

Do not use first-match conflict resolution or infer membership from collection
nesting. Publish only after full Model validation. C# structural and local
validation does not replace Python units, mathematical or provenance validation.

The [integration history](../../../docs/history/source-workflows/2026-10-08-integration-record.md)
keeps earlier source-consumer and pinned-service observations, and the
[Windows connector procedure](../../../docs/history/windows-acceptance.md) keeps
the retired host gate. They are historical evidence, not claims of current
live-service acceptance.
