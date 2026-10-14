"""Execute one notebook in a fresh, explicitly selected interpreter/kernel."""
from pathlib import Path
import argparse, json, os, sys
import nbformat
from nbclient import NotebookClient
from nbconvert import HTMLExporter
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager

parser=argparse.ArgumentParser()
parser.add_argument('source',type=Path)
parser.add_argument('output',type=Path)
parser.add_argument('--cwd',type=Path,required=True)
args=parser.parse_args()
root=Path('/private/tmp/rk-full-jupyter/kernels/rk-full')
root.mkdir(parents=True,exist_ok=True)
(root/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],
                                          'display_name':'RK migration verification','language':'python'}))
manager=KernelManager(kernel_name='rk-full',kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(root.parent)]))
notebook=nbformat.read(args.source,as_version=4)
NotebookClient(notebook,km=manager,timeout=120,resources={'metadata':{'path':str(args.cwd)}}).execute()
nbformat.validate(notebook)
args.output.parent.mkdir(parents=True,exist_ok=True)
nbformat.write(notebook,args.output)
html,_=HTMLExporter().from_notebook_node(notebook)
args.output.with_suffix('.html').write_text(html)
print(json.dumps({'source':str(args.source),'output':str(args.output),'python':sys.executable,
                  'cells':len(notebook.cells),'executed':sum(c.cell_type=='code' for c in notebook.cells)}))
