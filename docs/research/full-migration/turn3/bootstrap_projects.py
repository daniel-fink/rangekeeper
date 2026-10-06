"""Copy current project inputs only; run a preinstalled candidate wheel in isolation.

The environment is created separately from the recorded dependency list and exact
wheel. Archives, prior artifacts and editable RK imports never enter this build.
Outputs contain private source evidence and remain in the temporary workspace.
"""

from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess, sys

P = Path("/Volumes/Data/Projects/Whirlwind/projects")
ROOT = Path(__file__).resolve().parents[4]
p = argparse.ArgumentParser()
p.add_argument("phase", choices=["prepare", "build", "tests", "notebook"])
p.add_argument(
    "--root", type=Path, default=Path("/private/tmp/rk-turn3-complete-project-bootstrap")
)
args = p.parse_args()
B = args.root
if args.phase == "prepare":
    B.mkdir(parents=True, exist_ok=False)
    manifest = {}
    for project in ("mandarin", "east-whisman"):
        dest = B / project
        dest.mkdir()
        for name in ("spec", "inputs", "tests", "notebooks", "presentation"):
            source = P / project / name
            if source.is_dir():
                shutil.copytree(
                    source,
                    dest / name,
                    ignore=shutil.ignore_patterns(
                        "__pycache__", ".pytest_cache", ".ipynb_checkpoints"
                    ),
                )
        for name in ("pyproject.toml", "uv.lock"):
            shutil.copy2(P / project / name, dest / name)
        # The installed-wheel environment has no sibling source checkout.
        config = dest / "pyproject.toml"
        shutil.copy2(config, dest / "pyproject.source.toml")
        config.write_text(
            config.read_text().replace(
                'extra-paths = ["../../../Rangekeeper/src"]', "extra-paths = []"
            )
        )
        (dest / "docs").mkdir()
        for source in (P / project / "docs").glob("*.json"):
            shutil.copy2(source, dest / "docs" / source.name)
        for file in (dest / "inputs").rglob("*"):
            if file.is_file():
                manifest[str(file.relative_to(B))] = hashlib.sha256(
                    file.read_bytes()
                ).hexdigest()
    (B / "source-hashes.json").write_text(json.dumps(manifest, indent=2))
    print("Prepared current sources only")
else:
    import rangekeeper

    assert "/rk-turn3-project-venv/" in rangekeeper.__file__, rangekeeper.__file__
    assert "PYTHONPATH" not in os.environ, os.environ.get("PYTHONPATH")
    print("Installed import:", rangekeeper.__file__, flush=True)
    if args.phase == "build":
        from rangekeeper.workflow.workbench import build
        from collections import Counter

        for project, spec, name in [
            ("mandarin", "spec", "mandarin"),
            ("east-whisman", "spec/december", "december"),
            ("east-whisman", "spec/november-r2", "november-r2"),
        ]:
            attempt = build(
                B / project / spec,
                input_root=B / project / "inputs",
                output_root=B / "results" / name,
            )
            assert attempt.result is not None, attempt.diagnostics
            print(
                json.dumps(
                    {
                        "name": name,
                        "directory": str(attempt.directory),
                        "entities": len(attempt.result.model.find_entities()),
                        "relationships": len(attempt.result.model.system.relationships),
                        "checks": dict(
                            Counter(c.status for c in attempt.result.checks)
                        ),
                    }
                ),
                flush=True,
            )
    elif args.phase == "tests":
        for project in ("mandarin", "east-whisman"):
            for command in (
                [sys.executable, "-m", "pytest", "tests", "-q", "--tb=short"],
                [str(Path(sys.executable).parent / "ruff"), "check", "tests"],
                [
                    str(Path(sys.executable).parent / "ty"),
                    "check",
                    "tests",
                    "--python",
                    sys.executable,
                    "--config",
                    "environment.extra-paths=[]",
                ],
            ):
                result = subprocess.run(command, cwd=B / project, check=True)
                print(project, command, "passed", flush=True)
    else:
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "docs/research/full-migration/turn2/run_notebook.py"),
                str(B / "mandarin/notebooks/01_workflow_review.ipynb"),
                str(B / "mandarin-review.ipynb"),
                "--cwd",
                str(B / "mandarin"),
            ],
            cwd=B,
            check=True,
        )
    # Source preservation applies after every phase, including notebooks.
    for name, digest in json.loads((B / "source-hashes.json").read_text()).items():
        assert hashlib.sha256((B / name).read_bytes()).hexdigest() == digest, name
