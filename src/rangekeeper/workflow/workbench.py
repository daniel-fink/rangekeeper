"""Explicit local review sessions around the ordinary, stateless workflow API.

No watcher, scheduler or notebook dependency. Inspection is read-only; build writes
new bundles and advances a pointer only after a complete successful export.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import escape
from importlib.metadata import version
from pathlib import Path
from typing import cast
from uuid import uuid4

from rangekeeper.io import json as model_json
from rangekeeper.model import Model
from rangekeeper.adapters.cytoscape import ASSETS
from rangekeeper.model.diff import between

from . import _audit
from ._declarations import plain
from .progress import Observer, Reporter, emit
from ._review import decisions_html
from .catalog import OPERATIONS
from .implementation import manifests
from .review import export
from .runtime import WorkflowResult, run
from .specification import WorkflowSpec, load

_BUNDLE = ("model.json", "checks.json", "manifest.json", "review.html", "viewer.html")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


from ._artifacts import write_json as _atomic_json


def _latest(root):
    pointer = root / "latest.json"
    if not pointer.exists():
        return None, None
    raw = json.loads(pointer.read_text())
    directory = (root / raw["directory"]).resolve()
    if not directory.is_relative_to((root / "runs").resolve()):
        raise ValueError("Latest pointer is outside the run directory")
    record = json.loads((directory / "run.json").read_text())
    if not record.get("complete") or set(record["artifacts"]) != set(_BUNDLE):
        raise ValueError("Latest bundle is incomplete")
    if any(
        _hash(directory / name) != digest
        for name, digest in record["artifacts"].items()
    ):
        raise ValueError("Latest bundle failed artifact integrity checks")
    return directory, record


@dataclass(frozen=True)
class Inspection:
    """A point-in-time observation; saved notebook output does not update itself."""

    checked_at: str
    status: str
    specification: WorkflowSpec | None
    inputs: dict
    signature: dict
    latest: Path | None
    diagnostics: tuple[str, ...] = ()
    last_attempt: dict | None = None

    def __repr__(self):
        return f"Inspection(status={self.status!r}, checked_at={self.checked_at!r}, latest={self.latest!r})"

    def _repr_html_(self):
        rows = "".join(
            "<tr>"
            + "".join(
                "<td>" + escape(str(item.get(key) or "Not recorded")) + "</td>"
                for key in ("name", "path", "checksum", "status", "message")
            )
            + "</tr>"
            for item in self.inputs.values()
        )
        link = (
            "<p>No successful output recorded.</p>"
            if self.latest is None
            else '<p>Last successful output: <a href="'
            + escape((self.latest / "review.html").as_uri(), quote=True)
            + '" target="_blank">Review</a> · <a href="'
            + escape((self.latest / "viewer.html").as_uri(), quote=True)
            + '" target="_blank">Graph</a></p>'
        )
        return (
            "<section><h3>Inputs and freshness · "
            + escape(self.status)
            + "</h3><p>Checked "
            + escape(self.checked_at)
            + ". Refresh this cell after edits; saved output is a snapshot.</p>"
            + link
            + (
                "<p>Latest attempt: "
                + escape(str(self.last_attempt.get("status")))
                + ". The links above identify the last successful output.</p>"
                if self.last_attempt
                else ""
            )
            + "<ul>"
            + "".join("<li>" + escape(d) + "</li>" for d in self.diagnostics)
            + "</ul><table><tr><th>Source</th><th>File</th><th>SHA-256</th><th>Status</th><th>Finding</th></tr>"
            + rows
            + "</table><details><summary>Specification, implementation and environment fingerprints</summary><pre>"
            + escape(json.dumps(self.signature, indent=2))
            + "</pre></details></section>"
        )

    def clarifications_html(self):
        if self.specification is None:
            return "<p>Specification unavailable; see input diagnostics.</p>"
        return (
            "<p>Current authored declarations; graph links appear only in a successful build review.</p>"
            + decisions_html(self.specification.decisions)
        )


def inspect(spec_directory: Path, *, input_root: Path, output_root: Path) -> Inspection:
    """Inspect declared inputs through their owning adapters, without creating files."""
    checked, spec, inputs, signature, latest = _now(), None, {}, {}, None
    diagnostics = []
    previous = None
    try:
        latest, previous = _latest(Path(output_root).resolve())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        diagnostics.append("Previous output unavailable: " + str(exc))
    try:
        spec = load(Path(spec_directory))
        modules, dependencies = _audit.capabilities(spec)
        audit, _semantic, implementation_id = manifests(
            Path(__file__).resolve().parents[1], modules=modules
        )
        for step in spec.steps:
            handler = OPERATIONS[step.operation]
            if handler.inspect_input:
                inputs[step.id] = dict(
                    handler.inspect_input(step.request, Path(input_root).resolve())
                )
        signature = {
            "specification": dict(spec.hashes),
            "implementation": audit,
            "semantic_implementation": implementation_id,
            "viewer_assets": {
                str(p.relative_to(ASSETS)): _hash(p)
                for p in sorted(ASSETS.rglob("*"))
                if p.is_file()
            },
            "dependencies": {d: version(d) for d in dependencies},
            "python": sys.version.split()[0],
            "inputs": {
                key: {k: v for k, v in item.items() if k not in ("path", "message")}
                for key, item in inputs.items()
            },
        }
        for key, item in inputs.items():
            if item["status"] != "ready":
                diagnostics.append(f"{key}: {item.get('message', item['status'])}")
        if any(item["status"] != "ready" for item in inputs.values()):
            state = "invalid inputs"
        elif previous is None:
            state = "not built" if not diagnostics else "previous output unavailable"
        elif not previous.get("inputs_verified"):
            state = "unverified inputs"
        else:
            state = "current" if signature == previous["signature"] else "stale"
    except (
        Exception
    ) as exc:  # noqa: BLE001 -- user-facing attempt boundary retains the error type
        state = "invalid specification or environment"
        diagnostics.append(f"{type(exc).__name__}: {exc}")
    last_attempt = None
    try:
        last_attempt = json.loads(
            (Path(output_root) / "latest-attempt.json").read_text()
        )
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        diagnostics.append("Attempt status unavailable: " + str(exc))
    return Inspection(
        checked,
        state,
        spec,
        inputs,
        signature,
        latest,
        tuple(diagnostics),
        last_attempt,
    )


def _changes(previous, result):
    if previous is None:
        return {"status": "No previous successful build", "graph": {}, "checks": {}}
    diff = between(model_json.read(previous / "model.json", kind=Model), result.model)
    graph = {
        kind: len(getattr(diff, kind)) for kind in ("added", "removed", "modified")
    }
    old = {
        c["id"]: c for c in json.loads((previous / "checks.json").read_text())["checks"]
    }
    new = {c.id: plain(asdict(c)) for c in result.checks}
    changed = [
        key
        for key in sorted(old.keys() & new.keys())
        if any(old[key].get(field) != new[key].get(field) for field in new[key])
    ]
    return {
        "status": "Compared after successful build",
        "graph": graph,
        "checks": {
            "added": len(new.keys() - old.keys()),
            "removed": len(old.keys() - new.keys()),
            "changed": len(changed),
            "examples": changed[:20],
        },
    }


@dataclass(frozen=True)
class Attempt:
    """Always a new attempt; a failed attempt never carries a previous result."""

    status: str
    started_at: str
    finished_at: str
    directory: Path | None
    previous: Path | None
    result: WorkflowResult | None
    diagnostics: tuple[str, ...]
    changes: dict

    def __repr__(self):
        return f"Attempt(status={self.status!r}, directory={self.directory!r}, diagnostics={self.diagnostics!r})"

    def _repr_html_(self):
        text = (
            "<h3>Build · "
            + escape(self.status)
            + "</h3><p>"
            + escape(self.started_at + " → " + self.finished_at)
            + "</p>"
        )
        text += (
            "<ul>"
            + "".join("<li>" + escape(d) + "</li>" for d in self.diagnostics)
            + "</ul>"
        )
        directory = self.directory if self.status == "completed" else self.previous
        if directory:
            label = (
                "This successful run"
                if self.status == "completed"
                else "Previous successful run — not the failed attempt"
            )
            text += (
                "<p>"
                + label
                + ': <a target="_blank" href="'
                + escape((directory / "review.html").as_uri(), quote=True)
                + '">Findings and clarification trail</a> · <a target="_blank" href="'
                + escape((directory / "viewer.html").as_uri(), quote=True)
                + '">Open graph and provenance</a></p>'
            )
        if self.result is not None:
            from collections import Counter

            counts = Counter(
                c.status for c in self.result.checks if c.category == "comparison"
            )
            text += (
                "<p>"
                + escape(
                    f"{len(self.result.model.find_entities())} entities · {len(self.result.model.system.relationships or ())} relationships · comparisons {dict(counts)}"
                )
                + "</p>"
            )
        return (
            text
            + "<details><summary>Changes from previous successful run</summary><pre>"
            + escape(json.dumps(self.changes, indent=2))
            + "</pre></details>"
        )


def build(
    spec_directory: Path,
    *,
    input_root: Path,
    output_root: Path,
    on_progress: Observer | None = None,
) -> Attempt:
    """Run independently, then compare/export. Never overwrite a successful bundle.

    Failures return diagnostics without an old result. Unexpected exceptions retain
    their type and message in the attempt record; KeyboardInterrupt still propagates.
    """
    reporter = Reporter(on_progress)
    started = _now()
    root = Path(output_root).resolve()
    before = inspect(spec_directory, input_root=input_root, output_root=root)
    stage = None
    try:
        if (
            before.specification is None
            or not before.signature
            or any(i["status"] != "ready" for i in before.inputs.values())
        ):
            raise ValueError(
                "; ".join(before.diagnostics) or "Inputs could not be inspected"
            )
        result_outcome = run(
            before.specification, input_root=input_root, on_progress=reporter
        )
        if result_outcome.output is None:
            raise ValueError(
                "; ".join(f"{d.code}: {d.message}" for d in result_outcome.diagnostics)
            )
        result = result_outcome.output
        after = inspect(spec_directory, input_root=input_root, output_root=root)
        if before.signature != after.signature:
            raise ValueError(
                "Inputs, specification or implementation changed during execution; rerun explicitly"
            )
        # Ensure the bytes inspected are also the bytes actually used by the build.
        sources = cast(Mapping[str, Mapping[str, object]], result.metadata["sources"])
        for key, source in sources.items():
            if (
                key in before.inputs
                and source["checksum"] != before.inputs[key]["checksum"]
            ):
                raise ValueError(f"Source {key} changed during execution")
        changes = _changes(before.latest, result)
        emit(reporter, "export", "running")
        runs = root / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".pending-", dir=runs))
        export(result, stage)
        record = {
            "complete": True,
            "started_at": started,
            "finished_at": _now(),
            "signature": before.signature,
            "inputs": before.inputs,
            "inputs_verified": set(sources) <= set(before.inputs),
            "artifacts": {name: _hash(stage / name) for name in _BUNDLE},
            "changes": changes,
        }
        _atomic_json(stage / "run.json", record)
        directory = runs / str(uuid4())
        stage.rename(directory)
        stage = None
        # A failed status write or pointer replacement cannot invalidate old output.
        _atomic_json(
            root / "latest-attempt.json",
            {
                "status": "completed",
                "started_at": started,
                "finished_at": record["finished_at"],
                "directory": str(directory.relative_to(root)),
            },
        )
        _atomic_json(
            root / "latest.json", {"directory": str(directory.relative_to(root))}
        )
        # Publication is complete; do not let display failures turn it into a failed build.
        try:
            emit(reporter, "export", "completed")
        except Exception:  # noqa: BLE001, S110 -- publication has already succeeded
            pass
        return Attempt(
            "completed",
            started,
            record["finished_at"],
            directory,
            before.latest,
            result,
            tuple(
                d.message for d in (*result_outcome.diagnostics, *reporter.diagnostics)
            ),
            changes,
        )
    except (Exception, KeyboardInterrupt) as exc:
        status = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        diagnostics = (f"{type(exc).__name__}: {exc}",)
        attempt = Attempt(
            status, started, _now(), None, before.latest, None, diagnostics, {}
        )
        try:
            root.mkdir(parents=True, exist_ok=True)
            _atomic_json(
                root / "latest-attempt.json",
                {
                    "status": status,
                    "started_at": started,
                    "finished_at": attempt.finished_at,
                    "diagnostics": diagnostics,
                },
            )
        except OSError:
            pass  # The returned attempt still reports failure if the disk is unavailable.
        if isinstance(exc, KeyboardInterrupt):
            raise
        return attempt
    finally:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)


def notebook_progress():
    """Create an optional IPython display observer without importing IPython in RK core."""
    from IPython.display import HTML, display

    handle = display(HTML("<p>Ready to run.</p>"), display_id=True)

    def show(event):
        if handle is not None:
            label = f"{event.phase}: {event.status}"
            if event.step:
                label += f" · {event.step} · {event.completed}/{event.total}"
            handle.update(HTML("<p>" + escape(label) + "</p>"))

    return show
