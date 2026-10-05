"""Capture final input fingerprints, environment and API signatures."""
from pathlib import Path
import ast, hashlib, importlib.metadata as metadata, json, platform, subprocess, sys
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
packages=sorted({d.metadata['Name'] for d in metadata.distributions() if d.metadata.get('Name')},key=str.lower)
versions={name:metadata.version(name) for name in packages}
files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
       for directory in ['src/rangekeeper','schema','src/tests','tools/schema']
       for p in sorted((ROOT/directory).rglob('*'))
       if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py','.yaml','.json','.toml'}}
sys.path.insert(0, str(ROOT / "src"))
import rangekeeper
initial=json.loads((OUT/'baseline/initial-state.json').read_text())
assert hashlib.sha256((ROOT/'.gitignore').read_bytes()).hexdigest()==initial['tracked_sha256']['.gitignore']
assert subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT,text=True)==''
state=dict(python=sys.version,executable=sys.executable,platform=platform.platform(),
           import_path=rangekeeper.__file__,sys_path=sys.path,selected_packages=versions,
           input_sha256=files,unrelated_gitignore_preserved=True,index_empty=True,
           head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
(OUT/'verification/final-state.json').write_text(json.dumps(state,indent=2)+'\n')
(OUT/'verification/runtime-requirements.txt').write_text('\n'.join(f'{name}=={version}' for name,version in versions.items() if name.lower()!='rangekeeper')+'\n')
paths=[]
for package in ['calculations','temporal','migration']:
    paths.extend((ROOT/'src/rangekeeper'/package).rglob('*.py'))
paths.extend(ROOT/'src/rangekeeper'/p for p in ['model/flow.py','model/content.py','model/duration.py','adapters/pandas.py','adapters/polars.py'])
items=[]
for p in sorted(paths):
    def visit(nodes,prefix=''):
        for n in nodes:
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
                items.append(dict(module=str(p.relative_to(ROOT)),symbol=prefix+n.name,arguments=ast.unparse(n.args),returns=ast.unparse(n.returns) if n.returns else None,docstring=ast.get_docstring(n)))
            elif isinstance(n,ast.ClassDef): visit(n.body,prefix+n.name+'.')
    visit(ast.parse(p.read_text()).body)
(OUT/'api.json').write_text(json.dumps(items,indent=2)+'\n')
print(json.dumps({'files':len(files),'callables':len(items),'unrelated_gitignore_preserved':True,'index_empty':True}))
