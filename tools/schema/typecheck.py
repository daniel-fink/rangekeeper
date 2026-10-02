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
        "rangekeeper/specification",
        "rangekeeper/units.py",
        "rangekeeper/references.py",
        "rangekeeper/_comparison.py",
        "rangekeeper/run",
        "rangekeeper/io",
        "rangekeeper/__init__.py",
    ]
    subprocess.run(
        command
        + sources
        + [
            str(Path(__file__).with_name(name))
            for name in ("typing_valid.py", "typing_domain_valid.py", "typing_io_valid.py")
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
        cwd=ROOT / "src", text=True, capture_output=True,
    )
    print(result.stdout)
    assert result.returncode == 1, result.stderr
    assert result.stdout.count(": error:") == 5, result.stdout
    print("Verified five intended Run/IO static rejections")
