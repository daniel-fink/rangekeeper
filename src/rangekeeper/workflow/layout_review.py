"""Explicit saved-layout step after a successful workbench graph attempt."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from pathlib import Path
from time import perf_counter

import yaml  # type: ignore[import-untyped]

from rangekeeper.io import json as model_json
from rangekeeper.adapters.cytoscape import ASSETS, project
from rangekeeper.adapters.cytoscape.layout import profile as profiles
from rangekeeper.adapters.cytoscape.layout.seed import grid_seed
from rangekeeper.adapters.cytoscape.layout.viewer import export_layout_review

from ._artifacts import write_json as _atomic_json


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


@dataclass(frozen=True)
class LayoutAttempt:
    status: str
    checked_at: str
    directory: Path | None
    previous: Path | None
    diagnostics: tuple[str, ...] = ()
    measurements: dict | None = None

    def _repr_html_(self):
        text = f"<section><h3>Saved layout · {escape(self.status)}</h3><p>Checked {escape(self.checked_at)}. Saved output is a snapshot.</p>"
        if self.diagnostics:
            text += (
                "<ul>"
                + "".join(f"<li>{escape(d)}</li>" for d in self.diagnostics)
                + "</ul>"
            )
        path = self.directory if self.status == "completed" else self.previous
        if path:
            label = (
                "This successful layout"
                if self.status == "completed"
                else "Previous successful layout — not this attempt's output"
            )
            text += f'<p>{label}: <a target="_blank" href="{escape((path / "viewer.html").as_uri(), quote=True)}">Open stacked graph and provenance</a> · <a target="_blank" href="{escape((path / "review.html").as_uri(), quote=True)}">Findings and decisions</a></p>'
        if self.measurements:
            m = self.measurements
            text += f"<p>{m['width']:,} × {m['height']:,} px · {m['false_enclosures']} false enclosures · {m['grid_displacement']} grid displacement. Checked constructive layout; optimality not claimed.</p>"
        return text + "</section>"


def build(attempt, *, profile: Path, output_root: Path) -> LayoutAttempt:
    """Use only this successful attempt, never an earlier graph as a fallback input."""
    root = Path(output_root).resolve()
    previous = None
    started = perf_counter()
    now = lambda: datetime.now(timezone.utc).isoformat()
    try:
        previous = _latest(root)
        if (
            attempt is None
            or attempt.status != "completed"
            or attempt.result is None
            or attempt.directory is None
        ):
            raise ValueError(
                "No successful graph attempt in this kernel. Run the workflow cell first."
            )
        directory = Path(attempt.directory)
        record = json.loads((directory / "run.json").read_text())
        if not record.get("complete") or any(
            _hash(directory / n) != h for n, h in record["artifacts"].items()
        ):
            raise ValueError("Completed graph bundle failed integrity checks")
        if json.loads(model_json.dumps(attempt.result.model)) != json.loads(
            (directory / "model.json").read_text()
        ):
            raise ValueError("In-memory graph differs from the completed build")
        raw = Path(profile).read_bytes()
        config = yaml.safe_load(raw)
        implementation = _implementation()
        resolved_profile = profiles.resolve(config)
        problem, signals = profiles.prepare(attempt.result.model, config)
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
            attempt.result.model,
            "Workflow graph · stacked layout",
            {"reviewUrl": "review.html", "notes": resolved_profile["notes"]},
        )
        saved = export_layout_review(
            doc,
            problem,
            result,
            root,
            review_html=directory / "review.html",
            context=context,
        )
        outcome = LayoutAttempt(
            "completed", now(), saved, previous, measurements=result.measurements
        )
    except (
        Exception,
        KeyboardInterrupt,
    ) as exc:  # noqa: BLE001 -- notebook failure boundary, never old in-memory geometry
        outcome = LayoutAttempt(
            "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
            now(),
            None,
            previous,
            (f"{type(exc).__name__}: {exc}",),
        )
    root.mkdir(parents=True, exist_ok=True)
    _atomic_json(
        root / "latest-attempt.json",
        {
            "status": outcome.status,
            "checked_at": outcome.checked_at,
            "directory": str(outcome.directory) if outcome.directory else None,
            "diagnostics": outcome.diagnostics,
        },
    )
    return outcome
