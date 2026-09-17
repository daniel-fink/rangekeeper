"""Synthetic Evidence examples; no file I/O or graph changes.

Table owns row identity/lookup. Ingestion owns content-to-Claim validation and
fingerprints; package-level imports stay stable as implementation modules evolve.
"""

from uuid import NAMESPACE_URL, uuid5

from rangekeeper.graph.adapter.ingestion import (
    Issue,
    IssueSeverity,
    fingerprint,
    tabular,
)
from rangekeeper.graph.provenance import Claim, Location, Method, Source


def identifier(key):
    return uuid5(NAMESPACE_URL, "rk-evidence-example:" + key)


def main():
    source = Source(
        id=identifier("workbook"), name="Synthetic workbook", checksum="a" * 64
    )
    rows = (identifier("row-8"), identifier("row-9"))
    keys = tuple(("rows", str(row), "area") for row in rows)
    raw = Claim.sourced(
        (("raw", 103), ("formula", None)),
        at=Location(source=source, reference={"sheet": "Units", "cell": "J8"}),
        id=identifier("raw-area"),
    )
    unit_rule = Claim.asserted(
        ("unit", "meter**2"),
        method=Method(code="area-unit", version="1"),
        id=identifier("unit-rule"),
    )
    area = Claim.derived(
        103,
        from_claims=(raw, unit_rule),
        method=Method(code="parse-area", version="1"),
        id=identifier("parsed-area"),
    )
    missing_raw = Claim.sourced(
        (("formula", "=SUM(K9:L9)"), ("cached", None)),
        at=Location(source=source, reference={"sheet": "Units", "cell": "J9"}),
        id=identifier("raw-missing"),
    )
    missing = Claim.derived(
        None,
        from_claims=(missing_raw,),
        method=Method(code="read-cache", version="1"),
        id=identifier("missing-area"),
    )
    finding = Issue(
        rule_id="read-cache",
        code="missing_formula_cache",
        severity=IssueSeverity.WARNING,
        message="The formula has no stored result.",
        at=(keys[1],),
        related_claims=(missing_raw,),
    )
    areas = tabular.from_claims(
        name="Areas",
        columns=("area",),
        row_ids=rows,
        claims=dict(zip(keys, (area, missing))),
        issues=(finding,),
    )
    reordered = tabular.from_claims(
        name="Areas",
        columns=areas.data.columns,
        row_ids=reversed(rows),
        claims=areas.claims,
        issues=areas.issues,
    )
    assert areas.data.column("area") == (103, None)
    assert reordered.data.column("area") == (None, 103)
    assert tabular.claim(reordered, rows[0], "area") is area
    assert tabular.row(areas, rows[0]) is areas.data.row(rows[0])
    print("Area:", areas.data.row(rows[0]).values["area"], "(declared unit: m²)")
    print("Missing:", tabular.issues_for(areas, rows[1])[0].code)

    candidates = tuple(
        Claim.sourced(
            value,
            at=Location(source=source, reference={"cell": cell}),
            id=identifier(cell),
        )
        for cell, value in (("C8", 2), ("D8", 3))
    )
    conflict = Claim.derived(
        None,
        from_claims=candidates,
        method=Method(code="compare-counts", version="1"),
        id=identifier("unresolved-count"),
    )
    count_key = ("rows", str(rows[0]), "bedrooms")
    counts = tabular.from_claims(
        name="Bedroom candidates",
        columns=("bedrooms",),
        row_ids=(rows[0],),
        claims={count_key: conflict},
        issues=(
            Issue(
                rule_id="compare-counts",
                code="conflicting_values",
                severity=IssueSeverity.WARNING,
                message="Two source fields disagree.",
                at=(count_key,),
                related_claims=candidates,
            ),
        ),
    )
    # Explicit synthetic review evidence; successful execution never invents it.
    decision = Claim.asserted(
        2,
        method=Method(code="user-review", version="D-example"),
        id=identifier("decision"),
    )
    selected = Claim.derived(
        2,
        from_claims=(conflict, decision),
        method=Method(code="apply-decision", version="1"),
        id=identifier("resolved-count"),
    )
    resolved = tabular.from_claims(
        name="Reviewed bedrooms",
        columns=("bedrooms",),
        row_ids=(rows[0],),
        claims={count_key: selected},
    )
    assert counts.data.column("bedrooms") == (None,)
    assert resolved.data.column("bedrooms") == (2,)
    assert selected.sources[0].sources == candidates
    print("Bedrooms: unresolved →", resolved.data.column("bedrooms")[0])
    print("Evidence fingerprint:", fingerprint(areas))


if __name__ == "__main__":
    main()
