"""Static inventory; imports and notebook code are evidence, not compatibility tests."""
import ast, hashlib, json, re, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
files=[]
for p in sorted((ROOT/'src/rangekeeper').rglob('*.py')):
    tree=ast.parse(p.read_text()); symbols=[];imports=[]
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.ClassDef)):
            item=dict(name=node.name,line=node.lineno,kind=type(node).__name__)
            if isinstance(node,ast.ClassDef):item['methods']=[dict(name=n.name,line=n.lineno) for n in node.body if isinstance(n,ast.FunctionDef)]
            symbols.append(item)
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):imports.append(dict(line=node.lineno,module=','.join(n.name for n in node.names)))
        elif isinstance(node,ast.ImportFrom):imports.append(dict(line=node.lineno,module='.'*node.level+(node.module or ''),names=[n.name for n in node.names]))
    files.append(dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),symbols=symbols,imports=imports))
notebooks=[]
for p in sorted((ROOT/'walkthrough').glob('*.ipynb')):
    cells=json.loads(p.read_text()).get('cells',[])
    uses=[dict(cell=i,source_sha256=hashlib.sha256(''.join(c.get('source',[])).encode()).hexdigest(),api_references=sorted(set(re.findall(r'(?:rk|rangekeeper)\.[A-Za-z_][A-Za-z_.]*',''.join(c.get('source',[])))))) for i,c in enumerate(cells) if c.get('cell_type')=='code' and any(k in ''.join(c.get('source',[])) for k in ['rk.','rangekeeper','Speckle'])]
    notebooks.append(dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),usage=uses))
external=Path('/Volumes/Data/Projects/Whirlwind/projects')
external_files=[]
for project in ['mandarin','east-whisman']:
    for prefix in ['tests','spec']:
        for p in sorted((external/project/prefix).rglob('*')):
            if p.is_file() and p.suffix in ('.py','.yaml'):
                lines=[dict(line=i,text=l) for i,l in enumerate(p.read_text().splitlines(),1) if any(x in l for x in ['rangekeeper','rk.','measurements','features'])]
                if lines:external_files.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),references=lines))
external_state=dict(root=str(external),head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=external,text=True).strip(),branch=subprocess.check_output(['git','branch','--show-current'],cwd=external,text=True).strip(),files=external_files)
result=dict(modules=files,notebooks=notebooks,external=external_state,hypar_tracked_files=subprocess.check_output(['git','ls-files','hypar'],cwd=ROOT,text=True).splitlines())
(OUT/'inventory.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(modules=len(files),notebooks=len(notebooks),external_files=len(external_files),external_head=external_state['head'])))
