"""Local Run evidence checks need no resolver or solver.

These checks permit a report of failure without inferring mathematical success.
Tree validation adds exact revision and publication checks after resolution.
"""

from datetime import datetime
import math
from rangekeeper.shared.validation import require


def instant(value):
    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    require(stamp.utcoffset() is not None, "timestamp requires timezone")
    return stamp


def completion_for(completions):
    """Combine child completion states; an empty sequence is completed."""
    from rangekeeper.schema.enums import CompletionStatus

    states = tuple(completions)
    if any(not isinstance(state, CompletionStatus) for state in states):
        raise TypeError("completion states must be CompletionStatus members")
    if all(state is CompletionStatus.COMPLETED for state in states):
        return CompletionStatus.COMPLETED
    if CompletionStatus.COMPLETED in states:
        return CompletionStatus.PARTIAL
    for state in (
        CompletionStatus.FAILED,
        CompletionStatus.PARTIAL,
        CompletionStatus.LIMITED,
        CompletionStatus.CANCELLED,
    ):
        if state in states:
            return (
                CompletionStatus.FAILED if state is CompletionStatus.PARTIAL else state
            )
    return CompletionStatus.SKIPPED


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
            not data.get("outcomes") or effective.get("policy") is not None,
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
