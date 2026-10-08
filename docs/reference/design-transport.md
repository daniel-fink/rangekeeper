# Canonical design transport

`rangekeeper.adapters.speckle` separates authenticated acquisition, canonical
mapping and explicit legacy conversion. Geometry remains outside the Model.
Transport does not infer domain membership from a service collection hierarchy.
See the [Grasshopper guide](../guides/grasshopper.md) for native authoring and the
[upgrade guide](../guides/upgrading.md) for historical payloads.

## Canonical envelope

The versioned envelope is `rk.speckle-model/v1`. Its fields are declared once in
[`adapters/speckle/contract.json`](../../src/rangekeeper/adapters/speckle/contract.json)
and also generate the C# constants.

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

`encode_model(model, *, associations=())` returns a detached envelope dictionary.
It validates association scope and creates no SDK object, network request, store
write or publication. `decode_model(payload)` strictly decodes and validates a
canonical Model and its associations. Invalid envelopes raise `MappingError` with
path and identity where available. It does not silently convert legacy payloads.

## Pinned acquisition

`adapters.speckle.transport.receive(client, *, project_id, version_id=None,
object_id=None)` requires an authenticated client and exactly one version or object
pin. It returns immutable detached `Received(payload, source)` data. Source metadata
records project, requested version, resolved object and installed SDK version.
Authentication and the configured SDK's cache behavior belong to the caller.

Unavailable content raises `TransportError`. A version with no readable object
reference is an explicit failure. The adapter never selects a latest version or
falls back to another object pin. An independently recorded object pin is usable
only when it identifies the intended source. Receiving does not decode, convert,
persist, solve or publish the content.

Domain validation imports no service SDK or Rhino library. The service SDK loads
at the explicit transport boundary. A successful fixture or canonical decode is
not evidence that a live service or host connector route works.

## Explicit legacy conversion

`migration.speckle.convert_speckle(payload, *, mapping, revision_id=None)` returns
`ConversionResult(model, issues, associations, source_sha256)`. It is pure and
requires reviewed mappings. Conversion preserves supported domain UUIDs, merges
identical repeats and permits an Entity/Assembly duplicate only when shared
content agrees. It preserves supported rich properties and source Claims.
Conflicts, unsupported fields and unresolved references produce issues and no
partial Model. Inputs remain unchanged.

Do not use first-match conflict resolution or infer membership from collection
nesting. Publish only after full Model validation and the required adapter/host
acceptance. C# structural/local validation does not replace Python units,
mathematical or provenance validation. The C# solution now belongs at
`src/grasshopper`; its build and external gate are documented in the
[Grasshopper guide](../guides/grasshopper.md) and
[Windows acceptance procedure](../contributing/windows-acceptance.md).

## Design examples and execution limits

The maintained design notebooks under
[`examples/walkthrough`](../../examples/walkthrough) declare `RK_DESIGN_MODE` as
`fixture`, `live` or `canonical`. They do not switch modes after failure. Fixture
mode supports routine fresh-wheel checks. Live mode needs explicit pins and
credentials; neither notebook publishes.

`rangekeeper_examples.design.author`, `formulate` and `specify` construct a Model,
finite mathematical declarations and a Specification respectively. Construction
does not execute or store them. Ambiguous use interpretation and missing required
geometry quantities fail rather than being guessed. The financial notebook has
an explicit solve budget, overridable with `RK_DESIGN_TIME_LIMIT`; authoring is a
separate step. See [walkthroughs](../guides/walkthroughs.md) and
[execution](execution.md) for use and acceptance.

The [walkthrough guide](../guides/walkthroughs.md#design-example-conventions) owns
the design example's financial conventions. Prior external source-consumer and
pinned-service observations remain in the
[integration history](../history/source-workflows/2026-10-08-integration-record.md).
They are historical evidence, not claims of current live-service acceptance.
