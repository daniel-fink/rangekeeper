# Canonical design transport

`rangekeeper.io.speckle` encodes and decodes the canonical design envelope. It is
a pure codec. It does no authentication, network access, storage, conversion or
solving. Geometry remains outside the Model. The codec does not infer domain
membership from a service collection hierarchy.

RK contains no service transport and no legacy source conversion. A consumer that
receives design content from a service, or converts a historical payload, does that
work outside RK and creates canonical records through the public library API. See
the [upgrade guide](../guides/upgrading.md) for the removed APIs and the
[Grasshopper guide](../guides/grasshopper.md) for native authoring.

## Canonical envelope

The versioned envelope is `rk.speckle-model/v1`. Its fields are declared once in
[`speckle_contract.json`](../../src/rangekeeper/io/speckle_contract.json). The same
file generates the C# constants and drives the cross-language fixtures.

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

## Operations

| Operation | Result |
| --- | --- |
| `encode_model(model, *, associations=())` | A detached envelope dictionary. It validates association scope. It creates no SDK object, network request, store write or publication. |
| `decode_model(payload)` | An immutable canonical `Model`. It strictly decodes the envelope and validates its associations. It does not convert a legacy payload. |
| `validate_associations(model, associations)` | A copied list of valid associations, with duplicates removed. The [geometry display](../../src/rangekeeper/visualisation/geometry.py) uses it to check retained associations. |

Each operation raises `MappingError` for invalid content. The error carries the
envelope `path` and, where available, the domain `identity`. A payload without the
canonical `rk_format` value fails; it needs an explicit source reader outside RK.

Domain validation imports no service SDK or Rhino library. A successful fixture
or canonical decode is not evidence that a live service or host connector route
works.

Do not use first-match conflict resolution or infer membership from collection
nesting. Publish only after full Model validation and the required adapter/host
acceptance. C# structural/local validation does not replace Python units,
mathematical or provenance validation. The C# solution is at `src/grasshopper`;
its build and external gate are in the [Grasshopper guide](../guides/grasshopper.md)
and the [Windows acceptance procedure](../contributing/windows-acceptance.md).

## Design examples

[`rangekeeper_examples.design`](../../examples/rangekeeper_examples/design.py)
provides `author`, `formulate` and `specify`. They construct a Model, finite
mathematical declarations and a Specification respectively. Construction does not
execute or store them. Ambiguous use interpretation and missing required geometry
quantities fail; the builder does not guess them.

The [walkthrough guide](../guides/walkthroughs.md#design-example-conventions) owns
the design example's financial conventions and notebook modes. Prior external
source-consumer and pinned-service observations remain in the
[integration history](../history/source-workflows/2026-10-08-integration-record.md).
They are historical evidence, not claims of current live-service acceptance.
