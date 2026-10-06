"""Generate .NET wire fields from the same resolved LinkML slots as Python.

Run Python generation first. This generator adds no fields or domain rules.
Union and opaque slots retain JsonNode data; all other fields expose typed access.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'src/rangekeeper/_schema'
DEST=ROOT/'grasshopper/Model/Generated'


def name(value):
    return ''.join(part[:1].upper()+part[1:] for part in value.split('_'))


def generate():
    slots=json.loads((SOURCE/'slots.json').read_text())
    lines=['// Generated from resolved LinkML. Do not edit.','using System.Text.Json.Nodes;','using Rangekeeper.Serialization;','namespace Rangekeeper.Records;','']
    for kind,fields in slots.items():
        lines += [f'/// <summary>Schema-derived {kind} wire record. Exports and nested reads are detached.</summary>',f'public sealed class {kind} : WireRecord','{',f'    public {kind}() {{ }}',f'    public {kind}(JsonObject data) : base(data) {{ }}','']
        for field,slot in fields.items():
            options=slot['options'];t='JsonNode'
            if len(options)==1:
                option=options[0];category=option['category'];k=option['kind']
                if category=='record':t=k
                elif category=='uuid':t='Guid'
                elif category=='enum':t='string'  # Allowed values remain in the shared JSON Schema.
                elif category=='primitive':t={'Code':'string','string':'string','boolean':'bool','integer':'global::System.Numerics.BigInteger','date':'DateOnly','datetime':'DateTimeOffset','double':'double','decimal':'decimal'}[k]
            if slot['mapping']:t='JsonObject'
            elif slot['many']:t=f'IReadOnlyList<{t}>'
            optional=not slot['required'] or slot['nullable']
            publictype=f'Optional<{t}>' if optional else t
            read='ReadOptional' if optional else 'Read'
            write='WriteOptional' if optional else 'Write'
            prop=name(field)
            # C# does not permit a property with the containing type's name.
            if prop==kind:prop+='Value'
            lines += [f'    /// <summary>Wire field {field}; missing and null remain distinct.</summary>',f'    public {publictype} {prop}', '    {',f'        get => {read}<{t}>("{field}");',f'        init => {write}("{field}", value);','    }']
        lines += ['}','']
    contract=json.loads((ROOT/'src/rangekeeper/adapters/speckle/contract.json').read_text())
    constants=['// Generated from the shared Speckle envelope contract.','namespace Rangekeeper.Serialization;','public static class TransportContract','{',f'    public const string Format = {json.dumps(contract["format"])};']
    for key,value in contract['fields'].items():constants.append(f'    public const string {name(key)}Field = {json.dumps(value)};')
    for key in ('association_fields', 'required_association_fields'):
        values=', '.join(json.dumps(value) for value in contract[key])
        constants.append(f'    public static readonly string[] {name(key)} = new[] {{ {values} }};')
    constants += ['}']
    result={'Records.cs':'\n'.join(lines),'TransportContract.cs':'\n'.join(constants)+'\n','schema.json':(SOURCE/'schema.json').read_text(),'slots.json':(SOURCE/'slots.json').read_text()}
    inputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SOURCE/'slots.json',SOURCE/'schema.json',Path(__file__),ROOT/'src/rangekeeper/adapters/speckle/contract.json']}
    result['manifest.json']=json.dumps({'inputs':inputs,'outputs':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in result.items()}},indent=2,sort_keys=True)+'\n'
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    stale=[]
    for filename,text in generate().items():
        path=DEST/filename
        if args.check:
            if not path.exists() or path.read_text()!=text:stale.append(filename)
        else:path.write_text(text)
    if stale:raise SystemExit('Stale C# artifacts: '+', '.join(stale))
    print('C# artifacts are current' if args.check else 'Generated C# records, shared schemas and transport constants')
