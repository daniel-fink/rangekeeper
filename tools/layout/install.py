"""Install the checksum-pinned optional MiniZinc bundle into an explicit directory.

Uses official release assets. Existing directories are never overwritten. macOS
requires permission to mount a disk image; Linux uses safe tar extraction. No
shell profile, PATH, repository dependency or system solver setting is changed.
"""

import argparse
import hashlib
import json
import platform
import shutil
import shlex
import subprocess
import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlopen


def install(destination, archive=None):
    pins = json.loads(Path(__file__).with_name("toolchain.json").read_text())
    system = platform.system()
    key = f"{system}-{platform.machine()}"
    if key not in pins["bundles"]:
        raise ValueError(f"No pinned bundle for {key}; install MiniZinc explicitly")
    if destination.exists():
        raise FileExistsError(f"Refusing to replace {destination}")
    bundle = pins["bundles"][key]
    with tempfile.TemporaryDirectory(prefix="rk-minizinc-install-") as temp:
        work = Path(temp)
        if archive is None:
            archive = work / Path(bundle["url"]).name
            with urlopen(bundle["url"], timeout=60) as response, archive.open(
                "wb"
            ) as out:
                shutil.copyfileobj(response, out)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != bundle["sha256"]:
            raise ValueError(f"Bundle checksum mismatch: {archive}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if system == "Darwin":
            mount = work / "mount"
            subprocess.run(
                [
                    "hdiutil",
                    "attach",
                    "-nobrowse",
                    "-readonly",
                    "-mountpoint",
                    str(mount),
                    str(archive),
                ],
                check=True,
                timeout=120,
            )
            try:
                subprocess.run(
                    [
                        "ditto",
                        str(mount / "MiniZincIDE.app"),
                        str(destination / "MiniZincIDE.app"),
                    ],
                    check=True,
                    timeout=120,
                )
            finally:
                subprocess.run(
                    ["hdiutil", "detach", str(mount)], check=True, timeout=30
                )
            executable = destination / "MiniZincIDE.app/Contents/Resources/minizinc"
        else:
            unpacked = work / "unpacked"
            with tarfile.open(archive) as source:
                source.extractall(unpacked, filter="data")
            roots = list(unpacked.iterdir())
            if len(roots) != 1 or not (roots[0] / "bin/minizinc").is_file():
                raise ValueError("Unexpected MiniZinc archive structure")
            shutil.copytree(roots[0], destination, symlinks=True)
            executable = destination / "bin/minizinc"
        receipt = {
            "platform": key,
            "url": bundle["url"],
            "sha256": digest,
            "executable": str(executable),
        }
        (destination / "installation.json").write_text(
            json.dumps(receipt, indent=2) + "\n"
        )
        shell = f"export RK_MINIZINC={shlex.quote(str(executable))}\n"
        if system == "Linux":
            shell += f'export LD_LIBRARY_PATH={shlex.quote(str(destination / "lib"))}${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}\n'
        (destination / "env.sh").write_text(shell)
        return executable


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument(
        "--archive",
        type=Path,
        help="use a previously downloaded, checksum-verified asset",
    )
    args = parser.parse_args()
    print(install(args.directory.expanduser().resolve(), args.archive))
