"""Isolated runtime: existing RK packages plus already installed workflow extras."""
from pathlib import Path
import shutil, subprocess
ROOT=Path(__file__).resolve().parents[4]
DEST=Path('/private/tmp/rk-domain-runtime')
subprocess.run([str(ROOT/'src/.venv/bin/python'),'-m','venv','--without-pip',str(DEST)],check=True)
site=DEST/'lib/python3.10/site-packages'
base=ROOT/'src/.venv/lib/python3.10/site-packages'
(site/'rangekeeper-baseline.pth').write_text(str(base)+'\n')
source=Path('/private/tmp/rk-probe-audit-venv/lib/python3.10/site-packages')
for pattern in ['yaml','pyyaml-*.dist-info','openpyxl','openpyxl-*.dist-info','et_xmlfile','et_xmlfile-*.dist-info']:
    paths=list(source.glob(pattern));assert paths,pattern
    for p in paths: shutil.copytree(p,site/p.name,dirs_exist_ok=True)
print(DEST/'bin/python')
print('Runtime packages inherited from',base)
print('Copied PyYAML 6.0.3, openpyxl 3.1.5 and et_xmlfile from',source)
