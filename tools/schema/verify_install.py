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
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--runtime-python", default=sys.executable)
parser.add_argument(
    "--wheel", type=Path, help="Verify this exact prebuilt artifact without rebuilding"
)
parser.add_argument(
    "--execution-python",
    help="Also verify the optional solver extra, copying its dependencies from this interpreter",
)
parser.add_argument(
    "--workflow-python",
    help="Verify source workflows; copy openpyxl dependencies from this interpreter",
)
parser.add_argument(
    "--financial-python",
    help="Verify the PyXIRR financial wrapper without SciPy or dataframe dependencies",
)
parser.add_argument(
    "--tables-python", help="Verify Polars and CSV with no pandas installed"
)
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
    "py-moneyed",
    "Babel",
)
with tempfile.TemporaryDirectory(prefix="rk-installed-records-") as directory:
    temp = Path(directory)
    if args.wheel is None:
        stage = temp / "stage"
        stage.mkdir()
        for name in ("pyproject.toml", "README.md", "LICENSE"):
            shutil.copy2(ROOT / name, stage / name)
        shutil.copytree(
            ROOT / "src/rangekeeper",
            stage / "src/rangekeeper",
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
        wheel = next(wheel_dir.glob("*.whl"))
    else:
        wheel = args.wheel.resolve(strict=True)
    with ZipFile(wheel) as archive:
        licenses = [
            name
            for name in archive.namelist()
            if name.endswith(".dist-info/licenses/LICENSE")
        ]
        assert len(licenses) == 1, "wheel must contain the project license"
        assert archive.read(licenses[0]) == (ROOT / "LICENSE").read_bytes()
    venv = temp / "venv"
    subprocess.run(
        [args.runtime_python, "-m", "venv", "--without-pip", str(venv)], check=True
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
    base_dependencies = """
from importlib.metadata import distribution
from pathlib import Path
import json, shutil, sys
site = Path(sys.argv[1])
for name in json.loads(sys.argv[2]):
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
    subprocess.run(
        [
            args.runtime_python,
            "-c",
            base_dependencies,
            str(site),
            json.dumps(DEPENDENCIES),
        ],
        cwd=temp,
        check=True,
    )
    script = """
from importlib.resources import files
import importlib.util
import sys
from uuid import uuid4
from datetime import date
import rangekeeper
from rangekeeper.schema.records import Model, Metadata, Runtime, Period, Flow, Movement, Source
from rangekeeper.model.duration import PeriodTiming
from rangekeeper.model.validation import validate
period = Period(start_inclusive=date(2026, 1, 1), end_exclusive=date(2026, 2, 1))
movement = Movement(id=uuid4(), key="january", period=period)
assert movement.date is None and "date" not in movement.to_data()
flow = Flow(units="AUD", movements=(movement,))
assert set(flow.to_data()) == {"units", "movements"}
assert Flow.from_data(flow.to_data()) == flow
assert type(flow.movements[0]) is Movement and not hasattr(flow, "samples")
assert flow.movements[0].replace(magnitude=3).number == 3.0
assert not flow.replace().movements[0].has_field("magnitude")
assert period.check().resolve(timing=PeriodTiming.LAST) == date(2026, 1, 31)
assert Movement.__doc__ and Movement.magnitude.__doc__
for removed in ("rangekeeper.calculations._flow", "rangekeeper.calculations.distribution", "rangekeeper.model.flow"):
    assert importlib.util.find_spec(removed) is None, removed
import rangekeeper.model.flux as flow_api
assert flow_api.Movement is Movement and not hasattr(flow_api, "FlowSample")
assert not hasattr(flow, "basis") and not hasattr(flow, "kind")
assert type(Period.from_data(period.to_data()).start_inclusive) is date
source = Source(id=uuid4(), name="Schedule", checksum="abc",
    issued_at=date(2026, 1, 1), received_at="2026-01-02T09:30:00+11:00")
assert source.issued_at == date(2026, 1, 1)
assert source.received_at == "2026-01-02T09:30:00+11:00"
print("Installed wheel: date fields and source timestamp alternatives passed")
from rangekeeper.shared.errors import ValidationError
assert 'stage' not in rangekeeper.__file__
assert 'site-packages' in rangekeeper.__file__
assert validate(Model(metadata=Metadata(id=uuid4(), schema_version='0.7.0'))).valid
assert files('rangekeeper').joinpath('py.typed').is_file()
assert not files('rangekeeper').joinpath('_currencies.json').is_file()
from rangekeeper.shared.units import UnitSystem
assert 'py-moneyed/3.0' in UnitSystem.implementation
for name in ('api', 'measure', 'flux', '_legacy_duration', 'distribution', 'extrapolation', 'projection',
             'formula', 'dynamics', 'segmentation', 'policy', 'format', 'space',
             '_schema', '_records', '_record_index', '_revision', '_behaviors',
             'graph', 'formulations', 'duration', 'scenarios', 'policies', 'execution',
             'evidence', 'operation', 'account', 'metadata', 'table', 'units',
             'references', 'diagnostics', 'errors', 'validate', '_validation',
             '_encoding', '_structured', '_yaml', '_implementation'):
    assert importlib.util.find_spec('rangekeeper.' + name) is None, name
    assert not hasattr(rangekeeper, name), name
assert not hasattr(rangekeeper, 'update_class')
assert not hasattr(rangekeeper, 'rgba_from_cmap')
for resource in ('workflow/workbench.py', 'adapters/cytoscape/layout/review.py', 'adapters/cytoscape/assets/viewer.js', 'adapters/cytoscape/layout/assembly.mzn', 'adapters/speckle/contract.json', 'migration/layout.py', 'migration/speckle.py'):
    assert files('rangekeeper').joinpath(resource).is_file(), resource
from rangekeeper.adapters.speckle import decode_model, encode_model
assert 'specklepy' not in sys.modules
for name in ('schema.json', 'slots.json', 'manifest.json', 'native.py'):
    assert files('rangekeeper.schema').joinpath(name).is_file()
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
for name in ('view', 'hierarchy', 'reduction'):
    assert 'rangekeeper.model.system.' + name not in sys.modules
from rangekeeper.model import Model as DomainModel, Entity, System, Update
from rangekeeper.specification import Specification, SpecificationRecord
entity = Entity(id=uuid4(), code='A')
domain = DomainModel.create(metadata=Metadata(id=uuid4(), schema_version='0.7.0'), system=System(entities=(entity,)))
assert domain.entity(entity.id).code == 'A'
revised = domain.revise(Update(system=System()))
assert revised.metadata.previous == domain.id
spec = Specification(SpecificationRecord(metadata=Metadata(id=uuid4(), schema_version='0.7.0'), model=domain.id))
class Resolver:
    def load_model(self, id):
        assert id == domain.id
        return domain
    def load_specification(self, id):
        raise AssertionError('No includes expected')
composition = spec.compose(resolver=Resolver())
assert composition.validate(resolver=Resolver()).valid
assert 'pint' not in sys.modules
for name in ('view', 'hierarchy', 'reduction'):
    assert 'rangekeeper.model.system.' + name not in sys.modules
print('Installed wheel: records, packaged artifacts, validation, timestamps and lightweight imports passed')
print('Installed wheel: public Model lookup/revision and Specification composition/validation passed')
assert rangekeeper.Model is DomainModel and rangekeeper.Specification is Specification
from pathlib import Path
from tempfile import TemporaryDirectory
from rangekeeper.run import Run, RunRecord, Report, Status, Diagnostic, CompletionStatus, SolutionStatus, Severity
from rangekeeper.io import json, yaml, MemoryStore, DirectoryStore
assert rangekeeper.Run is Run
try:
    yaml.dumps(domain)
except ImportError as error:
    assert 'rangekeeper[yaml]' in str(error)
else:
    raise AssertionError('YAML should be absent in the base environment')
failed = Run(RunRecord(metadata=Metadata(id=uuid4(), schema_version='0.4.0'),
    specification=spec.id, report=Report(status=Status(completion=CompletionStatus.FAILED, solution=SolutionStatus.NOT_ASSESSED),
    diagnostics=(Diagnostic(severity=Severity.ERROR, code='unsupported', message='Fixture-only failed attempt'),))))
with TemporaryDirectory() as directory:
    for store in (MemoryStore(), DirectoryStore(Path(directory) / 'records')):
        for doc in (domain, spec, failed):
            store.put(doc)
            assert json.loads(json.dumps(doc), kind=type(doc)).to_data() == doc.to_data()
        assert store.load_run(failed.id).to_data() == failed.to_data()
for prefix in ('yaml', 'pint', 'pandas', 'numpy', 'networkx', 'matplotlib', 'specklepy', 'pyomo', 'highspy', 'rangekeeper.model.system.view', 'rangekeeper.model.system.hierarchy', 'rangekeeper.model.system.reduction'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
print('Installed wheel: all public roots, JSON and both revision stores passed without optional imports')
from rangekeeper.model.system import View, Hierarchy
view = View(domain)
assert view.entity(entity.id) is domain.entity(entity.id)
assert Hierarchy.from_relationships(view).preorder() == (entity.id,)
for prefix in ('pint', 'numpy', 'networkx', 'pandas', 'pyomo', 'highspy', 'rangekeeper.legacy', 'rangekeeper.graph'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
from rangekeeper.model.system.projection import to_table
from rangekeeper.shared.table import Table
from rangekeeper.adapters.cytoscape import project, write_viewer
assert to_table(view).column('model_id') == (domain.id,)
assert to_table(Hierarchy.from_relationships(view)).column('parent_id') == (None,)
with TemporaryDirectory() as destination:
    exported = write_viewer([project(domain, 'Installed Model')], Path(destination) / 'viewer.html')
    assert exported.is_file() and 'cytoscape' in exported.read_text()
for prefix in ('pint', 'numpy', 'networkx', 'pandas', 'pyomo', 'highspy', 'rangekeeper.legacy', 'rangekeeper.graph'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
print('Installed wheel: Model graph, tables and offline viewer assets passed without legacy or numerical imports')
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
    subprocess.run(
        [args.runtime_python, "-c", copy_dependencies, str(site)], cwd=temp, check=True
    )
    shutil.copytree(ROOT / "examples/schema", temp / "examples")
    script = """
from pathlib import Path
import sys
import rangekeeper as rk
from rangekeeper.io import json, yaml, MemoryStore, DirectoryStore
from rangekeeper.run import validate, CompletionStatus, SolutionStatus
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
    assert spec.compose(resolver=store).validate(resolver=store).valid
    from rangekeeper.run.execution import Executor
    unavailable = Executor(store).execute(spec)
    assert unavailable.report.status.completion is CompletionStatus.FAILED
    assert unavailable.report.status.solution is SolutionStatus.NOT_ASSESSED
    assert any(d.code == 'backend_unavailable' for d in unavailable.report.diagnostics)
for prefix in ('linkml', 'linkml_runtime', 'numpy', 'pandas', 'networkx', 'matplotlib', 'specklepy', 'pyomo', 'highspy', 'rangekeeper.model.system.view', 'rangekeeper.model.system.hierarchy', 'rangekeeper.model.system.reduction'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
print('Installed wheel: all unit-bearing Model/Specification/Run fixtures, composition, JSON/YAML and both stores passed')
from uuid import uuid4
from rangekeeper.model.system import View, Hierarchy, Reduction
from rangekeeper.model.system.selection import select_value
from rangekeeper.model.system import reducers
from rangekeeper.model import Metadata, Definitions, Measure, System, Entity, Assembly, Characteristics, Value, ValueKind, Quantity
measure = Measure(id=uuid4(), code='area', name='Area', units='meter ** 2')
value = Value(id=uuid4(), key='net', kind=ValueKind.MEASUREMENT, measure=measure.id, quantity=Quantity(magnitude=12, units='meter ** 2'))
entity = Entity(id=uuid4(), characteristics=Characteristics(values=(value,)))
group = Assembly(id=uuid4(), entities=(entity.id,))
model = rk.Model.create(metadata=Metadata(id=uuid4(), schema_version='0.7.0'), definitions=Definitions(measures=(measure,)), system=System(entities=(entity,), assemblies=(group,)))
hierarchy = Hierarchy.from_membership(View(model, assembly=group.id), root=group.id)
result = Reduction(select=select_value('net'), reducer=reducers.sum, units='centimeter ** 2', contributors=lambda item: item.id == entity.id).execute(hierarchy)
assert result.root_value.magnitude == 120000 and result.coverage(group.id).complete
assert result.value_ids[entity.id] == value.id
assert json.loads(json.dumps(model), kind=rk.Model).to_data() == model.to_data()
for prefix in ('networkx', 'pandas', 'rangekeeper.legacy', 'rangekeeper.graph', 'pyomo', 'highspy'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
print('Installed wheel: canonical membership, explicit Value reduction, coverage and conversion passed')
"""
    subprocess.run([str(python), "-I", "-c", script], cwd=temp, check=True)
    if args.financial_python:
        financial_dependencies = copy_dependencies.replace(
            "('Pint', 'flexcache', 'flexparser', 'platformdirs', 'PyYAML')",
            "('pyxirr',)",
        )
        subprocess.run(
            [args.financial_python, "-c", financial_dependencies, str(site)],
            cwd=temp,
            check=True,
        )
        script = """from rangekeeper.model.flux import Flow

from datetime import date
import math, sys
import pyxirr
from rangekeeper.calculations.financial import calculate_pv, calculate_xnpv, calculate_irr

from rangekeeper.model.duration import make_periods, Frequency, PeriodTiming
flow = Flow.from_events([date(2026, 1, 1), date(2027, 1, 1)], [-100, 110], units='AUD')
assert abs(calculate_xnpv(flow, rate=.1, valuation_date=date(2026, 1, 1)).magnitude) < 1e-9
result = calculate_irr(flow)
assert math.isclose(result.rate, .1) and result.method == 'pyxirr.xirr'
assert abs(result.residual.magnitude) < 1e-9
future = Flow.from_periods(make_periods(date(2026, 1, 1), frequency=Frequency.YEAR, count=1), [110], units='AUD')
assert math.isclose(calculate_pv(future, rate=.1).movements[0].magnitude, 100)
assert math.isclose(calculate_xnpv(future, rate=.1, valuation_date=date(2026, 1, 1), timing=PeriodTiming.END).magnitude, 100)
assert calculate_xnpv(Flow.from_events([], [], units='AUD'), rate=0.1, valuation_date=date(2026, 1, 1)).magnitude == 0
for prefix in ('scipy', 'pandas', 'polars', 'numpy', 'rangekeeper.flux', 'rangekeeper._legacy_duration'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
print('Installed wheel: PyXIRR', pyxirr.__version__, 'PV/XNPV/IRR passed without SciPy, dataframes or legacy imports')
"""
        subprocess.run([str(python), "-I", "-c", script], cwd=temp, check=True)
    if args.execution_python:
        execution_dependencies = copy_dependencies.replace(
            "('Pint', 'flexcache', 'flexparser', 'platformdirs', 'PyYAML')",
            "('pyomo', 'highspy', 'numpy')",
        )
        subprocess.run(
            [args.execution_python, "-c", execution_dependencies, str(site)],
            cwd=temp,
            check=True,
        )
        script = """
from pathlib import Path
from uuid import UUID, uuid4
import sys
import rangekeeper as rk
from rangekeeper.io import yaml, DirectoryStore
from rangekeeper.run.execution import Executor
from rangekeeper.run import validate, CompletionStatus, SolutionStatus
for prefix in ('pyomo', 'highspy', 'numpy', 'rangekeeper.model.system.view', 'rangekeeper.model.system.hierarchy', 'rangekeeper.model.system.reduction'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
store = DirectoryStore(Path('executed'))
model = yaml.read(Path('examples/model.yaml'), kind=rk.Model)
store.put(model)
for name in ('specification-common', 'specification-composed-forward', 'specification-composed-inverse'):
    store.put(yaml.read(Path('examples') / (name + '.yaml'), kind=rk.Specification))
forward = Executor(store).execute(yaml.read(Path('examples/specification-composed-forward.yaml'), kind=rk.Specification))
assert forward.report.status.solution is SolutionStatus.FEASIBLE, forward.report
first = store.load_model(forward.record.outputs[0])
assert abs(first.value(UUID('a947d40b-d9b0-54cb-a2a4-f8f598405ac2')).quantity.magnitude - 11000000) < 1e-6
data = yaml.read(Path('examples/specification-inverse.yaml'), kind=rk.Specification).to_data()
data['metadata']['id'] = str(uuid4())
data['model'] = str(first.id)
inverse = Executor(store).execute(rk.Specification.from_data(data))
second = store.load_model(inverse.record.outputs[0])
assert abs(second.value(UUID('e3fb1434-5371-5bcb-b0b8-e3af2bf65022')).quantity.magnitude - 27500) < 1e-6
assert second.metadata.previous == first.id
assert validate(inverse, resolver=store).valid
for prefix in ('pyomo', 'highspy', 'rangekeeper.model.system.view', 'rangekeeper.model.system.hierarchy', 'rangekeeper.model.system.reduction', 'linkml', 'linkml_runtime'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
print('Installed wheel: actual process-isolated forward/inverse solves, output reuse, acceptance and disk publication passed')
"""
        subprocess.run([str(python), "-I", "-c", script], cwd=temp, check=True)
    if args.workflow_python:
        workflow_dependencies = copy_dependencies.replace(
            "('Pint', 'flexcache', 'flexparser', 'platformdirs', 'PyYAML')",
            "('openpyxl', 'et_xmlfile')",
        )
        subprocess.run(
            [args.workflow_python, "-c", workflow_dependencies, str(site)],
            cwd=temp,
            check=True,
        )
        if not args.execution_python:
            raise ValueError(
                "--workflow-python requires --execution-python for the full acceptance example"
            )
        shutil.copy2(ROOT / "examples/workflow/scalar.py", temp / "source-example.py")
        script = """
import importlib.metadata, json, runpy, sys
from pathlib import Path
summary = runpy.run_path('source-example.py')['run_example'](Path('source-example'))
metadata = json.loads(Path('source-example/workflow/manifest.json').read_text())
assert metadata['dependencies']['jsonschema'] == importlib.metadata.version('jsonschema')
assert summary['forward_gross']['magnitude'] == 20
assert summary['inverse_net']['magnitude'] == 25
for prefix in ('rangekeeper.legacy', 'rangekeeper.graph', 'rangekeeper.model.entity', 'rangekeeper.measure', 'networkx', 'pandas', 'pyomo', 'highspy'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
print('Installed wheel: XLSX workflow, Model provenance, YAML/JSON, stores and real forward/inverse execution passed')
"""
        subprocess.run([str(python), "-I", "-c", script], cwd=temp, check=True)
    if args.tables_python:
        table_dependencies = copy_dependencies.replace(
            "('Pint', 'flexcache', 'flexparser', 'platformdirs', 'PyYAML')",
            "('polars', 'polars-runtime-32')",
        )
        subprocess.run(
            [args.tables_python, "-c", table_dependencies, str(site)],
            cwd=temp,
            check=True,
        )
        script = """
import importlib.util
from datetime import date
from pathlib import Path
from uuid import uuid4
import polars as pl
from rangekeeper.model.flux import Flow
from rangekeeper.shared.table import Table
from rangekeeper.adapters import csv, polars
assert importlib.util.find_spec('pandas') is None
assert importlib.util.find_spec('rangekeeper.adapters.pandas') is None
flow = Flow.from_events([date(2026, 1, 1)], [0], units='AUD')
assert polars.from_frame(polars.to_frame(flow), units='AUD') == flow
assert polars.dates(flow)['date'].to_list() == [date(2026, 1, 1)]
table = Table(columns=('code', 'status', 'value'), rows=({'code': '001', 'status': 'NA', 'value': None},))
assert polars.to_table(polars.to_frame(table)) == table
path = csv.write(table, Path('table.csv'))
assert csv.read(path, schema_overrides={'code': pl.String}) == table
mixed = Table(columns=('value',), rows=({'value': uuid4()}, {'value': {'x': (1, 2)}}))
assert polars.to_table(polars.to_frame(mixed)) == mixed
print('Installed wheel: Polars Flow/Table and CSV checks passed with pandas absent')
"""
        subprocess.run([str(python), "-I", "-c", script], cwd=temp, check=True)
    if args.tables_python:
        shutil.copy2(
            ROOT / "examples/rangekeeper_examples/flux.py", temp / "flux_example.py"
        )
        check = "import runpy; example=runpy.run_path('flux_example.py'); assert example['collection']().sum().movements[0].number == 960"
        if args.execution_python:
            check += "; result,ids=example['solve_example'](); assert result.value(ids['portfolio']).flow.movements[0].number == 2880"
        subprocess.run([str(python), "-I", "-c", check], cwd=temp, check=True)
        print("Installed wheel: Stream and acausal hierarchy acceptance example passed")
    # Report the installed candidate's dependency versions, not the build environment.
    subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            "import importlib.metadata, json; print(json.dumps({name: importlib.metadata.version(name) for name in "
            + repr(DEPENDENCIES)
            + "}, sort_keys=True))",
        ],
        cwd=temp,
        check=True,
    )
