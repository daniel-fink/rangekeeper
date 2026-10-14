"""Capture and run the existing, local-only baseline; does not alter test expectations."""
from pathlib import Path
import argparse, hashlib, importlib.metadata, json, os, platform, subprocess, sys, time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
PY = ROOT / 'src/.venv/bin/python'
SCHEMA_PY = Path('/private/tmp/rk-probe-audit-venv/bin/python')

def run(name, args, cwd, timeout=600):
    base = name
    attempt = 1
    while (OUT / (name + '.log')).exists():
        attempt += 1
        name = base + '-attempt' + str(attempt)
    start = time.monotonic()
    env = dict(os.environ, MPLBACKEND='Agg', PYTHONDONTWRITEBYTECODE='1',
               PYSTOW_HOME='/private/tmp/rk-domain-migration-pystow')
    with (OUT / (name + '.log')).open('w') as log:
        try:
            result = subprocess.run([str(a) for a in args], cwd=cwd, env=env,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 'timeout'
    item = dict(name=name, argv=[str(a) for a in args], cwd=str(cwd),
                environment_overrides={k:env[k] for k in ('MPLBACKEND','PYTHONDONTWRITEBYTECODE','PYSTOW_HOME')},
                timeout_seconds=timeout, elapsed_seconds=round(time.monotonic()-start, 3),
                exit_code=code, log=name+'.log')
    with (OUT/'commands.jsonl').open('a') as stream:
        stream.write(json.dumps(item)+'\n')
    print(json.dumps(item), flush=True)
    return code

def capture():
    paths = subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    fingerprints = {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
                    for p in paths if p and (ROOT/p).is_file()}
    state = dict(captured_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                 root=str(ROOT), platform=platform.platform(),
                 branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
                 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                 status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),
                 tracked_sha256=fingerprints)
    (OUT/'initial-state.json').write_text(json.dumps(state,indent=2)+'\n')
    probe = "import sys,json,importlib.metadata as m; print(json.dumps({'python':sys.version,'executable':sys.executable,'packages':sorted([(d.metadata['Name'],d.version) for d in m.distributions()])},indent=2)); "
    run('runtime-environment',[PY,'-c',probe+"import rangekeeper;print('rangekeeper:',rangekeeper.__file__)"],ROOT/'src')
    run('schema-environment',[SCHEMA_PY,'-c',probe],ROOT)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=['capture','schema','tests'])
    parser.add_argument('--runtime-python',type=Path,default=PY)
    parser.add_argument('--schema-python',type=Path,default=SCHEMA_PY)
    parser.add_argument('--output-dir',type=Path,default=OUT)
    args=parser.parse_args()
    PY,SCHEMA_PY,OUT=args.runtime_python,args.schema_python,args.output_dir.resolve()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.phase=='capture': capture()
    elif args.phase=='schema':
        for name in ['validate','native_roundtrip','expressions','formulations','models','specifications','runs']:
            run('schema-'+name,[SCHEMA_PY,ROOT/'schema/checks'/f'{name}.py'],ROOT)
    else:
        opts=['--ignore=tests/test_api.py','-o', 'cache_dir=/private/tmp/rk-domain-migration-pytest-cache']
        run('pytest-collection',[PY,'-m','pytest','tests','--collect-only','-q',*opts],ROOT/'src')
        run('pytest-local',[PY,'-m','pytest','tests','-q','--tb=short',*opts,'--junitxml='+str(OUT/'pytest-local.xml')],ROOT/'src',timeout=900)
