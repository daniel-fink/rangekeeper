"""Isolated feasibility probe, not a production codec or validation implementation."""
from pathlib import Path
from tempfile import TemporaryDirectory
import copy, importlib.util, inspect, json, os, subprocess, sys, typing
import yaml
from linkml_runtime.utils.schemaview import SchemaView
from linkml_runtime.loaders import json_loader
from linkml_runtime.dumpers import json_dumper
from jsonschema import FormatChecker
from jsonschema.validators import validator_for

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(os.environ.get("RK_RECORD_PROBE_OUTPUT", Path(__file__).resolve().parent))
OUT.mkdir(parents=True, exist_ok=True)
BIN=Path(sys.executable).parent
checks={}
with TemporaryDirectory(prefix='rk-record-boundary-') as temp:
    temp=Path(temp)
    for p in (ROOT/'schema').glob('*.yaml'):
        (temp/p.name).write_bytes(p.read_bytes())
    bundle=temp/'bundle.yaml'
    bundle.write_text(yaml.safe_dump(dict(id='https://example.org/rk-probe', name='rk_probe', imports=['model','specification','run'],prefixes={'linkml':'https://w3id.org/linkml/'})))
    sv=SchemaView(str(bundle)); classes=sv.all_classes()
    native_source=subprocess.check_output([str(BIN/'gen-python'),str(bundle)],text=True)
    (temp/'native.py').write_text(native_source)
    spec=importlib.util.spec_from_file_location('native_probe',temp/'native.py')
    native=importlib.util.module_from_spec(spec);sys.modules[spec.name]=native;spec.loader.exec_module(native)
    fixture=yaml.safe_load((ROOT/'schema/examples/model.yaml').read_text())
    nr=json_loader.loads(json.dumps(fixture),target_class=native.Model)
    nr.metadata.name='mutation accepted'
    checks['native_record_is_mutable']=nr.metadata.name=='mutation accepted'
    validators={}
    for kind,file in [('Model','model'),('Specification','specification'),('Run','run')]:
        schema=json.loads(subprocess.check_output([str(BIN/'gen-json-schema'),'--closed','--top-class',kind,str(ROOT/f'schema/{file}.yaml')],text=True))
        validators[kind]=validator_for(schema)(schema,format_checker=FormatChecker())
    opaque_names={n for n,c in classes.items() if str(c.class_uri) in ('linkml:Any','https://w3id.org/linkml/Any')}
    source='''from __future__ import annotations
from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping
from uuid import UUID
from typing import Any

class Unset:
    __slots__ = ()
UNSET = Unset()
def freeze(value):
    if isinstance(value, Record): return value._data
    if isinstance(value, UUID): return str(value)
    if isinstance(value, Mapping): return MappingProxyType({k:freeze(v) for k,v in value.items()})
    if isinstance(value, (list,tuple)): return tuple(freeze(v) for v in value)
    return value

def thaw(value):
    if isinstance(value, Mapping): return {k:thaw(v) for k,v in value.items()}
    if isinstance(value, tuple): return [thaw(v) for v in value]
    return value

@dataclass(frozen=True, slots=True, init=False)
class Record:
    _data: Mapping[str, Any]
    @classmethod
    def from_data(cls, data):
        value = object.__new__(cls)
        object.__setattr__(value, '_data', freeze(data))
        return value
    def to_data(self): return thaw(self._data)
    def _get(self, key, kind, many, inline):
        value = self._data.get(key)
        if value is None: return () if many and key not in self._data else None
        def cast(item):
            if item is None: return None
            if kind in OPAQUE: return item
            if kind == 'UUID' or (kind in RECORDS and not inline): return UUID(item)
            if kind in RECORDS and isinstance(item, Mapping): return RECORDS[kind].from_data(item)
            return item
        return tuple(cast(i) for i in value) if many else cast(value)
'''
    source += '\nOPAQUE = ' + repr(opaque_names) + '\n'
    for name in sorted(classes):
        fields=[sv.induced_slot(n,name) for n in sv.class_slots(name)]
        source+=f'\nclass {name}(Record):\n    __slots__ = ()\n'
        args=[]
        for s in fields:
            kind=s.range or 'string'
            ref=kind=='UUID' or kind in classes and not (s.inlined or s.inlined_as_list)
            typ='UUID' if ref else (kind if kind in classes else {'integer':'int','decimal':'float','double':'float','float':'float','boolean':'bool','string':'str','Code':'str','URI':'str'}.get(kind,'Any'))
            if s.multivalued:typ=f'tuple[{typ}, ...]'
            args.append(f'{s.name}: {typ} | None | Unset = UNSET')
        if args:
            source+='    def __init__(self, *, '+', '.join(args)+'):\n'
            source+="        object.__setattr__(self, '_data', freeze({k:v for k,v in locals().items() if k != 'self' and v is not UNSET}))\n"
        for s in fields:
            typ=args[[f.name for f in fields].index(s.name)].split(': ',1)[1].split(' | Unset')[0]
            source+=f'    @property\n    def {s.name}(self) -> {typ}:\n        return self._get({s.name!r}, {s.range!r}, {bool(s.multivalued)!r}, {bool(s.inlined or s.inlined_as_list)!r})\n'
        if not fields:source+='    pass\n'
    source+='\nRECORDS = {'+', '.join(f'{n!r}: {n}' for n in sorted(classes))+'}\n'
    (temp/'readonly.py').write_text(source)
    spec=importlib.util.spec_from_file_location('readonly_probe',temp/'readonly.py')
    records=importlib.util.module_from_spec(spec);sys.modules[spec.name]=records;spec.loader.exec_module(records)
    r=records.Model.from_data(fixture)
    fixture['metadata']['name']='caller changed'
    checks['input_is_detached']=r.metadata.name!='caller changed'
    exported=r.to_data();exported['metadata']['name']='export changed'
    checks['export_is_detached']=r.metadata.name!='export changed'
    mutations=[lambda:setattr(r.metadata,'name','x'),lambda:r._data.__setitem__('system',{}),lambda:r.system.entities.append(None),lambda:r.system.entities[0]._data.__setitem__('code','x')]
    rejected=0
    for mutate in mutations:
        try:mutate()
        except (AttributeError,TypeError):rejected+=1
    checks['nested_mutations_rejected']=rejected==4
    checks['typed_reference']=isinstance(r.system.entities[0].classification,records.UUID)
    checks['no_dynamic_getattr']='__getattr__' not in source
    checks['explicit_constructor']='metadata' in inspect.signature(records.Model).parameters
    checks['type_hints_resolve']=typing.get_type_hints(records.Model.metadata.fget)['return'] is not None
    q=records.Quantity(magnitude=0,units='dimensionless')
    v=records.Value(id=records.UUID('11111111-1111-4111-8111-111111111111'), key='amount',kind='measurement',measure=records.UUID('22222222-2222-4222-8222-222222222222'),quantity=q)
    checks['nested_authoring']=v.quantity.magnitude==0 and v.to_data()['quantity']['magnitude']==0
    omission=records.Value.from_data({k:w for k,w in v.to_data().items() if k!='quantity'})
    null=records.Value.from_data(dict(omission.to_data(),quantity=None))
    checks['omission_null_zero_distinct']='quantity' not in omission.to_data() and null.to_data()['quantity'] is None and v.quantity.magnitude==0
    opaque=records.Claim.from_data({'content':{'zero':0,'false':False,'items':[{'x':1}]}})
    checks['opaque_values_preserved']=opaque.content['false'] is False and opaque.to_data()['content']['zero']==0
    try:opaque.content['items'][0]['x']=2
    except TypeError:checks['opaque_content_frozen']=True
    checked=[]
    for filename in ['model.yaml','model-forward-output.yaml','model-inverse-output.yaml','specification-common.yaml','specification-forward.yaml','specification-inverse.yaml','specification-composed-forward.yaml','specification-composed-inverse.yaml','specification-batch.yaml','run-forward.yaml','run-inverse.yaml','run-batch.yaml','run-failed.yaml','run-skipped.yaml']:
        data=yaml.safe_load((ROOT/'schema/examples'/filename).read_text())
        kind='Model' if filename.startswith('model') else ('Run' if filename.startswith('run') else 'Specification')
        validators[kind].validate(data)
        restored=getattr(records,kind).from_data(data).to_data()
        assert restored==data,filename
        validators[kind].validate(restored)
        checked.append(filename)
    checks['fixture_roundtrips']=len(checked)==14
    def visit(value):
        if isinstance(value, records.Record):
            for slot in sv.class_slots(type(value).__name__):
                visit(getattr(value,slot))
        elif isinstance(value,tuple):
            for item in value: visit(item)
    for filename in checked:
        kind='Model' if filename.startswith('model') else ('Run' if filename.startswith('run') else 'Specification')
        visit(getattr(records,kind).from_data(yaml.safe_load((ROOT/'schema/examples'/filename).read_text())))
    checks['all_fixture_properties_accessible']=True
    (OUT/'readonly-probe-generated.py').write_text(source)
    result=dict(checks=checks,generated_classes=len(classes),fixtures=checked,
        limitations=['Prototype validates document structure externally; does not implement semantic entrypoints, store, canonical indexing, or public behavior mixins.','Constructor annotations demonstrate explicit typing; static type checker not run.','Readonly projection generation is a required maintained generator, not stock LinkML gen-python output.','Required-field and union annotations need production generation rules; prototype constructors permit Unset for all fields.'])
    (OUT/'record-boundary-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    assert all(checks.values())
