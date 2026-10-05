"""Attach each inventoried legacy symbol/consumer to an explicit migration responsibility.

This is a coverage ledger, not a claim that AST discovery proves runtime equivalence.
The source inventory is frozen; subsequent ports must add evidence to the named row.
"""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
source=json.loads((OUT.parent/'inventory.json').read_text())

def responsibility(path, symbol):
    p=path.removeprefix('src/rangekeeper/')
    if p in ('graph/characteristics.py',): return 'D02'
    if p in ('graph/classification.py','graph/taxonomy.py','graph/definitions.py'): return 'D03'
    if p=='graph/provenance.py': return 'D04'
    if p in ('graph/revision.py','graph/update.py'): return 'D05'
    if p.startswith('graph/adapter'): return 'D06'
    if p=='graph/table.py': return 'D09'
    if p=='graph/legacy/view.py': return 'D07'
    if p=='graph/legacy/reduction.py': return 'D08'
    if p.startswith('graph/'): return 'D01'
    if p=='measure.py': return 'C01'
    if p=='duration.py': return 'C02'
    if p=='flux.py':
        name=symbol.split('.')[-1]
        if name in ('plot','display','_repr_html_','__str__','_format_flows','_format_series','frame'): return 'F03'
        if name in ('pv','npv','irr'): return 'C07'
        if name=='from_projection': return 'C05'
        if name in ('from_DataFrame','from_dict','from_sequence','to_periods'): return 'D09'
        if name in ('Flow','Stream','name','movements','units','flows','frequency','start_date','end_date','__init__','duplicate','to_stream','extract','merge','__add__'): return 'C03'
        return 'C04'
    if p=='distribution.py': return 'C06'
    if p in ('projection.py','extrapolation.py'): return 'C05'
    if p.startswith('formula/'): return 'C07'
    if p=='dynamics/market.py' or p=='policy.py': return 'F01'
    if p.startswith('dynamics/'): return 'C08'
    if p=='segmentation.py': return 'C09'
    if p=='api.py': return 'F02'
    if p=='format.py': return 'F03'
    if p in ('space.py','__init__.py'): return 'F04'
    raise ValueError(p)

symbols=[]
modules=[]
for path, module in source['review_modules'].items():
    rows=[dict(path=path, symbol=s['name'], line=s['line'], kind=s['kind'], responsibility=responsibility(path,s['name'])) for s in module['symbols']]
    symbols.extend(rows)
    modules.append(dict(path=path, sha256=module['sha256'], responsibilities=sorted({r['responsibility'] for r in rows}) or [responsibility(path,'')], symbols=len(rows)))
consumers=[]
for scope,key in [('repository','local_consumer_candidates'),('external','external_consumer_candidates')]:
    for path,evidence in source[key].items():
        if path=='walkthrough/basic_dcf.ipynb' or path in ('src/tests/models/linear.py','src/tests/test_formulas.py') or path.startswith('src/examples/workflow/'):
            turn=1; status='migrated; see Turn 1 verification'
        elif path.startswith('walkthrough/') or '/models/' in path or any(s in path for s in ('dynamics','policy','distribution','extrapolation','flux','duration','formula')):
            turn=2; status='awaits remaining numerical/scenario consumer migration'
        elif path.startswith('tools/schema/'):
            turn=4; status='retain and extend canonical acceptance; final retirement scan'
        else:
            turn=3; status='consumer port or final audit required; old imports may remain'
        if scope=='external': turn=3; status='not executed in Turn 1; host/data acceptance required'
        consumers.append(dict(scope=scope,path=path,turn=turn,status=status,evidence=evidence))
result=dict(source='../inventory.json', limitation='All discovered symbols have a disposition. Pending rows are not runtime acceptance. No guarantee for undiscovered downstream code.',modules=modules,symbols=symbols,consumers=consumers,parallel_branch_features=source['parallel_branch_features'])
(OUT/'ledger.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'modules':len(modules),'symbols':len(symbols),'consumers':len(consumers),'parallel_files':len(source['parallel_branch_features'])}))
