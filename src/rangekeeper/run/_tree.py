"""Bounded finalized-Run conformance; not a scheduler, evaluator, or solver.

Structurally validate supplied documents first. Typed catalogues resolve immutable
references. Scalar output checks preserve input definitions, check supplied amounts
and required recorded quantities, but do not evaluate equations or prove feasibility.
Specification-local Value publication and structural interventions need adapters.
"""

from rangekeeper.model._references import resolve_reference
from rangekeeper.errors import ContractError
from rangekeeper._validation import require, require_acyclic
from rangekeeper.model._validation import model_documents, validate_model
from rangekeeper.specification._composition import (
    compose_specification,
    specification_catalogue,
)
from rangekeeper.specification._validation import records, validate_specification


from ._report import completion_for, validate_non_batch_status, validate_report
from ._publication import Publication


class Tree:
    """Resolve and check one immutable Run tree with caches scoped to this call.

    Local reports and accepted publications have separate validators. This class
    owns traversal, document identity, batch accounting and scoped references.
    """

    def __init__(
        self,
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
        self.catalogue = dict(runs)
        self.root_id = root["metadata"]["id"]
        require(
            self.root_id not in self.catalogue or self.catalogue[self.root_id] == root,
            "different Run revision content",
        )
        self.catalogue[self.root_id] = root
        self.typed = {}
        for kind, mapping in (
            ("Run", self.catalogue),
            ("Specification", specifications),
            ("Model", models),
        ):
            for key, doc in mapping.items():
                require(doc["metadata"]["id"] == key, "catalogue identity mismatch")
                require(key not in self.typed, "document identity has multiple kinds")
                self.typed[key] = (kind, doc)
        self.active, self.visited, self.parents = set(), {}, {}
        self.scope_cache = {}
        self.identity_cache = {}

        self.run_version, self.spec_version, self.model_version = (
            run_version,
            spec_version,
            model_version,
        )
        self.units_compatible = units_compatible
        self.specifications, self.models = specifications, models
        self.publication = Publication(self.resolve, model_version, quantities_equal)

    def resolve(self, ref, kind):
        require(ref in self.typed, f"unresolved {kind} reference")
        actual, doc = self.typed[ref]
        require(actual == kind, f"reference must resolve to {kind}")
        return doc

    def ids(self, kind, doc):
        # A temporal Run can reference thousands of constraints in one revision.
        # Index that immutable document once per validation call. Keep the cache
        # local so a later call must check its supplied documents afresh.
        revision = doc["metadata"]["id"]
        if revision not in self.identity_cache:
            if kind == "Model":
                _, doc = model_documents(doc)
            self.identity_cache[revision] = {r["id"] for r in records(doc) if "id" in r}
        return self.identity_cache[revision]

    def reference(self, record):
        document, target = record.get("document"), record.get("target")
        require(target is None or document is not None, "target requires document")
        if document is not None:
            require(document in self.typed, "unresolved report document")
            kind, doc = self.typed[document]
            require(
                target is None or target in self.ids(kind, doc),
                "target outside document scope",
            )

    def visit(self, ref):
        require(ref not in self.active, "Run spawn cycle")
        require(ref not in self.visited, "Run has multiple spawning parents")
        run = self.resolve(ref, "Run")
        require(
            run["metadata"]["schema_version"] == self.run_version,
            "unsupported Run version",
        )
        spec = self.resolve(run["specification"], "Specification")
        require(
            spec["metadata"]["schema_version"] == self.spec_version,
            "unsupported Specification version",
        )
        for field in ("spawns", "outputs"):
            refs = run.get(field) or []
            require(len(refs) == len(set(refs)), f"duplicate {field} reference")
        self.active.add(ref)
        children = []
        for child in run.get("spawns") or []:
            require(child not in self.parents, "Run has multiple spawning parents")
            self.parents[child] = ref
            children.append(self.visit(child))
        self.active.remove(ref)
        status = run["report"]["status"]
        completion, solution = status["completion"], status["solution"]
        batch = bool(spec.get("cases"))
        outputs = set(run.get("outputs") or [])
        effective = None
        scope = None
        if batch:
            # Check batch shape, pinned kinds and reference graph; individual leaf
            # attempts can still report invalid numerical roles without a solution.
            specification_catalogue(spec, self.specifications, self.spec_version)
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
                self.resolve(spec["model"], "Model")

                def inputs(child):
                    child_spec = self.specifications[child["specification"]]
                    if child_spec.get("cases"):
                        for sub in child.get("spawns") or []:
                            yield from inputs(self.catalogue[sub])
                    else:
                        try:
                            view = compose_specification(
                                child_spec, self.specifications, self.spec_version
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
                composition = compose_specification(
                    spec, self.specifications, self.spec_version
                )
                effective = composition.effective
                require(
                    effective.get("model") is not None,
                    "concrete Specification requires an input Model",
                )
                model = self.resolve(effective["model"], "Model")
                self.publication.input_ids.add(effective["model"])
                scope = validate_specification(
                    spec,
                    model,
                    self.spec_version,
                    self.model_version,
                    specifications=self.specifications,
                    units_compatible=self.units_compatible,
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
                    self.publication.check(run, model, effective, scope)
        validate_report(run, batch=batch, effective=effective)
        for item in (run["report"].get("diagnostics") or []) + (
            run["report"].get("trace") or []
        ):
            self.reference(item)
            for reference in item.get("references") or []:
                require(
                    not batch and scope is not None,
                    "diagnostic references require this Run's valid input Model",
                )
                input_id = effective["model"]
                if input_id not in self.scope_cache:
                    self.scope_cache[input_id] = validate_model(
                        self.models[input_id], self.model_version
                    )
                resolve_reference(reference, self.scope_cache[input_id].targets)
        self.visited[ref] = run
        return run

    def check(self):
        """Return reachable Runs after tree, lineage and publication checks pass."""
        self.visit(self.root_id)
        for ref, run in self.visited.items():
            previous = run["metadata"].get("previous")
            require(previous != ref, "Run self predecessor")
            require(previous not in self.visited, "Run lineage is not spawn hierarchy")
            if previous in self.typed:
                require(
                    self.typed[previous][0] == "Run", "Run predecessor must be a Run"
                )
        require_acyclic(
            {
                key: (
                    [r["metadata"]["previous"]] if r["metadata"].get("previous") else []
                )
                for key, r in self.catalogue.items()
            },
            "Run revision history",
        )
        # Model revisions can be inputs to later Runs, but Run/Specification revision
        # UUIDs cannot simultaneously identify canonical domain declarations.
        doc_ids = set(self.typed)
        for ref in self.publication.input_ids | self.publication.output_ids:
            internal = self.ids("Model", self.models[ref]) - {ref}
            require(
                not internal & doc_ids, "document identity collides with declaration"
            )
        return self.visited
