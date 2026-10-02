"""Build an isolated wheel and test its record boundary outside the checkout.

Run in the schema tool environment (setuptools>=77 and pip required). Only the
record boundary's dependencies are copied into a fresh venv; this is intentionally
not acceptance of the rest of the distribution or its service integrations.
"""

import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--runtime-python", default=sys.executable)
args = parser.parse_args()
DEPENDENCIES = (
    "jsonschema",
    "jsonschema-specifications",
    "referencing",
    "rpds-py",
    "attrs",
    "typing-extensions",
    "rfc3339-validator",
    "six",
)
with tempfile.TemporaryDirectory(prefix="rk-installed-records-") as directory:
    temp = Path(directory)
    stage = temp / "stage"
    stage.mkdir()
    for name in ("pyproject.toml", "README.md"):
        shutil.copy2(ROOT / "src" / name, stage / name)
    shutil.copytree(
        ROOT / "src/rangekeeper",
        stage / "rangekeeper",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules"),
    )
    wheel_dir = temp / "wheel"
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from setuptools.build_meta import build_wheel; build_wheel('"
            + str(wheel_dir)
            + "')",
        ],
        cwd=stage,
        check=True,
    )
    venv = temp / "venv"
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True
    )
    python = venv / "bin/python"
    site = Path(
        subprocess.check_output(
            [
                str(python),
                "-c",
                "import sysconfig; print(sysconfig.get_path('purelib'))",
            ],
            text=True,
        ).strip()
    )
    wheel = next(wheel_dir.glob("*.whl"))
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--no-compile",
            "--target",
            str(site),
            str(wheel),
        ],
        check=True,
    )
    for name in DEPENDENCIES:
        distribution = importlib.metadata.distribution(name)
        for item in distribution.files:
            if ".." in item.parts or "__pycache__" in item.parts:
                continue
            source = distribution.locate_file(item)
            if source.is_file():
                target = site / item
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    script = """
from importlib.resources import files
import importlib.util
import sys
from uuid import uuid4
import rangekeeper
from rangekeeper._schema.records import Model, Metadata, Runtime
from rangekeeper.model.validation import validate
from rangekeeper.errors import ValidationError
assert 'stage' not in rangekeeper.__file__
assert 'site-packages' in rangekeeper.__file__
assert validate(Model(metadata=Metadata(id=uuid4(), schema_version='0.3.0'))).valid
assert files('rangekeeper').joinpath('py.typed').is_file()
assert files('rangekeeper').joinpath('_currencies.json').is_file()
for name in ('schema.json', 'slots.json', 'manifest.json', 'native.py'):
    assert files('rangekeeper._schema').joinpath(name).is_file()
data = {'implementations': [{'kind': 'evaluator', 'name': 'test', 'version': '1'}],
        'started_at': '2026-10-02T00:00:00Z'}
Runtime.from_data(data)
try:
    Runtime.from_data({**data, 'started_at': 'not-a-timestamp'})
except ValidationError as error:
    assert any(issue.path == '/started_at' for issue in error.report.issues)
else:
    raise AssertionError('timestamp format silently accepted')
for name in ('linkml', 'linkml_runtime', 'numpy', 'pandas', 'pint', 'pyomo', 'specklepy'):
    assert importlib.util.find_spec(name) is None, name
assert 'rangekeeper.graph' not in sys.modules
from rangekeeper.model import Model as DomainModel, Entity, System, Update
from rangekeeper.specification import Specification, SpecificationRecord, compose, validate as validate_composition
entity = Entity(id=uuid4(), code='A')
domain = DomainModel.create(metadata=Metadata(id=uuid4(), schema_version='0.3.0'), system=System(entities=(entity,)))
assert domain.entity(entity.id).code == 'A'
revised = domain.revise(Update(system=System()))
assert revised.metadata.previous == domain.id
spec = Specification(SpecificationRecord(metadata=Metadata(id=uuid4(), schema_version='0.4.0'), model=domain.id))
class Resolver:
    def load_model(self, id):
        assert id == domain.id
        return domain
    def load_specification(self, id):
        raise AssertionError('No includes expected')
composition = compose(spec, resolver=Resolver())
assert validate_composition(composition, resolver=Resolver()).valid
assert 'pint' not in sys.modules and 'rangekeeper.graph' not in sys.modules
print('Installed wheel: records, packaged artifacts, validation, timestamps and lightweight imports passed')
print('Installed wheel: public Model lookup/revision and Specification composition/validation passed')
assert rangekeeper.Model is DomainModel and rangekeeper.Specification is Specification
from pathlib import Path
from tempfile import TemporaryDirectory
from rangekeeper.run import Run, RunRecord, Report, Status, Diagnostic
from rangekeeper.io import json, yaml, MemoryStore, DirectoryStore
assert rangekeeper.Run is Run
try:
    yaml.dumps(domain)
except ImportError as error:
    assert 'rangekeeper[yaml]' in str(error)
else:
    raise AssertionError('YAML should be absent in the base environment')
failed = Run(RunRecord(metadata=Metadata(id=uuid4(), schema_version='0.1.0'),
    specification=spec.id, report=Report(status=Status(completion='failed', solution='not_assessed'),
    diagnostics=(Diagnostic(severity='error', code='unsupported', message='Fixture-only failed attempt'),))))
with TemporaryDirectory() as directory:
    for store in (MemoryStore(), DirectoryStore(Path(directory) / 'records')):
        for doc in (domain, spec, failed):
            store.put(doc)
            assert json.loads(json.dumps(doc), kind=type(doc)).to_data() == doc.to_data()
        assert store.load_run(failed.id).to_data() == failed.to_data()
for prefix in ('yaml', 'pint', 'pandas', 'numpy', 'networkx', 'matplotlib', 'specklepy', 'pyomo', 'highspy', 'rangekeeper.graph'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
print('Installed wheel: all public roots, JSON and both revision stores passed without optional imports')
"""
    subprocess.run([str(python), "-I", "-c", script], cwd=temp, check=True)
    # Exercise unit-bearing fixtures and the optional YAML extra in the same isolated
    # wheel after installing only the additional declared domain dependencies.
    copy_dependencies = """
from importlib.metadata import distribution
from pathlib import Path
import shutil, sys
site = Path(sys.argv[1])
for name in ('Pint', 'flexcache', 'flexparser', 'platformdirs', 'PyYAML'):
    dist = distribution(name)
    for item in dist.files:
        if '..' in item.parts or '__pycache__' in item.parts:
            continue
        source = dist.locate_file(item)
        if source.is_file():
            target = site / item
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
"""
    subprocess.run([args.runtime_python, "-c", copy_dependencies, str(site)], cwd=temp, check=True)
    shutil.copytree(ROOT / "schema/examples", temp / "examples")
    script = """
from pathlib import Path
import sys
import rangekeeper as rk
from rangekeeper.io import json, yaml, MemoryStore, DirectoryStore
from rangekeeper.run import validate
from rangekeeper.specification import compose, validate as validate_composition
examples = Path('examples')
models = [yaml.read(path, kind=rk.Model) for path in sorted(examples.glob('model*.yaml'))]
specs = [yaml.read(path, kind=rk.Specification) for path in sorted(examples.glob('specification*.yaml'))]
runs = [yaml.read(examples / ('run-' + name + '.yaml'), kind=rk.Run) for name in ('forward', 'inverse', 'failed', 'skipped', 'batch')]
for store in (MemoryStore(), DirectoryStore(Path('revisions'))):
    for doc in models + specs + runs:
        store.put(doc)
        assert json.loads(json.dumps(doc), kind=type(doc)).to_data() == doc.to_data()
        assert yaml.loads(yaml.dumps(doc), kind=type(doc)).to_data() == doc.to_data()
    for run in runs:
        assert validate(store.load_run(run.id), resolver=store).valid
    spec = yaml.read(examples / 'specification-composed-forward.yaml', kind=rk.Specification)
    assert validate_composition(compose(spec, resolver=store), resolver=store).valid
for prefix in ('linkml', 'linkml_runtime', 'numpy', 'pandas', 'networkx', 'matplotlib', 'specklepy', 'pyomo', 'highspy', 'rangekeeper.graph'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
print('Installed wheel: all unit-bearing Model/Specification/Run fixtures, composition, JSON/YAML and both stores passed')
"""
    subprocess.run([str(python), "-I", "-c", script], cwd=temp, check=True)
    print(
        json.dumps(
            {name: importlib.metadata.version(name) for name in DEPENDENCIES},
            sort_keys=True,
        )
    )
