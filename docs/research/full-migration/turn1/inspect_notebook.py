"""Check executed outputs and export readable HTML without relying on stored images."""
from pathlib import Path
import json
import nbformat
from nbconvert import HTMLExporter
from bs4 import BeautifulSoup
p=Path(__file__).resolve().parent/'verification/basic_dcf_final.ipynb'
n=nbformat.read(p,as_version=4)
nbformat.validate(n)
html,_=HTMLExporter().from_notebook_node(n)
p.with_suffix('.html').write_text(html)
soup=BeautifulSoup(html,'html.parser')
assert 'Property PV: $1,000' in soup.get_text()
installed='/private/tmp/rk-foundations-release-check/site/rangekeeper/__init__.py'
assert installed in soup.get_text()
assert not any(o.get('output_type')=='error' for c in n.cells for o in c.get('outputs',[]))
counts=[c.execution_count for c in n.cells if c.cell_type=='code']
assert counts==list(range(1,len(counts)+1))
report=dict(code_cells=len(counts),execution_counts=counts,html_tables=len(soup.find_all('table')),
            pv='1000',installed_import=installed,
            visual_review='unverified: browser URL policy blocks file URLs; no bypass attempted',
            documentation_build='MyST directives/citations retained; full walkthrough rebuild remains Turn 4')
(p.parent/'notebook-inspection.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
