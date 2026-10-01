"""Composition acceptance fixtures, invoked by specifications.py."""

from copy import deepcopy
import json
from uuid import NAMESPACE_URL, uuid5

from linkml_runtime.dumpers import json_dumper
from linkml_runtime.loaders import json_loader
import yaml

from expression_contract import ContractError
from specification_composition import compose_specification, specification_catalogue
from specification_contract import validate_batch, validate_specification


def check_composition(schema, validators, module, model, version, model_version):
    names = ("common", "composed-forward", "composed-inverse", "batch")
    docs = {
        name: yaml.safe_load((schema / f"examples/specification-{name}.yaml").read_text())
        for name in names
    }
    common, forward, inverse, batch = (docs[name] for name in names)
    catalogue = {d["metadata"]["id"]: d for d in docs.values()}
    before = deepcopy((docs, model))
    model_id = model["metadata"]["id"]
    common_id = common["metadata"]["id"]
    models = {model_id: model}
    accepted, rejected = 0, 0

    def uid(name):
        return str(uuid5(NAMESPACE_URL, "rk-composition-check/" + name))

    def record(name, **fields):
        return dict(metadata=dict(id=uid(name), schema_version=version), **fields)

    def compose(doc, extra=()):
        cat = dict(catalogue)
        cat.update({d["metadata"]["id"]: d for d in extra})
        # Mutated test roots deliberately replace their fixture version here.
        cat[doc["metadata"]["id"]] = doc
        for item in cat.values():
            validators["Specification"].validate(item)
        return compose_specification(doc, cat, version), cat

    def check(doc, extra=()):
        nonlocal accepted
        composition, cat = compose(doc, extra)
        validate_specification(doc, model, version, model_version, specifications=cat)
        accepted += 1
        return composition

    def reject(message, fn):
        nonlocal rejected
        try:
            fn()
        except ContractError as error:
            assert message in str(error), (message, str(error))
            rejected += 1
        else:
            raise AssertionError(f"Missing composition rejection: {message}")

    # An independently authored flat record is the oracle for each composition.
    def requirements(doc):
        view = deepcopy(doc)
        view.pop("metadata")
        for field in ("assignments", "estimates"):
            if field in view:
                view[field].sort(key=lambda a: a["value"])
        if "unknowns" in view:
            view["unknowns"].sort()
        return view

    for name, doc in (("forward", forward), ("inverse", inverse)):
        flat = yaml.safe_load((schema / f"examples/specification-{name}.yaml").read_text())
        result = check(doc)
        assert requirements(result.effective) == requirements(flat)
        assert "includes" not in result.effective
        assert result.sources[("unknowns", common["unknowns"][0])] == common_id
    paths = validate_batch(batch, models, version, model_version, specifications=catalogue)
    assert {path[-1] for path in paths} == set(batch["cases"])
    accepted += 1

    # A partial contribution is structurally valid without being executable.
    validators["Specification"].validate(common)
    reject("missing solve role", lambda: check(common))
    empty = record("partial")
    validators["Specification"].validate(empty)
    assert compose(empty)[0].effective == empty
    reject("requires an input Model", lambda: check(empty))

    left = record("left", includes=[common_id])
    right = record("right", includes=[common_id])
    diamond = deepcopy(forward)
    diamond["includes"] = [left["metadata"]["id"], right["metadata"]["id"]]
    result = check(diamond, (left, right))
    assert len(result.contributors) == 4
    reversed_diamond = deepcopy(diamond)
    reversed_diamond["includes"].reverse()
    assert check(reversed_diamond, (left, right)).effective == result.effective
    # Repeating the agreed Model pin is a scope assertion, not an overwrite.
    with_model = deepcopy(forward)
    with_model["model"] = model_id
    check(with_model)
    split_settings = deepcopy(forward)
    time_limit = split_settings["settings"].pop("time_limit")
    timing = record("timing", settings=dict(time_limit=time_limit))
    split_settings["includes"].append(timing["metadata"]["id"])
    assert check(split_settings, (timing,)).effective["settings"] == forward["settings"]

    rent = forward["assignments"][0]
    target = rent["value"]
    for label, fields in (
        ("equal assignment", dict(assignments=[deepcopy(rent)])),
        ("different assignment", dict(assignments=[dict(value=target, quantity=dict(magnitude=1, units=rent["quantity"]["units"]))])),
        ("unknown role", dict(unknowns=[forward["unknowns"][0]])),
        ("setting", dict(settings=dict(time_limit=forward["settings"]["time_limit"]))),
    ):
        extra = record(label, **fields)
        bad = deepcopy(forward)
        bad["includes"].append(extra["metadata"]["id"])
        reject("multiple contributors", lambda: check(bad, (extra,)))
    conflict = record("role-conflict", unknowns=[target])
    bad = deepcopy(forward)
    bad["includes"].append(conflict["metadata"]["id"])
    reject("roles overlap", lambda: check(bad, (conflict,)))
    duplicate_estimate = record("estimate", estimates=deepcopy(inverse["estimates"]))
    bad = deepcopy(inverse)
    bad["includes"].append(duplicate_estimate["metadata"]["id"])
    reject("multiple contributors", lambda: check(bad, (duplicate_estimate,)))

    # Estimates and the corresponding unknown may have different contributors.
    split = deepcopy(inverse)
    split.pop("estimates")
    split["includes"].append(duplicate_estimate["metadata"]["id"])
    check(split, (duplicate_estimate,))
    for field in ("includes", "cases"):
        bad = deepcopy(batch if field == "cases" else forward)
        bad[field].append(bad[field][0])
        reject(f"duplicate {field}", lambda: compose(bad))

    for field in ("includes", "cases"):
        bad = deepcopy(batch if field == "cases" else forward)
        bad[field] = [uid("missing")]
        reject("unresolved Specification", lambda: compose(bad))
        bad[field] = [bad["metadata"]["id"]]
        reject("cycle", lambda: compose(bad))
    a, b = record("cycle-a"), record("cycle-b")
    a["includes"] = [b["metadata"]["id"]]
    b["includes"] = [a["metadata"]["id"]]
    reject("cycle", lambda: compose(a, (b,)))
    # A mixed case/include cycle is invalid too, not only separate edge cycles.
    a.pop("includes")
    a["cases"] = [b["metadata"]["id"]]
    reject("cycle", lambda: compose(a, (b,)))
    bad = record("includes-batch", includes=[batch["metadata"]["id"]])
    reject("cannot include a batch", lambda: compose(bad))

    for field, content in (("includes", [common_id]), ("unknowns", [target]),
                           ("assignments", [rent]), ("settings", {"time_limit": 1})):
        bad = deepcopy(batch)
        bad[field] = content
        reject("batch cannot", lambda: compose(bad))
    bad = deepcopy(batch)
    bad["model"] = uid("different-model")
    cat = dict(catalogue, **{bad["metadata"]["id"]: bad})
    reject("batch input Model assertion", lambda: validate_batch(bad, models, version, model_version, specifications=cat))
    # A batch Model pin does not repair an incomplete case.
    missing_model = deepcopy(forward)
    missing_model.pop("includes")
    cat = dict(catalogue, **{missing_model["metadata"]["id"]: missing_model})
    reject("requires an input Model", lambda: validate_batch(batch, models, version, model_version, specifications=cat))
    reject("unresolved input Model", lambda: validate_batch(batch, {}, version, model_version, specifications=catalogue))
    reject("batch is not one", lambda: validate_specification(batch, model, version, model_version, specifications=catalogue))
    outer = record("outer-batch", cases=[batch["metadata"]["id"], forward["metadata"]["id"]])
    nested_paths = validate_batch(outer, models, version, model_version, specifications=catalogue)
    assert len(nested_paths) == 3 and len(set(nested_paths)) == 3
    accepted += 1
    collision_batch = deepcopy(batch)
    collision_batch["metadata"]["id"] = model_id
    reject(
        "duplicate identity",
        lambda: validate_batch(
            collision_batch, models, version, model_version, specifications=catalogue
        ),
    )

    # Omission/empty lists are neutral; objectives are supplied as a whole.
    optimization = yaml.safe_load((schema / "examples/specification-objectives.yaml").read_text())
    criteria = record("criteria", objectives=optimization.pop("objectives"))
    optimization["includes"] = [criteria["metadata"]["id"]]
    optimization["objectives"] = []
    result = check(optimization, (criteria,))
    assert result.effective["objectives"] == criteria["objectives"]
    transported = json.loads(json_dumper.dumps(
        json_loader.loads(json.dumps(optimization), target_class=module.Specification),
        inject_type=False,
    ))
    # The native dumper omits the empty local list; included preference order stays.
    assert check(transported, (criteria,)).effective == result.effective
    competing = record("competing-criteria", objectives=deepcopy(criteria["objectives"]))
    optimization["includes"].append(competing["metadata"]["id"])
    reject("multiple contributors for objectives", lambda: check(optimization, (criteria, competing)))

    # Additional mathematics accumulates even when jointly infeasible.
    false_requirement = record("false", formulations=[dict(
        id=uid("false-formulation"),
        expressions=[dict(id=uid("false-expression"), kind="boolean", boolean=False)],
        constraints=[dict(id=uid("false-constraint"), predicate=uid("false-expression"))],
    )])
    constrained = deepcopy(forward)
    constrained["includes"].append(false_requirement["metadata"]["id"])
    check(constrained, (false_requirement,))
    duplicate_math = deepcopy(false_requirement)
    duplicate_math["metadata"]["id"] = uid("duplicate-math")
    constrained["includes"].append(duplicate_math["metadata"]["id"])
    reject("duplicate identity", lambda: check(constrained, (false_requirement, duplicate_math)))

    # Cross-contributor references resolve in the effective mathematical scope.
    opt = yaml.safe_load((schema / "examples/specification-optimization.yaml").read_text())
    maths = record("maths", formulations=opt.pop("formulations"))
    opt["includes"] = [maths["metadata"]["id"]]
    check(opt, (maths,))
    # Version, wrong-kind and catalogue identity checks are not UUID-shape checks.
    bad_version = deepcopy(common)
    bad_version["metadata"]["schema_version"] = "99"
    reject("unsupported Specification", lambda: compose(forward, (bad_version,)))
    bad_cat = dict(catalogue)
    bad_cat[common_id] = deepcopy(common)
    bad_cat[common_id]["metadata"]["id"] = uid("mismatch")
    reject("catalogue identity mismatch", lambda: specification_catalogue(forward, bad_cat, version))
    bad_cat[common_id] = model
    reject("must resolve to a Specification", lambda: specification_catalogue(forward, bad_cat, version))
    bad_cat = dict(catalogue)
    bad_cat[forward["metadata"]["id"]] = inverse
    reject("different content", lambda: specification_catalogue(forward, bad_cat, version))
    bad_model = deepcopy(common)
    bad_model["model"] = uid("another-model")
    reject("conflicting input Model", lambda: compose(with_model, (bad_model,)))
    renamed = deepcopy(forward)
    renamed["metadata"].update(name="Only a display rename", previous=common_id)
    renamed.pop("includes")
    reject("requires an input Model", lambda: check(renamed))
    # Included Metadata identities also cannot collide with Model declarations.
    collision = record("collision")
    collision["metadata"]["id"] = model["system"]["entities"][0]["id"]
    bad = deepcopy(forward)
    bad["includes"].append(collision["metadata"]["id"])
    reject("duplicate identity", lambda: check(bad, (collision,)))

    # Actual generated Python references survive round trips. Incomplete records
    # are allowed to serialize; only the completed investigations are executable.
    restored = {}
    for doc in docs.values():
        validators["Specification"].validate(doc)
        obj = json_loader.loads(json.dumps(doc), target_class=module.Specification)
        assert all(isinstance(ref, module.MetadataId) for ref in obj.includes + obj.cases)
        after = json.loads(json_dumper.dumps(obj, inject_type=False))
        assert after == doc, (doc, after)
        validators["Specification"].validate(after)
        restored[after["metadata"]["id"]] = after
    assert validate_batch(restored[batch["metadata"]["id"]], models, version, model_version, specifications=restored) == paths
    assert (docs, model) == before
    print(f"Passed {accepted} composition/batch acceptance checks, {rejected} composition rejections,")
    print(f"and {len(docs)} additional native round trips; no inputs mutated or solver executed.")
