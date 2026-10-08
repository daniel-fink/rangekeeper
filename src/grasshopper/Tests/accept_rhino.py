"""Run inside a fresh Rhino 8 process with RunPythonScript.

Build the local Components project first. This creates/replaces only the canonical
example GHX and temporary acceptance artifacts. It reads the original 3dm without
changing it. No old component library, EleFront, SDK or service is needed.
"""
import clr,System,Rhino,json,traceback,os
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
clr.AddReference('Grasshopper')
import Grasshopper
from System.Reflection import BindingFlags
from System.Drawing import PointF
from Grasshopper.Kernel import GH_Document,GH_DocumentIO,GH_RuntimeMessageLevel
from Grasshopper.Kernel.Special import GH_Panel
path=os.path.join(ROOT,'Components/bin/Debug/net8.0/Rangekeeper.Components.gha')
try:
    server=Grasshopper.Instances.ComponentServer
    if server.EmitObjectProxy(System.Guid('b2e45ba7-af08-4b49-9612-0d9308ced611')) is None:
        loaded=server.GetType().GetMethod('LoadGHA',BindingFlags.Instance|BindingFlags.NonPublic).Invoke(server,System.Array[System.Object]([Grasshopper.Kernel.GH_ExternalFile(path),False]))
    doc=GH_Document()
    output=os.path.abspath(os.path.join(ROOT,'../../examples/grasshopper/exampleDesignCanonical.ghx'))
    doc.FilePath=output
    def add(obj,x,y):
        obj.CreateAttributes();obj.Attributes.Pivot=PointF(x,y);doc.AddObject(obj,False);return obj
    source=add(GH_Panel(),50,70);source.UserText='exampleDesign.3dm'
    elevations=add(GH_Panel(),50,200);elevations.UserText='\n'.join(str(z) for z in [-5.9,-2.8,.3]+[5.3+3.1*i for i in range(20)])
    elevations.Properties.Multiline=False
    example=add(server.EmitObject(System.Guid('b2e45ba7-af08-4b49-9612-0d9308ced611')),340,100)
    export=add(server.EmitObject(System.Guid('b2e45ba7-af08-4b49-9612-0d9308ced607')),560,100)
    validate=add(server.EmitObject(System.Guid('b2e45ba7-af08-4b49-9612-0d9308ced608')),560,240)
    example.Params.Input[0].AddSource(source);example.Params.Input[1].AddSource(elevations)
    export.Params.Input[0].AddSource(example.Params.Output[0]);export.Params.Input[1].AddSource(example.Params.Output[1]);validate.Params.Input[0].AddSource(example.Params.Output[0])
    doc.Enabled=True
    GH_Document.EnableSolutions=True
    doc.NewSolution(True)
    System.IO.File.WriteAllText('/private/tmp/rk-ghx-state.json',json.dumps([{ 'name':obj.Name,'phase':str(obj.Phase),'inputs':[p.VolatileDataCount for p in obj.Params.Input],'outputs':[p.VolatileDataCount for p in obj.Params.Output],'warnings':[str(e) for e in obj.RuntimeMessages(GH_RuntimeMessageLevel.Warning)]} for obj in [example,export,validate]],indent=2))
    errors=[str(e) for obj in [example,export,validate] for e in obj.RuntimeMessages(GH_RuntimeMessageLevel.Error)]
    if errors:raise Exception(str(errors))
    first=str(export.Params.Output[0].VolatileData.AllData(True).GetEnumerator()) if False else [str(x) for x in export.Params.Output[0].VolatileData.AllData(True)][0]
    envelope=[str(x) for x in export.Params.Output[1].VolatileData.AllData(True)][0]
    io=GH_DocumentIO();io.Document=doc
    if not io.SaveQuiet(output):raise Exception('GHX save failed')
    reopened=GH_DocumentIO()
    if not reopened.Open(output):raise Exception('GHX reopen failed')
    reopened.Document.Enabled=True
    reopened.Document.NewSolution(True)
    secondExport=[x for x in reopened.Document.Objects if x.ComponentGuid==export.ComponentGuid][0]
    second=[str(x) for x in secondExport.Params.Output[0].VolatileData.AllData(True)][0]
    if first!=second:raise Exception('Reopen/recompute changed canonical content')
    System.IO.File.WriteAllText('/private/tmp/rk-rhino-model.json',first)
    System.IO.File.WriteAllText('/private/tmp/rk-rhino-envelope.json',envelope)
    # Exercise generic authoring revisions separately from the geometry example.
    generic=GH_Document();generic.Enabled=True
    def generic_add(obj,x,y):
        obj.CreateAttributes();obj.Attributes.Pivot=PointF(x,y);generic.AddObject(obj,False);return obj
    definitions_json=generic_add(GH_Panel(),10,10);definitions_json.UserText='{}'
    entity_json=generic_add(GH_Panel(),10,100);entity_json.UserText='{"name":"First"}'
    definitions=generic_add(server.EmitObject(System.Guid('b2e45ba7-af08-4b49-9612-0d9308ced601')),250,10)
    entity=generic_add(server.EmitObject(System.Guid('b2e45ba7-af08-4b49-9612-0d9308ced602')),250,100)
    model=generic_add(server.EmitObject(System.Guid('b2e45ba7-af08-4b49-9612-0d9308ced606')),450,10)
    encoded=generic_add(server.EmitObject(System.Guid('b2e45ba7-af08-4b49-9612-0d9308ced607')),650,10)
    definitions.Params.Input[0].AddSource(definitions_json);entity.Params.Input[0].AddSource(entity_json)
    model.Params.Input[0].AddSource(definitions.Params.Output[0]);model.Params.Input[1].AddSource(entity.Params.Output[0]);encoded.Params.Input[0].AddSource(model.Params.Output[0])
    generic.NewSolution(True)
    def output_model(component):return [str(x) for x in component.Params.Output[0].VolatileData.AllData(True)][0]
    before=output_model(encoded);generic.NewSolution(True)
    if before!=output_model(encoded):raise Exception('Unchanged recompute altered generic Model')
    entity_json.UserText='{"name":"Second"}';entity_json.ExpireSolution(False);generic.NewSolution(True)
    changed=output_model(encoded);a=json.loads(before);b=json.loads(changed)
    if a['system']['entities'][0]['id']!=b['system']['entities'][0]['id']:raise Exception('Editing name changed domain identity')
    if a['metadata']['id']==b['metadata']['id'] or b['metadata'].get('previous')!=a['metadata']['id']:raise Exception('Changed content did not advance revision')
    generic.NewSolution(True)
    if changed!=output_model(encoded):raise Exception('Unchanged recompute lost revision lineage')
    gio=GH_DocumentIO();gio.Document=generic;gio.SaveQuiet('/private/tmp/rk-generic-authoring.ghx')
    reopened_generic=GH_DocumentIO();reopened_generic.Open('/private/tmp/rk-generic-authoring.ghx');reopened_generic.Document.Enabled=True;reopened_generic.Document.NewSolution(True)
    reopened_export=[x for x in reopened_generic.Document.Objects if x.ComponentGuid==encoded.ComponentGuid][0]
    if changed!=output_model(reopened_export):raise Exception('Reopening lost generic revision lineage')
    report={'status':'passed','rhino':str(Rhino.RhinoApp.Version),'runtime':str(System.Environment.Version),'objects':len(list(doc.Objects)),'reopened_equal':first==second,'errors':errors,'generic_revisions':'stable identity; changed revision; retained previous after reopen'}
except Exception as error:report={'error':traceback.format_exc(),'dotnet':str(error.clsException.ToString()) if hasattr(error,'clsException') else repr(error)}
System.IO.File.WriteAllText('/private/tmp/rk-ghx-report.json',json.dumps(report,indent=2))
