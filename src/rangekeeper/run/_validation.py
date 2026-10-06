"""Bounded finalized-Run conformance; not a scheduler, evaluator, or solver.

Structurally validate supplied documents first. Typed catalogues resolve immutable
references. Scalar output checks preserve input definitions, check supplied amounts
and required recorded quantities, but do not evaluate equations or prove feasibility.
Specification-local Value publication and structural interventions need adapters.
"""

from copy import deepcopy
from datetime import datetime
import math

from rangekeeper.model._references import (
    reference_key,
    recorded_quantity,
    numerical_units,
    resolve_reference,
)
from rangekeeper.errors import ContractError
from rangekeeper._validation import require, require_acyclic
from rangekeeper.model._validation import model_documents, validate_model
from rangekeeper.specification._composition import (
    compose_specification,
    specification_catalogue,
)
from rangekeeper.specification._validation import records, validate_specification


def instant(value):
    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    require(stamp.utcoffset() is not None, "timestamp requires timezone")
    return stamp


def completion_for(children):
    states = [r["report"]["status"]["completion"] for r in children]
    if all(s == "completed" for s in states):
        return "completed"
    if "completed" in states:
        return "partial"
    for state in ("failed", "partial", "limited", "cancelled"):
        if state in states:
            return "failed" if state == "partial" else state
    return "skipped"


def validate_non_batch_status(run):
    """Check the permitted completion/solution/output combinations for one attempt."""
    status = run["report"]["status"]
    completion, solution = status["completion"], status["solution"]
    outputs = set(run.get("outputs") or [])
    allowed = {
        "completed": {"feasible", "infeasible", "unknown"},
        "limited": {"feasible", "unknown", "not_assessed"},
        "failed": {"unknown", "not_assessed"},
        "cancelled": {"unknown", "not_assessed"},
        "skipped": {"not_assessed"},
    }
    require(
        solution in allowed.get(completion, set()),
        "invalid non-batch status combination",
    )
    require(
        bool(outputs) == (solution == "feasible"),
        "outputs require feasible conclusion and vice versa",
    )
    if completion == "skipped":
        require(not run.get("spawns"), "skipped non-batch Run cannot spawn")


def validate_report(run, *, batch, effective=None):
    """Check local report evidence; effective requirements add requested-setting checks."""
    data = run["report"]
    if effective is not None:
        require(
            not data.get("decisions") or effective.get("policy") is not None,
            "decision evidence requires a policy",
        )
    status = data["status"]
    completion, solution = status["completion"], status["solution"]
    findings = data.get("diagnostics") or []
    require(
        bool(findings)
        or (completion == "completed" and solution not in ("unknown", "infeasible")),
        "outcome requires explanatory diagnostic",
    )
    runtime = data.get("runtime")
    if not batch and (
        completion == "limited"
        or (completion == "completed" and solution in ("feasible", "infeasible"))
    ):
        require(runtime is not None, "outcome requires runtime evidence")
    if completion == "skipped":
        require(runtime is None, "skipped Run cannot have runtime")
    start = finish = None
    if runtime is not None:
        implementations = runtime.get("implementations") or []
        require(bool(implementations), "runtime requires implementations")
        keys = [(i["kind"], i["name"], i["version"]) for i in implementations]
        require(len(keys) == len(set(keys)), "duplicate implementation")
        if runtime.get("started_at") is not None:
            start = instant(runtime["started_at"])
        if runtime.get("finished_at") is not None:
            finish = instant(runtime["finished_at"])
        require(
            start is None or finish is None or finish >= start,
            "runtime finishes before start",
        )
        settings = runtime.get("settings") or {}
        for key, value in settings.items():
            if value is not None:
                require(
                    math.isfinite(value) and value > 0,
                    "effective setting must be positive finite",
                )
                if key == "relative_tolerance":
                    require(
                        value < 1,
                        "effective relative tolerance must be less than one",
                    )
        for key, value in ((effective or {}).get("settings") or {}).items():
            if value is not None and settings.get(key) != value:
                require(
                    any(
                        d["code"] == "settings_adjusted" and key in d["message"]
                        for d in findings
                    ),
                    "unaccounted requested setting",
                )
    for diagnostic in findings:
        residual, tolerance = diagnostic.get("residual"), diagnostic.get("tolerance")
        require(
            tolerance is None or residual is not None, "tolerance requires residual"
        )
        if residual is not None:
            require(
                diagnostic.get("target") is not None
                and diagnostic.get("document") is not None,
                "residual requires scoped target",
            )
        for quantity in (residual, tolerance):
            if quantity is not None:
                require(
                    math.isfinite(quantity["magnitude"]),
                    "non-finite diagnostic quantity",
                )
        if tolerance is not None:
            require(tolerance["magnitude"] >= 0, "negative diagnostic tolerance")
            require(
                tolerance["units"] == residual["units"],
                "diagnostic unit conversion requires adapter",
            )
    last = None
    selected = set()
    for step in data.get("trace") or []:
        if step.get("at") is not None:
            stamp = instant(step["at"])
            require(last is None or stamp >= last, "trace times out of order")
            require(start is None or stamp >= start, "trace before runtime")
            require(finish is None or stamp <= finish, "trace after runtime")
            last = stamp
        if step["kind"] in ("publication", "selection"):
            require(
                step.get("document") in (run.get("outputs") or []),
                "trace requires accepted output",
            )
        if step["kind"] == "selection":
            selected.add(step["document"])
    if not batch and (effective or {}).get("objectives") and run.get("outputs"):
        require(
            set(run["outputs"]) <= selected,
            "objectives require output selection evidence",
        )


def validate_local(run, schema_version):
    """Check one finalized record without resolving any external document.

    not_applicable declares an aggregate; cross-document validation verifies that
    its Specification really is a batch and accounts for every direct case.
    """
    metadata = run["metadata"]
    identity = metadata["id"]
    require(metadata["schema_version"] == schema_version, "unsupported Run version")
    require(metadata.get("previous") != identity, "Run self predecessor")
    require(
        run["specification"] != identity, "Specification reference targets this Run"
    )
    for field in ("spawns", "outputs"):
        refs = run.get(field) or []
        require(len(refs) == len(set(refs)), f"duplicate {field} reference")
        require(identity not in refs, f"Run cannot reference itself through {field}")
    batch = run["report"]["status"]["solution"] == "not_applicable"
    if not batch:
        validate_non_batch_status(run)
    validate_report(run, batch=batch)


def validate_run(
    root,
    runs,
    specifications,
    models,
    run_version,
    spec_version,
    model_version,
    *,
    units_compatible=None,
    quantities_equal=None,
):
    """Validate the tree rooted at root; preserve all supplied documents.

    Returns the reachable Run mapping. Residual units use exact canonical spellings;
    optional unit-compatibility/equality callbacks support converted assignments.
    The default raw conformance path retains exact spelling/content checks. Invalid
    Specification attempts may be recorded as failed/skipped/cancelled with
    not_assessed and an explanatory diagnostic. No success is inferred from logs.
    """
    catalogue = dict(runs)
    root_id = root["metadata"]["id"]
    require(
        root_id not in catalogue or catalogue[root_id] == root,
        "different Run revision content",
    )
    catalogue[root_id] = root
    typed = {}
    for kind, mapping in (
        ("Run", catalogue),
        ("Specification", specifications),
        ("Model", models),
    ):
        for key, doc in mapping.items():
            require(doc["metadata"]["id"] == key, "catalogue identity mismatch")
            require(key not in typed, "document identity has multiple kinds")
            typed[key] = (kind, doc)
    active, visited, parents, producers = set(), {}, {}, {}
    input_ids, output_ids = set(), set()
    scope_cache = {}
    identity_cache = {}

    def resolve(ref, kind):
        require(ref in typed, f"unresolved {kind} reference")
        actual, doc = typed[ref]
        require(actual == kind, f"reference must resolve to {kind}")
        return doc

    def ids(kind, doc):
        # A temporal Run can reference thousands of constraints in one revision.
        # Index that immutable document once per validation call. Keep the cache
        # local so a later call must check its supplied documents afresh.
        revision = doc["metadata"]["id"]
        if revision not in identity_cache:
            if kind == "Model":
                _, doc = model_documents(doc)
            identity_cache[revision] = {r["id"] for r in records(doc) if "id" in r}
        return identity_cache[revision]

    def reference(record):
        document, target = record.get("document"), record.get("target")
        require(target is None or document is not None, "target requires document")
        if document is not None:
            require(document in typed, "unresolved report document")
            kind, doc = typed[document]
            require(
                target is None or target in ids(kind, doc),
                "target outside document scope",
            )

    def published(run, model, effective, scope):
        input_id = model["metadata"]["id"]
        input_ids.add(input_id)
        originals = scope.values
        assignments = list(effective.get("assignments") or [])
        decisions = run["report"].get("decisions") or []
        if effective.get("policy"):
            from rangekeeper.specification._policy_validation import validate_decisions

            assignments.extend(
                validate_decisions(
                    effective["policy"],
                    decisions,
                    scope=scope,
                    provenance=model.get("provenance") or {},
                )
            )
        else:
            require(not decisions, "decision evidence requires a policy")
        roles = list(effective.get("unknowns") or []) + [
            a["target"] for a in assignments
        ]
        needed = {reference_key(r): r for r in roles}
        model_values = {
            r["id"]
            for r in records(model.get("system") or {})
            if r.get("kind") in ("measurement", "flow")
        }
        require(
            all(r["value"] in model_values for r in roles),
            "Specification-local Value publication requires adapter",
        )

        def definition(snapshot):
            result = deepcopy(snapshot)
            result.pop("metadata", None)
            result.pop("provenance", None)
            for r in records(result):
                if r.get("kind") == "measurement" and "id" in r and r["id"] in needed:
                    r.pop("quantity", None)
                if r.get("kind") == "flow" and "id" in r:
                    for m in (r.get("flow") or {}).get("movements") or []:
                        if (
                            reference_key(dict(value=r["id"], movement=m["key"]))
                            in needed
                        ):
                            m.pop("magnitude", None)
                            m.pop("claims", None)
            return result

        for ref in run.get("outputs") or []:
            output = resolve(ref, "Model")
            require(ref != input_id, "output cannot be input revision")
            require(ref not in producers, "output has multiple producing Runs")
            producers[ref] = run["metadata"]["id"]
            output_ids.add(ref)
            require(
                output["metadata"].get("previous") == input_id,
                "output lineage must reference input",
            )
            output_scope = validate_model(output, model_version)
            require(
                definition(output) == definition(model),
                "output must preserve input definitions and unrelated recorded content",
            )
            for target in needed.values():
                quantity = recorded_quantity(
                    target, output_scope.values, output_scope.measures
                )
                require(
                    quantity is not None, "accepted output has unresolved solve Value"
                )
                require(
                    quantity["units"]
                    == numerical_units(target, originals, scope.measures),
                    "output unit conversion requires adapter",
                )
                require(
                    math.isfinite(quantity["magnitude"]), "non-finite output quantity"
                )
            for assignment in assignments:
                actual = recorded_quantity(
                    assignment["target"], output_scope.values, output_scope.measures
                )
                expected = assignment["quantity"]
                require(
                    (
                        quantities_equal(actual, expected)
                        if quantities_equal is not None
                        else actual == expected
                    ),
                    "output violates assignment",
                )
            old_claims = {
                c["id"]: c for c in (model.get("provenance") or {}).get("claims") or []
            }
            new_claims = {
                c["id"]: c for c in (output.get("provenance") or {}).get("claims") or []
            }
            require(
                all(new_claims.get(k) == v for k, v in old_claims.items()),
                "historical Claims changed",
            )

    def visit(ref):
        require(ref not in active, "Run spawn cycle")
        require(ref not in visited, "Run has multiple spawning parents")
        run = resolve(ref, "Run")
        require(
            run["metadata"]["schema_version"] == run_version, "unsupported Run version"
        )
        spec = resolve(run["specification"], "Specification")
        require(
            spec["metadata"]["schema_version"] == spec_version,
            "unsupported Specification version",
        )
        for field in ("spawns", "outputs"):
            refs = run.get(field) or []
            require(len(refs) == len(set(refs)), f"duplicate {field} reference")
        active.add(ref)
        children = []
        for child in run.get("spawns") or []:
            require(child not in parents, "Run has multiple spawning parents")
            parents[child] = ref
            children.append(visit(child))
        active.remove(ref)
        status = run["report"]["status"]
        completion, solution = status["completion"], status["solution"]
        batch = bool(spec.get("cases"))
        outputs = set(run.get("outputs") or [])
        effective = None
        if batch:
            # Check batch shape, pinned kinds and reference graph; individual leaf
            # attempts can still report invalid numerical roles without a solution.
            specification_catalogue(spec, specifications, spec_version)
            require(
                solution == "not_applicable", "batch solution must be not_applicable"
            )
            case_refs = [r["specification"] for r in children]
            require(
                len(case_refs) == len(set(case_refs))
                and set(case_refs) == set(spec["cases"]),
                "batch must account for each direct case once",
            )
            require(
                completion == completion_for(children),
                "batch completion disagrees with cases",
            )
            require(
                outputs
                == {m for child in children for m in child.get("outputs") or []},
                "batch outputs must equal spawned output union",
            )
            if spec.get("model") is not None:
                resolve(spec["model"], "Model")

                def inputs(child):
                    child_spec = specifications[child["specification"]]
                    if child_spec.get("cases"):
                        for sub in child.get("spawns") or []:
                            yield from inputs(catalogue[sub])
                    else:
                        try:
                            view = compose_specification(
                                child_spec, specifications, spec_version
                            ).effective
                        except ContractError:
                            # visit() already required failed/not_assessed evidence
                            # for an invalid leaf. It supplies no valid Model assertion.
                            return
                        if view.get("model") is not None:
                            yield view["model"]

                require(
                    all(
                        m == spec["model"] for child in children for m in inputs(child)
                    ),
                    "batch input Model assertion mismatch",
                )
        else:
            validate_non_batch_status(run)
            try:
                composition = compose_specification(spec, specifications, spec_version)
                effective = composition.effective
                require(
                    effective.get("model") is not None,
                    "concrete Specification requires an input Model",
                )
                model = resolve(effective["model"], "Model")
                input_ids.add(effective["model"])
                scope = validate_specification(
                    spec,
                    model,
                    spec_version,
                    model_version,
                    specifications=specifications,
                    units_compatible=units_compatible,
                )
            except ContractError:
                require(
                    completion in ("failed", "cancelled", "skipped")
                    and solution == "not_assessed",
                    "invalid Specification cannot support mathematical conclusion",
                )
                require(
                    any(
                        d["code"] == "specification_invalid"
                        for d in run["report"].get("diagnostics") or []
                    ),
                    "invalid Specification requires diagnostic",
                )
            else:
                if (
                    effective.get("policy")
                    and not outputs
                    and (run["report"].get("decisions") or solution != "not_assessed")
                ):
                    from rangekeeper.specification._policy_validation import (
                        validate_decisions,
                    )

                    validate_decisions(
                        effective["policy"],
                        run["report"].get("decisions") or [],
                        scope=scope,
                        provenance=model.get("provenance") or {},
                    )
                if outputs:
                    published(run, model, effective, scope)
        validate_report(run, batch=batch, effective=effective)
        for item in (run["report"].get("diagnostics") or []) + (
            run["report"].get("trace") or []
        ):
            reference(item)
            for scoped in item.get("references") or []:
                doc = resolve(scoped["document"], "Model")
                if scoped["document"] not in scope_cache:
                    scope_cache[scoped["document"]] = validate_model(doc, model_version)
                referenced_scope = scope_cache[scoped["document"]]
                resolve_reference(scoped["reference"], referenced_scope.values)
        visited[ref] = run
        return run

    visit(root_id)
    for ref, run in visited.items():
        previous = run["metadata"].get("previous")
        require(previous != ref, "Run self predecessor")
        require(previous not in visited, "Run lineage is not spawn hierarchy")
        if previous in typed:
            require(typed[previous][0] == "Run", "Run predecessor must be a Run")
    require_acyclic(
        {
            key: [r["metadata"]["previous"]] if r["metadata"].get("previous") else []
            for key, r in catalogue.items()
        },
        "Run revision history",
    )
    # Model revisions can be inputs to later Runs, but Run/Specification revision
    # UUIDs cannot simultaneously identify canonical domain declarations.
    doc_ids = set(typed)
    for ref in input_ids | output_ids:
        internal = ids("Model", models[ref]) - {ref}
        require(not internal & doc_ids, "document identity collides with declaration")
    return visited
