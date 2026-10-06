"""Strict comparison of preserved workflow Graph content with a canonical Model.

Run separately from source builds. The old wire decoder is explicit; no reference
artifact enters workflow construction. Only named representation changes are
normalized. Real payloads stay in the private artifact directory.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
from uuid import UUID, NAMESPACE_URL, uuid5
from rangekeeper.io import json as codec
from rangekeeper.model import Model
from rangekeeper.migration.graph import convert_graph
from rangekeeper.model.provenance import locations


def neutral(model):
    data = model.to_data()
    assert set(data["system"]) <= {"entities", "assemblies", "relationships"}, (
        "unsupported System content"
    )
    definitions = data["definitions"]
    spelling = {"foot**2": "foot ** 2", "meter**2": "meter ** 2"}
    for measure in definitions.get("measures", []):
        measure["units"] = spelling.get(measure["units"], measure["units"])
        # Legacy YAML uses enum names; the old wire format stores enum values.
        measure["tags"] = sorted(
            t.lower()
            if t.startswith(("legacy.quantity_kind:", "legacy.aggregation:"))
            else t
            for t in measure.get("tags", [])
        )
    for taxonomy in definitions.get("taxonomies", []):
        for item in taxonomy["classifications"]:
            item.setdefault(
                "parent", None
            )  # The old decoder omits a root's null parent.
        taxonomy["classifications"] = sorted(
            taxonomy["classifications"], key=lambda c: c["id"]
        )
    for kind in definitions:
        definitions[kind] = sorted(definitions[kind], key=lambda c: c["id"])
    result = {"definitions": definitions, "objects": {}, "relationships": {}}
    for kind in ("entities", "assemblies", "relationships"):
        for original in data["system"].get(kind, []):
            item = dict(original)
            chars = item.pop("characteristics", {}) or {}
            item["values"] = {v["key"]: v for v in chars.get("values", [])}
            for value in item["values"].values():
                if value.get("quantity"):
                    q = value["quantity"]
                    q["units"] = spelling.get(q["units"], q["units"])
            item["labels"] = {v["key"]: v for v in chars.get("labels", [])}
            for label in item["labels"].values():
                label["classifications"] = sorted(label.get("classifications", []))
            for field in ("entities", "relationships"):
                if field in item:
                    item[field] = sorted(item[field])
            item["kind"] = kind
            result["relationships" if kind == "relationships" else "objects"][
                item["id"]
            ] = item
    return result


def support_index(model):
    facts = {f.target: f for f in model.provenance.facts or ()}
    claims = {c.id: c for c in model.provenance.claims or ()}
    sources = {s.id: s for s in model.provenance.sources or ()}
    memo = {}

    def parents(uid):
        if uid in memo:
            return memo[uid]
        claim = claims[uid]
        source_rows, decisions = set(), set()
        if claim.method and claim.method.code == "reviewed-decision":
            payload = claim.content
            encoded = payload["value"]
            if payload["encoding"] == "rk.source-value/v1":
                assert encoded[0] == "str"
                encoded = encoded[1]
            decisions.add(json.dumps(json.loads(encoded), sort_keys=True))
        for s in claim.sources or ():
            if isinstance(s, UUID):
                rows, records = parents(s)
                source_rows.update(rows)
                decisions.update(records)
            else:
                source = sources[s.source]
                if source.name == "workflow specification" and set(s.address or {}) <= {
                    "files",
                    "configuration",
                }:
                    continue
                source_rows.add(
                    json.dumps(
                        [source.name, source.checksum, dict(s.address or {})],
                        sort_keys=True,
                    )
                )
        memo[uid] = (frozenset(source_rows), frozenset(decisions))
        return memo[uid]

    result = {}
    for target, fact in facts.items():
        rows, records = set(), set()
        for uid in fact.claims:
            source, decisions = parents(uid)
            rows.update(source)
            records.update(decisions)
        result[str(target)] = (sorted(rows), sorted(records))
    return result


def compare(reference, candidate, namespace):
    conversion = convert_graph((reference / "graph.json").read_text())
    assert conversion.model is not None, conversion.issues
    before = conversion.model
    after = codec.read(candidate / "model.json", kind=Model)
    a, b = neutral(before), neutral(after)
    identities = {}
    additions = []
    for group in ("objects", "relationships"):
        assert set(a[group]) == set(b[group]), group
        for uid, left in a[group].items():
            right = b[group][uid]
            for key, value in left["values"].items():
                expected = str(
                    uuid5(
                        uuid5(NAMESPACE_URL, namespace),
                        json.dumps(["value", f"{uid}:{key}"], ensure_ascii=False),
                    )
                )
                assert right["values"][key]["id"] == expected, (uid, key)
                identities[value["id"]] = expected
                value["id"] = expected
            # V2 retains declared unresolved measurements that V1 omitted. An
            # extra quantity or property is never accepted by this allowance.
            for key, value in right["values"].items():
                if key not in left["values"]:
                    assert (
                        value["kind"] == "measurement" and value.get("quantity") is None
                    ), (uid, key, value)
                    additions.append({"owner": uid, "key": key, "id": value["id"]})
                    left["values"][key] = value
            assert left == right, ("domain", uid, left, right)
    assert a["definitions"] == b["definitions"], "definitions"
    lineage = []
    old_support, new_support = support_index(before), support_index(after)
    for fact in before.provenance.facts:
        old = str(fact.target)
        new = identities.get(old, old)
        assert old_support[old] == new_support[new], ("support", old, new)
        lineage.append([old, new])
    old = json.loads((reference / "checks.json").read_text())
    new = json.loads((candidate / "checks.json").read_text())

    def rewrite(value):
        if isinstance(value, str):
            return identities.get(value, value)
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        if isinstance(value, dict):
            return {k: rewrite(v) for k, v in value.items()}
        return value

    old = rewrite(old)

    # Configuration rendering changes are exact, not broad source exclusions.
    def normalize_checks(data):
        for section in ("checks", "source_checks", "findings"):
            for row in data.get(section, []):
                row["references"] = sorted(
                    r
                    for r in row.get("references", [])
                    if not r.startswith('workflow specification · {"files":')
                )
                for field in ("targets", "left_members", "right_members"):
                    if field in row:
                        row[field] = sorted(row[field])
        return data

    old, new = normalize_checks(old), normalize_checks(new)
    assert len(old["checks"]) == len(new["checks"])
    new_null_ids = {row["id"] for row in additions}
    for left, right in zip(old["checks"], new["checks"]):
        if left.get("explanation") == "Graph structural invariant":
            left["explanation"] = "Model structural invariant"
        # V1 omitted these exact unresolved Values. V2 checks can identify them
        # without inventing a quantity or changing the check's unavailable status.
        if (
            left.get("targets") == []
            and right.get("targets")
            and set(right["targets"]) <= new_null_ids
        ):
            assert left["status"] == right["status"] == "unavailable"
            left["targets"] = right["targets"]
    assert old == new, "checks/findings/source references"
    return {
        "domain_equal": True,
        "lineage_equal": True,
        "checks_equal": True,
        "identity_map": identities,
        "retained_null_measurements": additions,
        "facts_compared": len(lineage),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--namespace", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = compare(args.reference, args.candidate, args.namespace)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        {
            k: v
            for k, v in result.items()
            if k not in ("identity_map", "retained_null_measurements")
        }
    )
