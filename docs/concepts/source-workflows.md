# Source interpretation and reproducibility

Applications interpret source observations and create canonical RK Models through
public authoring APIs. RK owns the resulting records, identity, validation and
provenance. It does not provide an ingestion service or workflow runner.
The mathematical `Specification` and finalized `Run` remain distinct from a
consumer's source-processing configuration and operation records.

## Source interpretation

Retain the exact source edition and native location for an observation. Record
the mapping or decision that turns it into Model content. Use the canonical
Source, Location, Claim and Fact records from the
[provenance schema](../../schema/provenance.yaml). A relationship between an Entity
and a geometry object is not a substitute for evidence supporting its properties.

Preserve missing values, unresolved interpretation, zero and false as distinct
states. A successful parse does not establish the meaning or completeness of the
source. Review ambiguous mappings before treating the result as accepted content.

## Reproducible construction

| Input | Required content |
| --- | --- |
| Sources | Exact retained editions and checksums; a mutable URL is insufficient. |
| Decisions | Explicit mappings, selections, business identities, unresolved cases and policies. |
| Code | The implementations and supporting files used to construct the Model. |
| Environment | Exact library and dependency versions, with any solver or provider pins. |

Reconstruction must not depend on chat history, hidden notebook state, wall-clock
defaults or a previous successful output. A missing input must not be replaced
silently by cached output. Rebuild in a fresh environment and compare canonical
content, identities and provenance, including changed editions and failed inputs.

## Identity and acceptance

A source edition, an observation within it and a business object have different
identities. Reordering source rows must not accidentally replace the apartment or
asset that they describe. A changed source claim can still change Model content
and its revision. Keep the previous revision and its source support intact.

Structural validation and repeatability do not establish correct interpretation
or physical completeness. Compare outputs against independent expectations.
Source interpretation does not certify a numerical solution; use the separate
[execution contract](../reference/execution.md) for mathematical investigations.
