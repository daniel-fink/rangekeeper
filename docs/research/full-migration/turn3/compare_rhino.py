"""Compare preserved design transport with recomputed Rhino content by explicit identity map.

Identity mapping uses classification/name plus measured geometry and child scope.
Names alone are insufficient: the example contains repeated floor/space names.
The C# authoring UUIDs derive from Rhino IDs; historical domain UUIDs remain in the
legacy conversion. The map is an acceptance artifact, not an identity rewrite.
"""

import json, math, sys
from pathlib import Path
from rangekeeper.io import json as codec
from rangekeeper.model import Model
from rangekeeper.model.content import decode
from rangekeeper.adapters.speckle import decode_model

old = codec.read(Path(sys.argv[1]), kind=Model)
envelope = json.loads(Path(sys.argv[2]).read_text())
new = decode_model(envelope)


def contents(m):
    classes = {
        c.id: c.code for t in m.definitions.taxonomies for c in t.classifications
    }
    objs = {o.id: o for o in m.find_entities()}

    def fields(o):
        quantities = {}
        properties = {}
        for v in o.characteristics.values or ():
            if v.kind == "measurement":
                quantities[v.key] = (
                    float(v.quantity.magnitude),
                    v.quantity.units.replace(" ", ""),
                )
            elif v.kind == "property":
                properties[v.key] = decode(v.content)
            else:
                raise AssertionError(v.kind)
        return quantities, properties

    def signature(uid):
        o = objs[uid]
        q, p = fields(o)
        # Rounded values select a candidate only; exact tolerance checks follow.
        base = (
            classes[o.classification],
            o.name,
            tuple(sorted((k, round(v[0], 6), v[1]) for k, v in q.items())),
        )
        members = tuple(sorted(signature(x) for x in getattr(o, "entities", ()) or ()))
        return base + (members,)

    return classes, objs, fields, signature


ac, ao, af, akey = contents(old)
bc, bo, bf, bkey = contents(new)
assert len(ao) == len(bo)
bindex = {bkey(uid): uid for uid in bo}
assert len(bindex) == len(bo), "ambiguous geometry signature"
identity = {uid: bindex[akey(uid)] for uid in ao}
assert len(set(identity.values())) == len(ao)
for uid, target in identity.items():
    a, b = ao[uid], bo[target]
    aq, ap = af(a)
    bq, bp = bf(b)
    assert aq.keys() == bq.keys(), (a.name, aq, bq)
    for key, (amount, units) in aq.items():
        actual, actual_units = bq[key]
        assert units == actual_units
        assert math.isclose(amount, actual, rel_tol=1e-10, abs_tol=1e-7), (
            a.name,
            key,
            amount,
            actual,
        )
    # Utility 'use' now records the original Rhino layer interpretation explicitly.
    if (
        ac[a.classification] == "utilities"
        and a.name != "utilities"
        and "use" not in ap
    ):
        assert bp.pop("use") == ("plant" if a.name.endswith("plant") else "cores")
    assert ap == bp, (a.name, ap, bp)
    assert {identity[x] for x in getattr(a, "entities", ()) or ()} == set(
        getattr(b, "entities", ()) or ()
    ), a.name
left = {
    (identity[r.source], identity[r.target], ac[r.classification])
    for r in old.system.relationships
}
right = {(r.source, r.target, bc[r.classification]) for r in new.system.relationships}
assert left == right, (left - right, right - left)
for association in envelope["rk_associations"]:
    assert association["domain_id"] in {str(uid) for uid in bo}
assert new.provenance.sources[0].checksum
report = {
    "status": "passed",
    "entities": len(new.system.entities),
    "assemblies": len(new.system.assemblies),
    "relationships": len(left),
    "associations": len(envelope["rk_associations"]),
    "identity_map": {str(a): str(b) for a, b in identity.items()},
    "absolute_tolerance": 1e-7,
    "relative_tolerance": 1e-10,
}
Path(sys.argv[3]).write_text(json.dumps(report, indent=2))
print({k: v for k, v in report.items() if k != "identity_map"})
