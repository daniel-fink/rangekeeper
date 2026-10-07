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
    # Check every active runtime owner explicitly; followed imports are not evidence.
    sources = [
        str(path.relative_to(ROOT / "src"))
        for path in sorted((ROOT / "src/rangekeeper").rglob("*.py"))
        if "legacy" not in path.parts and path.name != "native.py"
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
                "typing_behavior_valid.py",
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
    assert result.stdout.count(": error:") == 9, result.stdout
    print("Verified nine intended static rejections")
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

    result = subprocess.run(
        command + [str(Path(__file__).with_name("typing_behavior_invalid.py"))],
        cwd=ROOT / "src",
        text=True,
        capture_output=True,
    )
    print(result.stdout)
    assert result.returncode == 1, result.stderr
    assert result.stdout.count(": error:") == 6, result.stdout
    print("Verified six intended record behaviour static rejections")
