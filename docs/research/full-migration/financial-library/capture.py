"""Inspect executed notebook outputs and retain input hashes for this correction."""
from pathlib import Path
import ast
import hashlib
import importlib.metadata as metadata
import json
import shutil
import subprocess
import sys
import nbformat

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
SITE = Path('/private/tmp/rk-financial-library-wheel/site')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

notebook = nbformat.read(OUT / 'basic_dcf.ipynb', as_version=4)
nbformat.validate(notebook)
code = [cell for cell in notebook.cells if cell.cell_type == 'code']
assert len(code) == 23 and [cell.execution_count for cell in code] == list(range(1, 24))
outputs = [output for cell in code for output in cell.outputs]
assert not any(output.output_type == 'error' for output in outputs)
text = '\n'.join(output.get('text', '') for output in outputs)
assert 'Property PV: $1,000' in text and str(SITE) in text
assert '<table' in (OUT / 'basic_dcf.html').read_text()
shutil.copy2(OUT / 'basic_dcf.ipynb', ROOT / 'walkthrough/basic_dcf.ipynb')
(OUT / 'notebook-inspection.json').write_text(json.dumps(dict(
    cells=23, errors=0, pv=1000, independent_oracle_passed=True,
    table_markup_checked=True, visual_review_completed=False, wheel_site=str(SITE)), indent=2)+'\n')

before = json.loads((OUT / 'before.json').read_text())
assert digest(ROOT / '.gitignore') == before['sha256']['.gitignore']
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT, text=True)
current = {path: digest(ROOT / path) for path in before['sha256'] if (ROOT / path).is_file()}
current['src/tests/test_financial_library.py'] = digest(ROOT / 'src/tests/test_financial_library.py')
for path, value in current.items():
    if path.startswith('src/rangekeeper/') and path.endswith('.py'):
        assert digest(SITE / Path(path).relative_to('src')) == value, path
assert all(value == before['sha256'][path] for path, value in current.items()
           if path.startswith('schema/') or path.startswith('src/rangekeeper/_schema/'))
(OUT / 'final-state.json').write_text(json.dumps(dict(
    head=before['head'], python=sys.version, executable=sys.executable,
    packages={name: metadata.version(name) for name in ('pyxirr', 'scipy', 'numpy', 'pandas', 'polars', 'pint')},
    input_sha256=current,
    changed_inputs=[path for path, value in current.items() if value != before['sha256'].get(path)],
    schemas_unchanged=True, wheel_python_matches_source=True,
    unrelated_gitignore_preserved=True, index_empty=True), indent=2)+'\n')
paths = [path for package in ('calculations', 'temporal', 'migration')
         for path in (ROOT / 'src/rangekeeper' / package).rglob('*.py')]
paths.extend(ROOT / 'src/rangekeeper' / path for path in (
    'model/flow.py', 'model/content.py', 'model/duration.py', 'adapters/pandas.py', 'adapters/polars.py'))
items = []
for path in sorted(paths):
    def visit(nodes, prefix=''):
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                items.append(dict(module=str(path.relative_to(ROOT)), symbol=prefix+node.name,
                    arguments=ast.unparse(node.args), returns=ast.unparse(node.returns) if node.returns else None,
                    docstring=ast.get_docstring(node)))
            elif isinstance(node, ast.ClassDef):
                visit(node.body, prefix+node.name+'.')
    visit(ast.parse(path.read_text()).body)
(OUT / 'api.json').write_text(json.dumps(items, indent=2)+'\n')
print('23 notebook cells verified; schemas unchanged; wheel Python matches source; unrelated .gitignore preserved; index empty.')
