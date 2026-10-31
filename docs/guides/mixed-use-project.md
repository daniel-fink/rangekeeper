# Mixed use property project brief

This is the continuing project for walkthrough lessons 02–07. Notebook 02 asks
how its spaces, buildings and shared systems produce income, costs and value.
Later lessons add a development plan, inverse financial questions, uncertain
markets and flexibility strategies.

The reference is the actual legacy Rangekeeper design. Its complete pinned source
was captured on 2026-10-12 and converted to the current canonical Model. The
[source package](../../examples/data/mixed_use_property) contains the
original transport records, external geometry associations, canonical Model and
an independently reconciled inventory. [ADR-020](../decisions/020-walkthrough-plan-v2.md) owns the complete walkthrough
plan. The archived [notebook 02 outline](../history/plans/006-notebook-02-outline.md)
records the interim chapter's sequence and visual aids.

## The property

The design comprises two mixed-use buildings over a shared basement plinth.
Building A combines a hotel, residential accommodation, retail and parking.
Building B combines residential accommodation, retail and parking. The plinth
contains two basement parking levels and shared plant. Each building has a core
system. The service relationships connect these physical components.

For notebook 02, treat this as a proposed completed property with a fixed use mix.
The source does not establish a site address, construction programme, funding plan,
market forecast or permission for an alternative use. Those belong to later,
explicit teaching assumptions.

### Verified quantities

These are sums of the 33 unique floor objects, not sums of floor values and parent
totals. Floor objects are spatial components; their count is not the number of
distinct building storeys. Some share a name or elevation.

| Component | Use | Floor objects | Gross floor area (m²) |
| --- | --- | ---: | ---: |
| Building A | Hotel | 14 | 11,716.69 |
| Building A | Residential | 4 | 2,308.32 |
| Building A | Retail | 2 | 1,511.83 |
| Building A | Parking | 1 | 1,038.79 |
| Building B | Residential | 8 | 11,442.74 |
| Building B | Retail | 1 | 815.98 |
| Building B | Parking | 1 | 1,178.16 |
| Shared basement plinth | Parking | 2 | 12,773.74 |
| **Property** | **All uses** | **33** | **42,786.26** |

Building A totals 16,575.63 m²; Building B totals 13,436.88 m². The property total
includes parking. It is neither lettable area nor an assertion about a statutory
floor-area definition. Calculations retain source precision; this table rounds
for display.

### Objects and relationships

The source has 50 domain objects: one property, three objects classified as
buildings (including the plinth), nine spaces, 33 floors and four objects classified
as utilities. The latter comprise three physical utility objects and one grouping.
The canonical Model stores 36 Entities and 14 Assemblies without duplicating them.

| Relationship | Count | Interpretation |
| --- | ---: | --- |
| `spatiallyContains` | 49 | One rooted spatial hierarchy spanning all 50 objects |
| `services` | 11 | Plant and core service dependencies |
| `contains` | 3 | The utilities assembly groups the plant and two core systems |

The shared plant serves the plinth parking and both building core systems. Building
A's cores serve its hotel, residential, parking and two retail spaces. Building
B's cores serve its residential, retail and parking spaces.

The two Building A retail spaces have the same label but different identities.
Building B also has two distinct residential Floor 0 objects. Preserve them. In
the notebook, introduce this briefly when selecting an object rather than as a
separate identity lesson.

### Source characteristics and geometry

Floor objects record GFA (m²), perimeter (m), floor-to-floor height (m), finished
floor elevation (m) and floor number. Spaces record their use and volume (m³).
Floor use is obtained from its spatial parent; it is not inserted into the source
Model as if directly observed on that floor.

| Utility object | Source volume (m³) | Spatial parent |
| --- | ---: | --- |
| Shared plinth plant | 643.105790 | Plinth |
| Building A cores | 11,086.180775 | Building A |
| Building B cores | 8,656.633886 | Building B |

The archive retains original Breps, display meshes, curves, materials, context and
property geometry. Geometry stays outside the canonical Model. The 52 association
records cover all 50 domain identities; multiple source representations do not
create extra domain objects.

All 144 mapped measurements and 45 properties agree with the captured source.
The 33 floor areas and three physical utility volumes also agree with their
supplied Brep summaries within absolute tolerance `1e-7` and relative tolerance
`1e-10`. This checks two recorded representations. It does not independently
recompute Brep geometry or establish browser-viewer acceptance.

## Financial assumptions for notebook 02

Retain the following teaching assumptions to preserve the example's meaning.
They are not current market estimates or source geometry facts. They are the
legacy rates, except two changes of 31 October 2026
([#205](https://github.com/daniel-fink/rangekeeper/issues/205)): each rent is 10 %
higher, and each floor and facade OPEX rate is 10 % lower, so that the dated plan
of lesson 03 can pay for its costs and its loan. The readable
[assumptions file](../../examples/data/mixed_use_property/assumptions.json)
records the source notebook cells and conventions separately from `model.json`,
and [`origins.json`](../../examples/data/mixed_use_property/origins.json) records
the two changes.

### Income

| Use | Efficiency | Initial rent (AUD/m² per year) | Annual income growth | Vacancy |
| --- | ---: | ---: | ---: | ---: |
| Hotel | 0.800 | 825 | 3.5% | 2.5% |
| Residential | 0.750 | 660 | 5.5% | 1.5% |
| Retail | 0.675 | 1,100 | 7.5% | 7.5% |
| Parking | 0.900 | 0 | 0% | 0% |

Initial potential income is GFA × efficiency × rent. Vacancy is a deduction from
potential income. Zero parking rent is an explicit simplification; parking still
incurs operating and capital costs.

Use Building A hotel Floor 1 as the first worked object. Its GFA is
1,697.4515719337053 m². The assumptions produce initial potential income of
AUD 1,120,318.04 and effective income of AUD 1,092,310.09. Show this arithmetic
before applying it to every floor. Its identifier is
`22851887-f9ee-4aa8-8755-bc021c3a3b30`.

### Operating and periodic capital expenditure

Negative amounts are deductions. Floor and facade OPEX grow 3.5% each year.
Facade area uses perimeter × floor-to-floor height as the inherited proxy. Explain
that this does not prove that every measured boundary is an external facade.

| Use | Floor OPEX (AUD/m² per year) | Facade OPEX (AUD/m² per year) | Floor CAPEX (AUD/m² per capital payment) |
| --- | ---: | ---: | ---: |
| Hotel | -157.5 | -45 | -100 |
| Residential | -112.5 | -45 | -75 |
| Retail | -202.5 | -90 | -150 |
| Parking | -58.5 | -22.5 | -50 |

Core CAPEX is AUD -100/m³ per capital payment; plant CAPEX is AUD -1,000/m³ per
capital payment. The example's capital payments occur on 2005-12-31 and 2010-12-31.
Retain the inherited 3.5% increase **per capital-payment interval**: exponents zero
and one for those two payments. Do not silently reinterpret it as annual compounding.
This convention concerns periodic asset expenditure, not development cost.

### Dates and valuation

- Holding span: 2001-01-01 inclusive to 2011-01-01 exclusive, ten annual periods.
- Forecast span: 2001-01-01 inclusive to 2012-01-01 exclusive; 2011 supplies the
  next-period income used at sale.
- Annual operating receipts and expenditure occur at year end. Year 2001 uses
  the initial amounts with growth exponent zero.
- NOI is effective income plus signed operating expenditure. NACF is NOI plus
  signed capital expenditure, including utility-only costs.
- Sale proceeds are 2011 NACF divided by the 5% exit capitalization rate, received
  on 2010-12-31. This is the inherited NACF convention, not NOI capitalization.
- Discount the ten holding-period net cash flows at 7%, using year-end exponents
  one through ten. Notebook 02 calculates asset value; it does not model an
  acquisition price, project debt or an equity return.

### Reporting and contributor selection

Keep the physical spatial hierarchy unchanged. Building totals can include their
own floor and core costs. The plinth has its parking and shared plant costs.
Show the plinth/shared costs separately in the property reconciliation; do not
allocate them to buildings without an explicit additional rule.

The utilities grouping is an inspection view over the same three physical
objects. Its costs are not additional to those already counted through their
spatial parents. For the root calculation, select each floor and physical utility
once. An empty grouping is not evidence of a measured zero.

The legacy notebook's NACF construction can omit utility-only capital expenditure
because it first requires income or OPEX. Preserve the intended costs, not that
omission. Verify NOI + CAPEX = NACF and component-to-property reconciliation; an
old displayed valuation is not the acceptance target.

## Visual project brief

The notebook opens with the Speckle 3D view and the legacy property-as-graph image.
It then loads the Model and displays the full interactive graph. The relationship
section explains overlapping assemblies. The spatial graph precedes GFA aggregation. Income and cost
charts reuse that hierarchy, and the 3D plant/core view sits beside utility costs.

The [detailed visual inventory](../history/plans/006-notebook-02-outline.md#visual-requirements)
specifies the required images, PyVis graphs and Plotly charts. A current record
diagram replaces the legacy object-model diagram. The original hosted viewer reports an expired model. Notebook 02 therefore uses
Speckle's viewer SDK locally, reading the complete archive. It supplies context,
property, floor and services views, object selection and recorded properties.
Static mesh images remain available as references outside the chapter. The
[chapter acceptance](../research/notebook-02-2026-10-12/README.md) records interaction
checks; the hosted saved views are not claimed to work. The
[condensed revision](../research/notebook-02-2026-10-13/README.md) retains the inline
3D-to-graph illustration, uses four sunbursts and moves presentation code into
`examples/walkthrough/helpers/plot.py`.

## Source package and reproducibility

The original source pin is project `c0f66c35e3`, object
`e7acaac21ae7e9369339900a4aaeb827`. The historical model is `119ad04487` and the
notebooks also name version `9a9670946f`. Acquisition used the explicit object
pin; it did not select latest or claim that historical version resolution worked.
The original property collection is `bed351126771f61e3d6255c18cd48aa5`.

| File | Purpose |
| --- | --- |
| [README.md](../../examples/data/mixed_use_property/README.md) | Licence, attribution text and provenance rules |
| [LICENSE](../../examples/data/mixed_use_property/LICENSE) | CC BY 4.0 for all files in the folder |
| [manifest.json](../../examples/data/mixed_use_property/manifest.json) | Source pins, capture details and, for each file, its size, SHA-256 hash, origin, description and licence |
| [transport.json.gz](../../examples/data/mixed_use_property/transport.json.gz) | All 3,007 original transport JSON records, including complete geometry and context |
| [model.json](../../examples/data/mixed_use_property/model.json) | Current canonical domain Model with source provenance |
| [mapping.json](../../examples/data/mixed_use_property/mapping.json) | Explicit classifications, units and property interpretation |
| [associations.json](../../examples/data/mixed_use_property/associations.json) | Model-scoped domain-to-original-content associations |
| [inventory.csv](../../examples/data/mixed_use_property/inventory.csv) | Derived readable inventory; source use and parent-derived effective use remain distinct |
| [relationships.csv](../../examples/data/mixed_use_property/relationships.csv) | Explicit relationship endpoints, labels and identities |
| [audit.json](../../examples/data/mixed_use_property/audit.json) | Counts, exact graph reconciliation, quantity checks and geometry-summary checks |
| [assumptions.json](../../examples/data/mixed_use_property/assumptions.json) | Separate legacy teaching assumptions and calculation conventions |
| [development.json](../../examples/data/mixed_use_property/development.json) | Teaching inputs for the development plan |
| [base_plan.json](../../examples/data/mixed_use_property/base_plan.json) | The dated plan of walkthrough lesson 03 at 2027 prices, derived from the inventory, the assumptions and the development plan |
| [origins.json](../../examples/data/mixed_use_property/origins.json) | The origin of each teaching assumption: a legacy notebook cell, a book method or the author's choice |

SDK reserialization changes content IDs for this historical payload. The package
therefore retains original transport strings. The preparation tool expanded
references and removed only redundant `__closure` indexes before it invoked the
legacy converter. All original records and indexes remain in the archive.
The resulting source checksum refers to that expanded conversion input.

The preparation tool captured, rebuilt and verified this package. It used the
legacy converter that RK no longer contains, so it is not part of the current
repository. Its source remains at revision
[`6d39b09`](https://github.com/daniel-fink/rangekeeper/blob/6d39b092e8bc7b5f71b545f6d0d5180e345b9140/tools/docs/prepare_property.py).
A new capture is source-specific extraction and
belongs to the consumer; see the [upgrade guide](upgrading.md).

Routine notebook loading only needs the canonical Model:

```python
from pathlib import Path
from rangekeeper.io import json as codec
from rangekeeper.model import Model

# Working directory: examples/walkthrough
model = codec.read(path=Path("../data/mixed_use_property/model.json"), kind=Model)
```

The source preparation [evidence](../research/notebook-02-source-2026-10-12/README.md)
records the source verification scope. The separate
[notebook acceptance](../research/notebook-02-2026-10-12/README.md) records execution,
independent financial reconciliation and local viewer/book review. Notebook 02 was
part of the interim draft book on `codex/walkthrough-acausal`.

## Notebook 03 development assumptions

[Notebook 03](https://github.com/daniel-fink/rangekeeper/blob/codex/walkthrough-acausal/examples/walkthrough/development_feasibility.ipynb) turns the
same design into a fixed development proposal. Its separate
[development inputs](../../examples/data/mixed_use_property/development.json)
are teaching assumptions. They are not measurements from the source model or
current market estimates. The source capture and its manifest remain unchanged.

The base date is 1 January 2027. Construct the shared plinth in 2027, Building A
in 2028–2029 and Building B in 2030–2031. Each package opens the following January.
Construction rates apply once to the 33 floor areas and include cores and plant.
Add soft costs and contingency separately. Periodic renewal CAPEX remains an
operating-asset expense; it does not substitute for initial construction.

Rebase the inherited rent and operating-cost rates to 2027 without an inflation
adjustment. Growth follows one calendar, while opening dates gate operations and
five operating years trigger each renewal. The holding period ends in 2036; sale
proceeds capitalise forecast 2037 NACF. Land is paid at the base date. Dated project
NPV excludes financing; the SFFA snapshot and construction funding include a
separate, fixed finance allowance.

The starting site is available for purchase and has no existing business. The
baseline is to neither acquire nor build, with zero project cash flows and no
retained asset. The fixed funding test ends in 2031, before permanent refinancing.
It checks payment capacity and remaining commitments; it does not calculate
post-refinance debt repayment or equity IRR. The permanent loan calculated by the
SFFA snapshot is not construction cash.

## Decisions deferred to later notebooks

Market drivers and correlations, feasible alternative phase boundaries, use
changes and their physical provisions, and decision rules remain explicit later
work. Do not infer them from geometry or the fixed base plan.
