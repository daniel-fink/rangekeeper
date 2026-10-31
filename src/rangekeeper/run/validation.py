"""Bounded finalized-Run checks; synthetic fixtures are not solver evidence."""

import weakref
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

from rangekeeper.model._scope import resolve_reference
from rangekeeper.model.model import Model
from rangekeeper.model.validation import check_model
from rangekeeper.quantity import Quantity, UnitSystem, default_units
from rangekeeper.run._rule.evidence import validate_evidence
from rangekeeper.run.documents import closure
from rangekeeper.run.outputs import validate_outputs
from rangekeeper.run.report import (
    check_non_batch_status,
    check_report,
    completion_for,
)
from rangekeeper.run.run import Run, _validate_local
from rangekeeper.schema.enums import CompletionStatus
from rangekeeper.schema.index import walk_data
from rangekeeper.schema.runtime import Record, exact_equal
from rangekeeper.schema.validation import checked, document_version, supports_version
from rangekeeper.shared.diagnostics import Issue, ValidationReport
from rangekeeper.shared.errors import (
    ContractError,
    IdentityConflictError,
    MissingReferenceError,
    ReferenceTypeError,
    UnitError,
)
from rangekeeper.shared.references import DocumentResolver
from rangekeeper.shared.validation import bounded, require, require_acyclic
from rangekeeper.specification.composition import (
    compose_specification,
    specification_catalogue,
)
from rangekeeper.specification.specification import Specification
from rangekeeper.specification.validation import check_specification

if TYPE_CHECKING:
    from rangekeeper.shared.references import DocumentResolver
    from rangekeeper.specification.composition import Composition


@dataclass(frozen=True, kw_only=True)
class Prerequisites:
    """Checks that a caller already ran on the same immutable revisions.

    ``compositions`` maps a leaf Specification UUID to its composition, and
    ``scopes`` maps it to the scope that its Specification check returned. Run
    validation uses them instead of composing and checking that Specification
    again. An execution passes its own; other callers pass nothing.
    """

    compositions: Mapping[UUID, "Composition"] = field(default_factory=dict)
    scopes: Mapping[UUID, Any] = field(default_factory=dict)


def validate_records(
    run: Record | Mapping[str, object],
    *,
    runs: Mapping[str, Record | Mapping[str, object]],
    specifications: Mapping[str, Record | Mapping[str, object]],
    models: Mapping[str, Record | Mapping[str, object]],
    units: UnitSystem | None = None,
    prerequisites: Prerequisites | None = None,
) -> ValidationReport:
    """Check a revision-keyed tree; opt into assignment conversion with ``units``.

    Raw conformance defaults remain strict. The public facade validator supplies
    its UnitSystem so physically equivalent assigned/output quantities can match.
    ``prerequisites`` replace the composition and Specification checks of the
    leaves that they name.
    """

    def compatible(left, right):
        assert units is not None
        try:
            return units.compatible(left, right)
        except UnitError:
            # An invalid supplied unit makes the Specification invalid. A failed
            # not_assessed Run may still record that unsuccessful attempt.
            return False

    issues: list[Issue] = []
    root = checked("Run", run, "", issues)
    run_data = {
        key: root if value is run else checked("Run", value, f"/runs/{key}", issues)
        for key, value in runs.items()
    }
    spec_data = {
        key: checked("Specification", value, f"/specifications/{key}", issues)
        for key, value in specifications.items()
    }
    model_data = {
        key: checked("Model", value, f"/models/{key}", issues)
        for key, value in models.items()
    }
    return bounded(
        issues,
        lambda: _RunValidation(
            root,
            run_data,
            spec_data,
            model_data,
            document_version("Run"),
            document_version("Specification"),
            document_version("Model"),
            units=units or default_units,
            units_compatible=None if units is None else compatible,
            prerequisites=prerequisites,
            quantities_equal=(
                None
                if units is None
                else lambda actual, requested: (
                    actual
                    == units.convert(
                        quantity=Quantity.from_data(requested), to=actual["units"]
                    ).to_data()
                )
            ),
        ).check(),
        document=root,
    )


def validate_document(
    run: "Run",
    *,
    resolver: "DocumentResolver | None" = None,
    units: UnitSystem | None = None,
) -> ValidationReport:
    """Report the problems of one Run: local rules, or the tree with ``resolver``."""
    if resolver is None:
        return _validate_local(run.record)
    return validate(run=run, resolver=resolver, units=units)


def validate(
    *,
    run: "Run",
    resolver: "DocumentResolver",
    units: UnitSystem | None = None,
) -> ValidationReport:
    """Check a finalized tree and published outputs against exact resolved revisions.

    Without ``units``, the check uses the unit system of the root's input Model,
    or the default unit system when the root has no input Model.

    The supplied Run need not be stored yet. Resolution performs only the reads
    provided by the resolver. References must resolve even for failed attempts;
    incomplete or mathematically invalid Specifications may support not_assessed
    outcomes with the required diagnostic. No solver or scheduler is invoked.
    Assignments are compared after explicit conversion to output Measure units;
    this does not evaluate equations or certify a solver's numerical claims.
    To validate the Run of an Outcome that is not stored yet, lay its outputs
    and case Runs over the resolver with ``rk.execution.Overlay``.
    """
    return validate_executed(
        run, resolver=resolver, units=units, prerequisites=Prerequisites()
    )


def validate_executed(
    run: "Run",
    *,
    resolver: "DocumentResolver",
    prerequisites: Prerequisites,
    units: UnitSystem | None = None,
) -> ValidationReport:
    """Validate the Run of an execution, reusing the checks that it already ran.

    ``prerequisites`` are the compositions and Specification checks of the
    execution on the same revisions; validation does not repeat them. The
    execution layer calls this; other callers use ``validate``.
    """
    if not isinstance(run, Run):
        raise TypeError("run must be a Run; use validate_records for raw catalogues")
    try:
        found = _documents(run, resolver)
        runs, specifications, models = _catalogues(found)
        if units is None:
            units = _input_unit_system(run, found)
        return validate_records(
            run.record,
            runs=runs,
            specifications=specifications,
            models=models,
            units=units,
            prerequisites=prerequisites,
        )
    except (MissingReferenceError, ReferenceTypeError, IdentityConflictError) as error:
        return ValidationReport((Issue(error.code, str(error), run.id),))


def collect_documents(
    root: "Run",
    resolver: DocumentResolver,
) -> tuple[dict, dict, dict]:
    """Cache each resolved revision; leave cycle/ownership decisions to validation.

    Return the Run, Specification and Model records, keyed by revision text.
    """
    return _catalogues(_documents(root, resolver))


def _input_unit_system(root: "Run", found: dict) -> UnitSystem:
    specification = found[root.record.specification]
    model = found.get(specification.record.model)
    return model.unit_system if isinstance(model, Model) else default_units


def _documents(root: "Run", resolver: DocumentResolver) -> dict:
    """Resolve each revision once; leave cycle/ownership decisions to validation.

    The root is supplied in memory, allowing validation before its first store write.
    Includes, cases, spawns, outputs, Model pins and scoped report documents resolve.
    Historical predecessors are not required to interpret the current document.
    Untyped report-document references use the resolver's three typed lookups.
    """
    return {item.id: item for item in closure([root], resolver=resolver)}


def _catalogues(found: dict) -> tuple[dict, dict, dict]:
    def catalogue(kind):
        return {
            str(identity): (doc._record if isinstance(doc, Model) else doc.record)
            for identity, doc in found.items()
            if isinstance(doc, kind)
        }

    return catalogue(Run), catalogue(Specification), catalogue(Model)


class _RunValidation:
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
        units=default_units,
        units_compatible=None,
        quantities_equal=None,
        prerequisites=None,
    ):
        self.catalogue = dict(runs)
        self.root_id = root["metadata"]["id"]
        require(
            self.root_id not in self.catalogue
            or exact_equal(self.catalogue[self.root_id], root),
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
        self.units = units
        self.units_compatible = units_compatible
        self.specifications, self.models = specifications, models
        self.quantities_equal = quantities_equal
        self.input_ids, self.output_ids, self.producers = set(), set(), {}
        self.compositions, self.pins, self.prepared_scopes = {}, {}, {}
        if prerequisites is not None:
            self.compositions.update(
                (str(key), value) for key, value in prerequisites.compositions.items()
            )
            self.prepared_scopes.update(
                (str(key), value) for key, value in prerequisites.scopes.items()
            )

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
            self.identity_cache[revision] = {
                record["id"] for record, _ in walk_data(kind, doc) if "id" in record
            }
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
        try:
            require(ref not in self.active, "Run spawn cycle")
            require(ref not in self.visited, "Run has multiple spawning parents")
            run = self.resolve(ref, "Run")
            require(
                supports_version(run["metadata"]["schema_version"], self.run_version),
                "unsupported Run version",
            )
            spec = self.resolve(run["specification"], "Specification")
            require(
                supports_version(spec["metadata"]["schema_version"], self.spec_version),
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
                    solution == "not_applicable",
                    "batch solution must be not_applicable",
                )
                case_refs = [r["specification"] for r in children]
                require(
                    len(case_refs) == len(set(case_refs))
                    and set(case_refs) == set(spec["cases"]),
                    "batch must account for each direct case once",
                )
                require(
                    completion
                    == completion_for(
                        CompletionStatus(child["report"]["status"]["completion"])
                        for child in children
                    ).value,
                    "batch completion disagrees with cases",
                )
                require(
                    outputs
                    == {m for child in children for m in child.get("outputs") or []},
                    "batch outputs must equal spawned output union",
                )
                if spec.get("model") is not None:
                    self.resolve(spec["model"], "Model")

                    require(
                        all(
                            m == spec["model"]
                            for child in children
                            for m in self.pins[child["metadata"]["id"]]
                        ),
                        "batch input Model assertion mismatch",
                    )
            else:
                check_non_batch_status(run)
                try:
                    spec_id = spec["metadata"]["id"]
                    if spec_id not in self.compositions:
                        self.compositions[spec_id] = compose_specification(
                            spec, self.specifications, self.spec_version
                        )
                    composition = self.compositions[spec_id]
                    effective = composition.effective
                    require(
                        effective.get("model") is not None,
                        "concrete Specification requires an input Model",
                    )
                    model = self.resolve(effective["model"], "Model")
                    self.input_ids.add(effective["model"])
                    if effective["model"] not in self.scope_cache:
                        self.scope_cache[effective["model"]] = check_model(
                            model, self.model_version
                        )
                    if spec_id not in self.prepared_scopes:
                        scope, _ = check_specification(
                            spec,
                            model,
                            self.spec_version,
                            self.model_version,
                            specifications=self.specifications,
                            units_compatible=self.units_compatible,
                            composition=composition,
                            validate_input=False,
                        )
                        self.prepared_scopes[spec_id] = scope
                    scope = self.prepared_scopes[spec_id]
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
                        effective.get("rules")
                        and not outputs
                        and (
                            run["report"].get("rule_evidence")
                            or solution != "not_assessed"
                        )
                    ):
                        validate_evidence(
                            effective["rules"],
                            run["report"].get("rule_evidence") or [],
                            scope=scope,
                            provenance=model.get("provenance") or {},
                            units=self.units,
                        )
                    if outputs:
                        prepared_outputs = []
                        for output_id in run.get("outputs") or ():
                            require(
                                output_id not in self.producers,
                                "output has multiple producing Runs",
                            )
                            self.producers[output_id] = ref
                            self.output_ids.add(output_id)
                            output = self.resolve(output_id, "Model")
                            if output_id not in self.scope_cache:
                                self.scope_cache[output_id] = check_model(
                                    output, self.model_version
                                )
                            prepared_outputs.append(
                                (output, self.scope_cache[output_id])
                            )
                        try:
                            validate_outputs(
                                run,
                                model,
                                effective,
                                scope,
                                prepared_outputs,
                                units=self.units,
                                quantities_equal=self.quantities_equal,
                            )
                        except ContractError as error:
                            if not error.path:
                                error.path = "/outputs"
                            raise
            try:
                check_report(run, batch=batch, effective=effective)
            except ContractError as error:
                if not error.path:
                    error.path = "/report"
                raise
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
                        self.scope_cache[input_id] = check_model(
                            self.models[input_id], self.model_version
                        )
                    resolve_reference(reference, self.scope_cache[input_id].targets)
            self.pins[ref] = (
                tuple(
                    pin
                    for child in children
                    for pin in self.pins[child["metadata"]["id"]]
                )
                if batch
                else (
                    ()
                    if effective is None or effective.get("model") is None
                    else (effective["model"],)
                )
            )
            self.visited[ref] = run
            return run
        except ContractError as error:
            if error.document_id is None:
                error.document_id = UUID(ref)
            raise

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
        for ref in self.input_ids | self.output_ids:
            internal = self.ids("Model", self.models[ref]) - {ref}
            require(
                not internal & doc_ids, "document identity collides with declaration"
            )
        return self.visited


def mark_validated(run: "Run", store: object, documents: Iterable[UUID]) -> None:
    """Record that ``run`` passed validation against ``store``.

    ``documents`` are the revisions that the validation read from elsewhere than
    ``store``: the unstored outputs, Runs and Specifications laid over it. A
    store skips its own validation of ``run`` while each of them is in the store
    (``validated_in``). Revisions are immutable, so the result still holds.
    """
    try:
        reference = weakref.ref(store)
    except TypeError:
        return  # a store that cannot be weakly referenced validates again
    object.__setattr__(run, "_validated", (reference, frozenset(documents)))


def validated_in(run: "Run", store: object, contains: Callable[[UUID], bool]) -> bool:
    """Return whether ``run`` passed validation against ``store``.

    ``contains`` tells whether the store holds a revision. The documents that
    the validation read from elsewhere must all be in the store now.
    """
    marker = getattr(run, "_validated", None)
    if marker is None:
        return False
    reference, documents = marker
    return reference() is store and all(contains(id) for id in documents)
