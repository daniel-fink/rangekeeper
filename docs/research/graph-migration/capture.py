"""Capture final results and confirm preservation against this slice's starting files."""
from pathlib import Path
import hashlib
import json
import subprocess
import tarfile
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
initial = json.loads((OUT / 'initial.json').read_text())
verified = json.loads((OUT / 'verified-sources.json').read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert all(sha(ROOT / path) == digest for path, digest in verified.items())
protected = [path for path in initial['files'] if
    path == '.gitignore' or path.startswith((
        'src/rangekeeper/execution/', 'src/rangekeeper/model/',
        'src/rangekeeper/specification/', 'src/rangekeeper/run/',
        'src/rangekeeper/io/', 'src/rangekeeper/_schema/',
        'schema/examples/', 'schema/checks/', 'docs/research/scalar-execution/',
    )) or (path.startswith('schema/') and path.endswith('.yaml'))]
assert all(sha(ROOT / path) == initial['files'][path] for path in protected)
for name in ('view', 'reduction'):
    original = subprocess.check_output(['git', 'show', f"{initial['head']}:src/rangekeeper/graph/{name}.py"], cwd=ROOT, text=True)
    if name == 'view':
        for module in ('assembly', 'classification', 'entity', 'errors', 'graph', 'relationship'):
            original = original.replace(f'from .{module} import', f'from ..{module} import')
    else:
        original = original.replace('from ..measure import', 'from ...measure import').replace('from .entity import', 'from ..entity import').replace('from .errors import', 'from ..errors import')
    assert original == (ROOT / f'src/rangekeeper/graph/legacy/{name}.py').read_text()
xml = ElementTree.parse(OUT / 'pytest.xml')
cases = xml.findall('.//testcase')
failures = [f"{item.attrib['classname']}::{item.attrib['name']}" for item in cases if item.find('failure') is not None]
assert sorted(failures) == sorted([
    'tests.test_adapters::test_supported_adapter_and_table_surfaces_are_explicit',
    'tests.test_formulas.TestSolver::test_residual',
])
assert not xml.findall('.//error') and not xml.findall('.//skipped')
commands = [json.loads(line) for line in (OUT / 'commands.jsonl').read_text().splitlines()]
# Preserve exact log references without guessing timestamp suffixes.
logs = {}
for label in ('environment', 'schema-environment', 'generation', 'typing', 'native', 'installed', 'pytest'):
    logs[label] = next(item['log'] for item in reversed(commands) if item['log'] == label+'.log' or item['log'].startswith(label+'-') and item['log'][len(label)+1:].split('.')[0].isdigit())
report = {
    'starting_head': initial['head'], 'executed': len(cases), 'passed': len(cases)-len(failures),
    'failures': failures, 'new_model_graph_cases': sum(item.attrib['classname']=='tests.test_model_graph' for item in cases),
    'protected_files_unchanged': len(protected), 'verified_source_files': len(verified),
    'legacy_algorithm_changes': 'Only relative imports changed when relocating View and reduction.',
    'latest_logs': logs,
    'changed_existing_files': [path for path,digest in initial['files'].items() if sha(ROOT/path)!=digest],
    'limitations': ['Three live API tests excluded.', 'No remote CI or external project/host acceptance.',
                    'Step 6C-F remain; legacy table/adapters/workflows still use the old domain.',
                    'No staging, commit or push commands issued; pre-existing index state preserved.'],
}
(OUT / 'summary.json').write_text(json.dumps(report, indent=2)+'\n')
with tarfile.open(OUT/'evidence.tar.gz', 'w:gz') as archive:
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.suffix in ('.log','.xml','.json','.jsonl','.py'):
            archive.add(path, arcname=path.name)
print(json.dumps(report,indent=2))
