"""Run with mypy==1.18.2 installed; check valid and deliberately invalid calls."""

from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="rk-mypy-") as cache:
    command = [
        sys.executable,
        "-m",
        "mypy",
        "--follow-imports=silent",
        "--ignore-missing-imports",
        "--cache-dir=" + cache,
    ]
    sources = [
        "rangekeeper/_schema/records.py",
        "rangekeeper/_records.py",
        "rangekeeper/diagnostics.py",
        "rangekeeper/errors.py",
        "rangekeeper/validate.py",
        "rangekeeper/_validation.py",
        "rangekeeper/model",
        "rangekeeper/duration",
        "rangekeeper/calculations",
        "rangekeeper/formulations",
        "rangekeeper/scenarios",
        "rangekeeper/policies",
        "rangekeeper/examples",
        "rangekeeper/adapters/plotting.py",
        "rangekeeper/migration",
        "rangekeeper/adapters/pandas.py",
        "rangekeeper/adapters/polars.py",
        "rangekeeper/specification",
        "rangekeeper/units.py",
        "rangekeeper/references.py",
        "rangekeeper/_comparison.py",
        "rangekeeper/run",
        "rangekeeper/io",
        "rangekeeper/execution",
        "rangekeeper/graph/__init__.py",
        "rangekeeper/graph/view.py",
        "rangekeeper/graph/projection.py",
        "rangekeeper/table.py",
        "rangekeeper/adapters/speckle",
        "rangekeeper/adapters/cytoscape/layout",
        "rangekeeper/workflow/workbench.py",
        "rangekeeper/workflow/layout_review.py",
        "rangekeeper/workflow/progress.py",
        "rangekeeper/workflow/_artifacts.py",
        "rangekeeper/workflow/runtime.py",
        "rangekeeper/workflow/composition.py",
        "rangekeeper/workflow/provenance.py",
        "rangekeeper/graph/hierarchy.py",
        "rangekeeper/graph/membership.py",
        "rangekeeper/graph/selection.py",
        "rangekeeper/graph/reduction.py",
        "rangekeeper/graph/reducers.py",
        "rangekeeper/__init__.py",
    ]
    subprocess.run(
        command
        + sources
        + [
            str(Path(__file__).with_name(name))
            for name in (
                "typing_valid.py",
                "typing_domain_valid.py",
                "typing_io_valid.py",
                "typing_execution_valid.py",
                "typing_graph_valid.py",
                "typing_consumers_valid.py",
            )
        ],
        cwd=ROOT / "src",
        check=True,
    )
    result = subprocess.run(
        command + [str(Path(__file__).with_name("typing_invalid.py"))],
        cwd=ROOT / "src",
        text=True,
        capture_output=True,
    )
    print(result.stdout)
    assert result.returncode == 1, result.stderr
    assert result.stdout.count(": error:") == 8, result.stdout
    print("Verified eight intended static rejections")
    result = subprocess.run(
        command + [str(Path(__file__).with_name("typing_domain_invalid.py"))],
        cwd=ROOT / "src",
        text=True,
        capture_output=True,
    )
    print(result.stdout)
    assert result.returncode == 1, result.stderr
    assert result.stdout.count(": error:") == 6, result.stdout
    print("Verified six intended domain API static rejections")

    result = subprocess.run(
        command + [str(Path(__file__).with_name("typing_io_invalid.py"))],
        cwd=ROOT / "src",
        text=True,
        capture_output=True,
    )
    print(result.stdout)
    assert result.returncode == 1, result.stderr
    assert result.stdout.count(": error:") == 5, result.stdout
    print("Verified five intended Run/IO static rejections")
    result = subprocess.run(
        command + [str(Path(__file__).with_name("typing_execution_invalid.py"))],
        cwd=ROOT / "src",
        text=True,
        capture_output=True,
    )
    print(result.stdout)
    assert result.returncode == 1, result.stderr
    assert result.stdout.count(": error:") == 4, result.stdout
    print("Verified four intended execution API static rejections")
    result = subprocess.run(
        command + [str(Path(__file__).with_name("typing_graph_invalid.py"))],
        cwd=ROOT / "src",
        text=True,
        capture_output=True,
    )
    print(result.stdout)
    assert result.returncode == 1, result.stderr
    assert result.stdout.count(": error:") == 5, result.stdout
    print("Verified five intended graph API static rejections")

    result = subprocess.run(
        command + [str(Path(__file__).with_name("typing_consumers_invalid.py"))],
        cwd=ROOT / "src",
        text=True,
        capture_output=True,
    )
    print(result.stdout)
    assert result.returncode == 1, result.stderr
    assert result.stdout.count(": error:") == 3, result.stdout
    print("Verified three intended consumer API static rejections")
