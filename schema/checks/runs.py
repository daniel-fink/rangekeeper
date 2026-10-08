"""Check synthetic Run records, references, publication, and native round trips.

No scheduler or solver executes. The scalar fixture amounts are independently
asserted arithmetic expectations, not results of a generic evaluation adapter.
"""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from uuid import NAMESPACE_URL, uuid5

from jsonschema import FormatChecker
from jsonschema.validators import validator_for
from linkml_runtime.dumpers import json_dumper
from linkml_runtime.loaders import json_loader
from linkml_runtime.utils.schemaview import SchemaView
import yaml

import _library

from rangekeeper.shared.errors import ContractError
from rangekeeper.run.report import instant
from rangekeeper.run.validation import validate_records
from rangekeeper.schema.index import walk_data


def records(system):
    return (record for record, _ in walk_data("System", system))


SCHEMA = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
VERSIONS = [
    yaml.safe_load((SCHEMA / f"{name}.yaml").read_text())["version"]
    for name in ("run", "specification", "model")
]


def uid(name):
    return str(uuid5(NAMESPACE_URL, "rk-run-check/" + name))


validators = {}
for cls in (
    "Run",
    "Report",
    "Status",
    "Runtime",
    "Implementation",
    "Diagnostic",
    "Step",
    "Settings",
    "Model",
    "Specification",
):
    schema_name = {"Model": "model", "Specification": "specification"}.get(cls, "run")
    generated = json.loads(_library.schema_json(cls))
    validator = validator_for(generated)
    validator.check_schema(generated)
    validators[cls] = validator(generated, format_checker=FormatChecker())
view = SchemaView(str(SCHEMA / "run.yaml"))
assert [name for name, cls in view.all_classes().items() if cls.tree_root] == ["Run"]
assert view.get_identifier_slot("Run") is None
assert view.get_identifier_slot("Metadata").name == "id"
assert view.get_class("Settings").from_schema.endswith("/settings")
for owner, field in (
    ("Run", "specification"),
    ("Run", "spawns"),
    ("Run", "outputs"),
    ("Diagnostic", "document"),
    ("Step", "document"),
):
    slot = view.induced_slot(field, owner)
    assert slot.range == "Metadata" and slot.inlined is False
assert view.induced_slot("trace", "Report").list_elements_ordered
assert not view.induced_slot("spawns", "Run").list_elements_ordered


def load(name):
    return yaml.safe_load((SCHEMA.parent / "examples/schema" / f"{name}.yaml").read_text())


base = dict(
    runs={
        d["metadata"]["id"]: d
        for d in (
            load("run-" + name)
            for name in ("forward", "inverse", "batch", "failed", "skipped")
        )
    },
    specifications={
        d["metadata"]["id"]: d
        for d in (
            yaml.safe_load(p.read_text())
            for p in (SCHEMA.parent / "examples/schema").glob("specification-*.yaml")
        )
    },
    models={
        d["metadata"]["id"]: d
        for d in (
            load(name)
            for name in ("model", "model-forward-output", "model-inverse-output")
        )
    },
)
ids = {
    name: load("run-" + name)["metadata"]["id"]
    for name in ("forward", "inverse", "batch", "failed", "skipped")
}
mid = load("model")["metadata"]["id"]
fmid = load("model-forward-output")["metadata"]["id"]
imid = load("model-inverse-output")["metadata"]["id"]
valid, structural, semantic = [], [], []


def shape(bundle):
    for cls, field in (
        ("Run", "runs"),
        ("Specification", "specifications"),
        ("Model", "models"),
    ):
        for doc in bundle[field].values():
            validators[cls].validate(doc)


def check(root, bundle):
    before = deepcopy(bundle)
    shape(bundle)
    validate_records(bundle["runs"][root], **bundle).raise_if_invalid()
    visited = set()

    def visit(identity):
        if identity in visited:
            return
        visited.add(identity)
        for child in bundle["runs"][identity].get("spawns") or ():
            visit(child)

    visit(root)
    assert bundle == before
    return visited


def good(root, edit=lambda bundle, run: None):
    bundle = deepcopy(base)
    edit(bundle, bundle["runs"][ids[root]])
    check(ids[root], bundle)
    valid.append((ids[root], bundle))


def bad(message, edit, root="forward"):
    bundle = deepcopy(base)
    edit(bundle, bundle["runs"][ids[root]])
    shape(bundle)
    report = validate_records(bundle["runs"][ids[root]], **bundle)
    assert not report.valid and any(
        message in issue.message for issue in report.issues
    ), (message, report)
    semantic.append(message)


def malformed(edit):
    run = deepcopy(base["runs"][ids["forward"]])
    edit(run)
    assert not validators["Run"].is_valid(run), run
    structural.append(run)


def outcome(run, completion, solution, keep_output=False):
    run["report"]["status"] = dict(completion=completion, solution=solution)
    run["report"]["diagnostics"] = [
        dict(
            severity="warning",
            code="synthetic_outcome",
            message="Synthetic recorded termination or mathematical conclusion; not observed execution.",
        )
    ]
    if not keep_output:
        run.pop("outputs", None)
        run["report"].pop("trace", None)


for name in ids:
    good(name)
for completion, solution in (
    ("limited", "unknown"),
    ("limited", "not_assessed"),
    ("completed", "unknown"),
    ("completed", "infeasible"),
    ("cancelled", "unknown"),
):
    good("forward", lambda b, r, c=completion, s=solution: outcome(r, c, s))
good("forward", lambda b, r: outcome(r, "limited", "feasible", True))


def partial(bundle, run):
    run["spawns"][1] = ids["failed"]
    run["outputs"] = [fmid]
    outcome(run, "partial", "not_applicable", True)


good("batch", partial)


def all_skipped(bundle, run):
    for ref in run["spawns"]:
        child = bundle["runs"][ref]
        outcome(child, "skipped", "not_assessed")
        child["report"].pop("runtime", None)
    outcome(run, "skipped", "not_applicable")


good("batch", all_skipped)


def nested(repeated=False):
    bundle = deepcopy(base)
    spec = dict(
        metadata=dict(id=uid("outer-spec"), schema_version=VERSIONS[1]),
        cases=[base["runs"][ids["batch"]]["specification"]],
    )
    run = dict(
        metadata=dict(id=uid("outer-run"), schema_version=VERSIONS[0]),
        specification=spec["metadata"]["id"],
        spawns=[ids["batch"]],
        outputs=[fmid, imid],
        report=dict(status=dict(completion="completed", solution="not_applicable")),
    )
    if repeated:
        extra = deepcopy(base["runs"][ids["forward"]])
        extra["metadata"]["id"] = uid("repeated-forward")
        out = deepcopy(base["models"][fmid])
        out["metadata"]["id"] = uid("repeated-output")
        extra["outputs"] = [out["metadata"]["id"]]
        for item in extra["report"]["diagnostics"] + extra["report"]["trace"]:
            if item.get("document") == fmid:
                item["document"] = out["metadata"]["id"]
        bundle["runs"][extra["metadata"]["id"]] = extra
        bundle["models"][out["metadata"]["id"]] = out
        spec["cases"].append(extra["specification"])
        run["spawns"].append(extra["metadata"]["id"])
        run["outputs"].append(out["metadata"]["id"])
    bundle["specifications"][spec["metadata"]["id"]] = spec
    bundle["runs"][run["metadata"]["id"]] = run
    check(run["metadata"]["id"], bundle)
    valid.append((run["metadata"]["id"], bundle))


nested()
nested(True)


def unsupported(bundle, run):
    spec = deepcopy(bundle["specifications"][run["specification"]])
    spec.pop("includes")
    spec["metadata"]["id"] = uid("incomplete-spec")
    bundle["specifications"][spec["metadata"]["id"]] = spec
    run["specification"] = spec["metadata"]["id"]
    outcome(run, "failed", "not_assessed")
    run["report"].pop("runtime")
    run["report"]["diagnostics"][0]["code"] = "specification_invalid"


good("forward", unsupported)


def settings_changed(bundle, run):
    run["report"]["runtime"]["settings"]["iteration_limit"] = 50
    run["report"]["diagnostics"].append(
        dict(
            severity="warning",
            code="settings_adjusted",
            message="iteration_limit requested as 100; effective 50 under the documented synthetic adapter limit.",
        )
    )


good("forward", settings_changed)


def inverse_on_recorded(bundle, run):
    spec = load("specification-inverse")
    spec["metadata"].update(id=uid("recorded-spec"), previous=spec["metadata"]["id"])
    spec["model"] = fmid
    bundle["specifications"][spec["metadata"]["id"]] = spec
    run["specification"] = spec["metadata"]["id"]
    bundle["models"][imid]["metadata"]["previous"] = fmid


good("inverse", inverse_on_recorded)


def optimization(bundle, run):
    spec = load("specification-optimization")
    run["specification"] = spec["metadata"]["id"]
    for r in records(bundle["models"][fmid]["system"]):
        if r.get("key") in ("annual_rent_per_home", "NOI", "capital_value"):
            r["quantity"]["magnitude"] = {
                "annual_rent_per_home": 32000,
                "NOI": 590000,
                "capital_value": 11800000,
            }[r["key"]]
    run["report"]["trace"].insert(
        -1,
        dict(
            kind="selection",
            message="Synthetic automatic selection using the stated objective and rent ceiling; no general optimality proof or observed solver result is asserted.",
            document=fmid,
        ),
    )


good("forward", optimization)

# Structural failures: missing content, invalid references/enums, and diagnostic guards.
for field in ("metadata", "specification", "report"):
    malformed(lambda r, f=field: r.pop(f))
for field in ("children", "runs", "subruns", "model", "selection", "execution"):
    malformed(lambda r, f=field: r.update({f: []}))
for value in ("forward", {"id": uid("embedded")}, 42):
    malformed(lambda r, v=value: r.update(specification=v))
for field in ("spawns", "outputs"):
    malformed(lambda r, f=field: r.update({f: ["not-a-uuid"]}))
malformed(lambda r: r["report"].pop("status"))
for field in ("completion", "solution"):
    malformed(lambda r, f=field: r["report"]["status"].pop(f))
malformed(lambda r: r["report"]["status"].update(completion="running"))
malformed(lambda r: r["report"]["status"].update(solution="optimal"))
malformed(lambda r: r["report"]["runtime"]["implementations"][0].pop("version"))
malformed(lambda r: r["report"]["runtime"]["implementations"][0].update(kind="worker"))
malformed(lambda r: r["report"]["runtime"].update(started_at="2026-10-01T00:00:00"))
malformed(lambda r: r["report"]["runtime"].update(settings=dict(iteration_limit=-1)))
malformed(lambda r: r["report"]["diagnostics"][0].pop("document"))
malformed(lambda r: r["report"]["diagnostics"][0].pop("residual"))
malformed(lambda r: r["report"]["diagnostics"][0]["tolerance"].update(magnitude=True))
malformed(lambda r: r["report"]["trace"][-1].pop("document"))
malformed(lambda r: r["report"]["trace"][0].update(kind="policy"))

# Semantic failures that generated shape validation cannot establish.
bad("unsupported Run", lambda b, r: r["metadata"].update(schema_version="99"))
bad("unresolved Specification", lambda b, r: r.update(specification=uid("missing")))
bad("must resolve to Specification", lambda b, r: r.update(specification=mid))
bad("unresolved Run", lambda b, r: r.update(spawns=[uid("missing-run")]))
bad("spawn cycle", lambda b, r: r.update(spawns=[r["metadata"]["id"]]))
bad("duplicate spawns", lambda b, r: r["spawns"].append(r["spawns"][0]), "batch")
bad("duplicate outputs", lambda b, r: r["outputs"].append(r["outputs"][0]))
bad("each direct case", lambda b, r: r["spawns"].pop(), "batch")
bad("each direct case", lambda b, r: r["spawns"].append(ids["failed"]), "batch")
bad("output union", lambda b, r: r["outputs"].pop(), "batch")
bad(
    "completion disagrees",
    lambda b, r: r["report"]["status"].update(completion="partial"),
    "batch",
)
bad(
    "batch solution",
    lambda b, r: r["report"]["status"].update(solution="feasible"),
    "batch",
)
bad(
    "invalid non-batch", lambda b, r: r["report"]["status"].update(completion="partial")
)
bad("invalid non-batch", lambda b, r: r["report"]["status"].update(completion="failed"))
bad("outputs require feasible", lambda b, r: r.pop("outputs"))
bad("outputs require feasible", lambda b, r: r.update(outputs=[fmid]), "failed")
bad("runtime evidence", lambda b, r: r["report"].pop("runtime"))
bad(
    "skipped Run cannot have runtime",
    lambda b, r: r["report"].update(
        runtime=deepcopy(base["runs"][ids["inverse"]]["report"]["runtime"])
    ),
    "skipped",
)
bad("explanatory diagnostic", lambda b, r: r["report"].pop("diagnostics"), "failed")
bad(
    "duplicate implementation",
    lambda b, r: r["report"]["runtime"]["implementations"].append(
        deepcopy(r["report"]["runtime"]["implementations"][0])
    ),
)
bad(
    "finishes before start",
    lambda b, r: r["report"]["runtime"].update(finished_at="2026-09-30T00:00:00Z"),
)
bad(
    "positive finite",
    lambda b, r: r["report"]["runtime"]["settings"].update(time_limit=0),
)
bad(
    "less than one",
    lambda b, r: r["report"]["runtime"]["settings"].update(relative_tolerance=1),
)
bad(
    "unaccounted requested setting",
    lambda b, r: r["report"]["runtime"]["settings"].update(iteration_limit=99),
)
bad(
    "unresolved report document",
    lambda b, r: r["report"]["diagnostics"][0].update(document=uid("missing-document")),
)
bad(
    "outside document scope",
    lambda b, r: r["report"]["diagnostics"][0].update(document=r["specification"]),
)
bad(
    "non-finite",
    lambda b, r: r["report"]["diagnostics"][0]["residual"].update(
        magnitude=float("inf")
    ),
)
bad(
    "negative diagnostic tolerance",
    lambda b, r: r["report"]["diagnostics"][0]["tolerance"].update(magnitude=-1),
)
bad(
    "unit conversion requires adapter",
    lambda b, r: r["report"]["diagnostics"][0]["tolerance"].update(units="USD"),
)
bad("trace times out of order", lambda b, r: r["report"]["trace"].reverse())
bad(
    "trace before runtime",
    lambda b, r: r["report"]["trace"][0].update(at="2026-09-30T00:00:00Z"),
)
bad(
    "trace after runtime",
    lambda b, r: r["report"]["trace"][-1].update(at="2026-10-02T00:00:00Z"),
)
bad(
    "trace requires accepted output",
    lambda b, r: r["report"]["trace"][-1].update(document=mid),
)
bad("output cannot be input", lambda b, r: r.update(outputs=[mid]))
bad("unresolved Model", lambda b, r: r.update(outputs=[uid("missing-output")]))
bad("output lineage", lambda b, r: b["models"][fmid]["metadata"].pop("previous"))
bad(
    "preserve input definitions",
    lambda b, r: b["models"][fmid]["system"]["entities"][0].update(name="Changed name"),
)


def output_value(bundle, key):
    return next(
        v for v in records(bundle["models"][fmid]["system"]) if v.get("key") == key
    )


bad("unresolved solve Value", lambda b, r: output_value(b, "NOI").pop("quantity"))
bad(
    "violates assignment",
    lambda b, r: output_value(b, "homes")["quantity"].update(magnitude=21),
)
bad(
    "unrelated recorded content",
    lambda b, r: output_value(b, "floor_area").update(
        quantity=dict(magnitude=1, units="m^2")
    ),
)
bad("self predecessor", lambda b, r: r["metadata"].update(previous=r["metadata"]["id"]))
bad("predecessor must be a Run", lambda b, r: r["metadata"].update(previous=mid))


def omit_selection(bundle, run):
    optimization(bundle, run)
    run["report"]["trace"] = [
        s for s in run["report"]["trace"] if s["kind"] != "selection"
    ]


bad("selection evidence", omit_selection)


def false_success(bundle, run):
    unsupported(bundle, run)
    run["report"]["status"] = dict(completion="completed", solution="infeasible")


bad("cannot support mathematical conclusion", false_success)


def shared_child(bundle, run):
    sibling = bundle["runs"][ids["inverse"]]
    sibling["spawns"] = [ids["forward"]]


bad("multiple spawning parents", shared_child, "batch")

# Arithmetic oracle for fixture contents, independent of the conformance code.
for name, rent, noi, capital in (
    ("forward", 30000, 550000, 11000000),
    ("inverse", 27500, 500000, 10000000),
):
    values = {
        r["key"]: r.get("quantity", {}).get("magnitude")
        for r in records(load("model-" + name + "-output")["system"])
        if r.get("kind") == "measurement"
    }
    assert values["annual_rent_per_home"] == rent
    assert values["NOI"] == noi == 20 * rent - 50000
    assert values["capital_value"] == capital and capital * 0.05 == noi


def normalized(value, key=None):
    if isinstance(value, dict):
        return {
            k: normalized(v, k) for k, v in value.items() if v not in (None, [], {})
        }
    if isinstance(value, list):
        return [normalized(v) for v in value]
    if key in ("at", "started_at", "finished_at"):
        return instant(value).isoformat()
    return value


roundtrips = 0
with TemporaryDirectory(prefix="rk-run-check-") as temp:
    path = Path(temp) / "generated.py"
    path.write_text(
        subprocess.check_output(
            [str(BIN / "gen-python"), str(SCHEMA / "run.yaml")], text=True
        )
    )
    spec = importlib.util.spec_from_file_location("rk_run_records", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for root, bundle in valid:
        before = deepcopy(bundle)
        for key in check(root, bundle):
            doc = bundle["runs"][key]
            obj = json_loader.loads(json.dumps(doc), target_class=module.Run)
            assert isinstance(obj.metadata, module.Metadata)
            assert isinstance(obj.specification, module.MetadataId)
            assert all(
                isinstance(ref, module.MetadataId) for ref in obj.spawns + obj.outputs
            )
            after = json.loads(json_dumper.dumps(obj, inject_type=False))
            assert normalized(after) == normalized(doc), (doc, after)
            bundle["runs"][key] = after
            roundtrips += 1
        check(root, bundle)
        assert normalized(bundle) == normalized(before)
print(
    f"Passed {len(validators)} generated schemas, {len(valid)} valid Run/tree cases, {len(structural)} structural rejections,"
)
print(
    f"{len(semantic)} bounded semantic rejections, and {roundtrips} native Run round trips."
)
print(
    "Synthetic records only. No scheduler or solver executed; full residual/optimality verification and structural publication require adapters."
)
