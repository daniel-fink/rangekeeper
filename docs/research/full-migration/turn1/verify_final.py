"""Run final bounded acceptance with command metadata and independent output paths."""
from pathlib import Path
import importlib.util, os, sys
ROOT=Path(__file__).resolve().parents[4]
helper=ROOT/'docs/research/domain-migration/evidence/run_baseline.py'
spec=importlib.util.spec_from_file_location('baseline',helper)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.OUT=Path(__file__).resolve().parent/'verification'
schema=Path('/private/tmp/rk-probe-audit-venv/bin/python')
os.environ['MPLCONFIGDIR']='/private/tmp/rk-mpl-cache'
failed=[]
for name in ['validate','native_roundtrip','expressions','formulations','models','specifications','runs']:
    if m.run('final-schema-'+name,[schema,ROOT/'schema/checks'/f'{name}.py'],ROOT): failed.append(name)
if m.run('final-content',[sys.executable,'-m','pytest','tests/test_calculations.py','tests/test_migration_foundations.py','tests/test_calculation_equivalence.py','-q'], ROOT/'src'): failed.append('content')
if m.run('generation-check',[schema,ROOT/'tools/schema/generate.py','--check'],ROOT): failed.append('generation')
raise SystemExit(bool(failed))
