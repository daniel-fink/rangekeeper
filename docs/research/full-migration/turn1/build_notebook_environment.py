"""Build and unpack a wheel in an isolated directory for notebook acceptance.

Use the pinned schema interpreter (setuptools>=77) to run this script. Notebook
runtime dependencies stay in the separate runtime environment. PYTHONPATH points
first to the unpacked wheel; the notebook and inspection verify every RK import.
"""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, sys, zipfile
ROOT = Path(__file__).resolve().parents[4]
parser=argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=Path('/private/tmp/rk-foundations-installed'))
OUT=parser.parse_args().output.resolve()
if OUT.exists():
    raise SystemExit('Output already exists; choose a fresh verification directory')
OUT.mkdir()
stage = OUT/'stage'
stage.mkdir()
for name in ('pyproject.toml','README.md'):
    shutil.copy2(ROOT/'src'/name, stage/name)
shutil.copytree(ROOT/'src/rangekeeper', stage/'rangekeeper', ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
subprocess.run([sys.executable,'-c',"from setuptools.build_meta import build_wheel; build_wheel('../wheel')"], cwd=stage, check=True)
wheel=next((OUT/'wheel').glob('*.whl'))
with zipfile.ZipFile(wheel) as z:
    z.extractall(OUT/'site')
print(json.dumps({'wheel':str(wheel),'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'site':str(OUT/'site')}))
