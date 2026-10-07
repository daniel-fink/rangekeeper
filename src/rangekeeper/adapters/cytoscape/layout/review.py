"""Explicit saved-layout step after a successful workbench graph attempt."""

import json
from dataclasses import dataclass, replace as replace_result
from enum import Enum, unique
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from time import perf_counter

import yaml  # type: ignore[import-untyped]

from rangekeeper import _records
from rangekeeper.adapters.cytoscape import ASSETS, project
from rangekeeper.adapters.cytoscape.layout import profile as profiles
from rangekeeper.adapters.cytoscape.layout.seed import grid_seed
from rangekeeper.adapters.cytoscape.layout.viewer import (
    PublishedLayoutError,
    PublishedLayoutInterrupted,
    export_layout_review,
)

from rangekeeper.io import _atomic
from rangekeeper.io._atomic import replace
from rangekeeper.model import Model


def _atomic_json(path, value):
    return replace(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _record_attempt(root, outcome):
    root.mkdir(parents=True, exist_ok=True)
    _atomic_json(
        root / "latest-attempt.json",
        {
            "status": outcome.status.value,
            "checked_at": outcome.checked_at,
            "directory": str(outcome.directory) if outcome.directory else None,
            "diagnostics": outcome.diagnostics,
        },
    )


def _hash(path):
    return sha256(path.read_bytes()).hexdigest()


def _implementation():
    return {
        "layout": {
            p.name: _hash(p)
            for p in Path(profiles.__file__).parent.iterdir()
            if p.suffix in {".py", ".mzn"}
        },
        "review": _hash(Path(__file__)),
        "record_comparison": _hash(Path(_records.__file__)),
        "atomic_publication": _hash(Path(_atomic.__file__)),
        "assets": {
            str(p.relative_to(ASSETS)): _hash(p)
            for p in ASSETS.rglob("*")
            if p.is_file()
        },
    }


def _latest(root):
    if not (root / "latest.json").exists():
        return None
    directory = (root / json.loads((root / "latest.json").read_text())["run"]).resolve()
    if not directory.is_relative_to((root / "runs").resolve()):
        raise ValueError("Layout pointer outside runs")
    manifest = json.loads((directory / "manifest.json").read_text())
    if not {
        "problem.json",
        "geometry.json",
        "document.json",
        "viewer.html",
        "run.json",
        "context.json",
    } <= manifest.keys() or any(_hash(directory / n) != h for n, h in manifest.items()):
        raise ValueError("Previous layout bundle failed integrity checks")
    return directory


@unique
class BuildStatus(Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True)
class LayoutAttempt:
    status: BuildStatus
    checked_at: str
    directory: Path | None
    previous: Path | None
    diagnostics: tuple[str, ...] = ()
    measurements: dict | None = None

    def _repr_html_(self):
        text = f"<section><h3>Saved layout · {escape(self.status.value)}</h3><p>Checked {escape(self.checked_at)}. Saved output is a snapshot.</p>"
        if self.diagnostics:
            text += (
                "<ul>"
                + "".join(f"<li>{escape(d)}</li>" for d in self.diagnostics)
                + "</ul>"
            )
        path = self.directory if self.status is BuildStatus.COMPLETED else self.previous
        if path:
            label = (
                "This successful layout"
                if self.status is BuildStatus.COMPLETED
                else "Previous successful layout — not this attempt's output"
            )
            text += f'<p>{label}: <a target="_blank" href="{escape((path / "viewer.html").as_uri(), quote=True)}">Open stacked graph and provenance</a> · <a target="_blank" href="{escape((path / "review.html").as_uri(), quote=True)}">Findings and decisions</a></p>'
        if self.measurements:
            m = self.measurements
            text += f"<p>{m['width']:,} × {m['height']:,} px · {m['false_enclosures']} false enclosures · {m['grid_displacement']} grid displacement. Checked constructive layout; optimality not claimed.</p>"
        return text + "</section>"


def build(
    model: Model,
    *,
    bundle: Path,
    profile: Path,
    output_root: Path,
) -> LayoutAttempt:
    """Use only this successful attempt, never an earlier graph as a fallback input."""
    root = Path(output_root).resolve()
    previous = None
    interruption: KeyboardInterrupt | None = None
    started = perf_counter()
    now = lambda: datetime.now(timezone.utc).isoformat()
    try:
        previous = _latest(root)
        if not isinstance(model, Model):
            raise TypeError("layout build requires a Model and its completed bundle")
        directory = Path(bundle)
        record = json.loads((directory / "run.json").read_text())
        if not record.get("complete") or any(
            _hash(directory / n) != h for n, h in record["artifacts"].items()
        ):
            raise ValueError("Completed graph bundle failed integrity checks")
        if not _records.exact_equal(
            model.to_data(), json.loads((directory / "model.json").read_text())
        ):
            raise ValueError("In-memory graph differs from the completed build")
        raw = Path(profile).read_bytes()
        config = yaml.safe_load(raw)
        implementation = _implementation()
        resolved_profile = profiles.resolve(config)
        problem, signals = profiles.prepare(model, config)
        result = grid_seed(problem)
        if result is None:
            raise ValueError(
                "No constructive layout for this profile; inspect shared memberships or constraints and run a solver explicitly."
            )
        result.elapsed_seconds = perf_counter() - started
        if Path(profile).read_bytes() != raw:
            raise ValueError(
                "Layout profile changed during execution; rerun explicitly"
            )
        if implementation != _implementation():
            raise ValueError(
                "Layout implementation changed during execution; rerun explicitly"
            )
        context = {
            "profile": config,
            "resolved_profile": resolved_profile,
            "profile_sha256": sha256(raw).hexdigest(),
            "source_build": str(directory.resolve()),
            "source_artifacts": record["artifacts"],
            "source_signature": record["signature"],
            "signals": signals,
            "implementation": implementation,
            "review_implementation": _hash(Path(__file__)),
            "viewer_assets": {
                str(p.relative_to(ASSETS)): _hash(p)
                for p in ASSETS.rglob("*")
                if p.is_file()
            },
        }
        doc = project(
            model,
            "Workflow graph · stacked layout",
            {"reviewUrl": "review.html", "notes": resolved_profile["notes"]},
        )
        diagnostics: tuple[str, ...] = ()
        try:
            saved = export_layout_review(
                doc,
                problem,
                result,
                root,
                review_html=directory / "review.html",
                context=context,
            )
        except PublishedLayoutError as exc:
            saved = exc.directory
            diagnostics = (str(exc),)
        except PublishedLayoutInterrupted as exc:
            saved = exc.directory
            diagnostics = (str(exc),)
            interruption = exc
        outcome = LayoutAttempt(
            BuildStatus.COMPLETED,
            now(),
            saved,
            previous,
            diagnostics,
            measurements=result.measurements,
        )
    except (
        Exception,
        KeyboardInterrupt,
    ) as exc:  # noqa: BLE001 -- notebook failure boundary, never old in-memory geometry
        if isinstance(exc, KeyboardInterrupt):
            interruption = exc
        outcome = LayoutAttempt(
            (
                BuildStatus.INTERRUPTED
                if isinstance(exc, KeyboardInterrupt)
                else BuildStatus.FAILED
            ),
            now(),
            None,
            previous,
            (f"{type(exc).__name__}: {exc}",),
        )
    try:
        _record_attempt(root, outcome)
    except KeyboardInterrupt as exc:
        interruption = interruption or exc
        outcome = replace_result(
            outcome,
            diagnostics=(*outcome.diagnostics, "Attempt record write interrupted"),
        )
        try:
            _record_attempt(root, outcome)
        except (OSError, KeyboardInterrupt) as record_error:
            outcome = replace_result(
                outcome,
                diagnostics=(
                    *outcome.diagnostics,
                    f"Attempt record write was not confirmed: {record_error}",
                ),
            )
    except OSError as exc:
        outcome = replace_result(
            outcome,
            diagnostics=(
                *outcome.diagnostics,
                f"Attempt record write was not confirmed: {exc}",
            ),
        )
    if interruption is not None:
        if outcome.status is BuildStatus.COMPLETED:
            setattr(interruption, "completed_attempt", outcome)
        raise interruption
    return outcome
