using System.Drawing;
using System.Text.Json.Nodes;
using Grasshopper.Kernel;
using Rangekeeper.Serialization;
using Rangekeeper.Authoring;
using Rangekeeper.Records;
using ModelRecord=Rangekeeper.Records.Model;

namespace Rangekeeper.Components;

/// <summary>Typed wire authoring from explicit JSON, with stable component identity.</summary>
public abstract class RecordComponent<T> : GH_Component where T:WireRecord
{
    protected RecordComponent(string name,string nickname):base(name,nickname,"Create a canonical "+typeof(T).Name+" from schema JSON. Omitted IDs use this saved component identity.","Rangekeeper","Model") { }
    protected override Bitmap? Icon => null;
    protected override void RegisterInputParams(GH_InputParamManager p)
    {
        p.AddTextParameter("JSON","J","Fields from the canonical schema; no transport objects",GH_ParamAccess.item);
        p.AddTextParameter("Identity","ID","Explicit identity to reuse; omit to use this saved component instance",GH_ParamAccess.item,"");p[1].Optional=true;
    }
    protected override void RegisterOutputParams(GH_OutputParamManager p) => p.AddGenericParameter(typeof(T).Name,"R","Immutable canonical record",GH_ParamAccess.item);
    protected override void SolveInstance(IGH_DataAccess data)
    {
        string json="",identity="";
        if(!data.GetData(0,ref json)) return;
        data.GetData(1,ref identity);
        try
        {
            var node=JsonNode.Parse(json)!.AsObject();
            if(typeof(T).GetProperty("Id") is not null)
            {
                if(identity.Length!=0) node["id"]=Guid.Parse(identity).ToString();
                else if(!node.ContainsKey("id")) node["id"]=InstanceGuid.ToString();
            }
            data.SetData(0,new RecordGoo(Compose.Decode<T>(node.ToJsonString())));
        }
        catch(Exception error) { AddRuntimeMessage(GH_RuntimeMessageLevel.Error,error.Message); }
    }
}
public sealed class DefinitionsComponent : RecordComponent<Definitions> { public DefinitionsComponent():base("RK Definitions","Defs"){} public override Guid ComponentGuid=>new("b2e45ba7-af08-4b49-9612-0d9308ced601"); }
public sealed class EntityComponent : RecordComponent<Entity> { public EntityComponent():base("RK Entity","Entity"){} public override Guid ComponentGuid=>new("b2e45ba7-af08-4b49-9612-0d9308ced602"); }
public sealed class ValueComponent : RecordComponent<Value> { public ValueComponent():base("RK Value","Value"){} public override Guid ComponentGuid=>new("b2e45ba7-af08-4b49-9612-0d9308ced603"); }
public sealed class RelationshipComponent : RecordComponent<Relationship> { public RelationshipComponent():base("RK Relationship","Relation"){} public override Guid ComponentGuid=>new("b2e45ba7-af08-4b49-9612-0d9308ced604"); }
public sealed class AssemblyComponent : RecordComponent<Rangekeeper.Records.Assembly> { public AssemblyComponent():base("RK Assembly","Assembly"){} public override Guid ComponentGuid=>new("b2e45ba7-af08-4b49-9612-0d9308ced605"); }

public sealed class ModelComponent : GH_Component
{
    private Guid revisionId=Guid.NewGuid();
    private Guid? previousRevision;
    private string contentFingerprint="";
    public override bool Write(GH_IO.Serialization.GH_IWriter writer)
    { writer.SetGuid("RKRevision",revisionId);writer.SetString("RKContent",contentFingerprint);if(previousRevision is Guid previous)writer.SetGuid("RKPrevious",previous);return base.Write(writer); }
    public override bool Read(GH_IO.Serialization.GH_IReader reader)
    { if(reader.ItemExists("RKRevision")) revisionId=reader.GetGuid("RKRevision");if(reader.ItemExists("RKContent"))contentFingerprint=reader.GetString("RKContent");if(reader.ItemExists("RKPrevious"))previousRevision=reader.GetGuid("RKPrevious");return base.Read(reader); }

    public ModelComponent():base("RK Model","Model","Compose and validate canonical collections. No solve, file write or publication.","Rangekeeper","Model") { }
    public override Guid ComponentGuid=>new("b2e45ba7-af08-4b49-9612-0d9308ced606");
    protected override Bitmap? Icon=>null;
    protected override void RegisterInputParams(GH_InputParamManager p)
    {
        p.AddGenericParameter("Definitions","D","Canonical definitions",GH_ParamAccess.item);
        p.AddGenericParameter("Entities","E","Canonical Entities",GH_ParamAccess.list);p[1].Optional=true;
        p.AddGenericParameter("Assemblies","A","Canonical Assemblies, separate from Entities",GH_ParamAccess.list);p[2].Optional=true;
        p.AddGenericParameter("Relationships","R","Explicit domain relationships",GH_ParamAccess.list);p[3].Optional=true;
        p.AddTextParameter("Revision","ID","New revision UUID for changed content; omit for saved component identity",GH_ParamAccess.item,"");p[4].Optional=true;
        p.AddGenericParameter("Provenance","P","Optional sources, Claims and Facts",GH_ParamAccess.item);p[5].Optional=true;
    }
    protected override void RegisterOutputParams(GH_OutputParamManager p)=>p.AddGenericParameter("Model","M","Validated canonical Model",GH_ParamAccess.item);
    protected override void SolveInstance(IGH_DataAccess data)
    {
        RecordGoo definitions=null!;var entities=new List<RecordGoo>();var assemblies=new List<RecordGoo>();var relationships=new List<RecordGoo>();string revision="";RecordGoo provenance=null!;
        if(!data.GetData(0,ref definitions)) return;
        data.GetDataList(1,entities);data.GetDataList(2,assemblies);data.GetDataList(3,relationships);data.GetData(4,ref revision);data.GetData(5,ref provenance);
        try
        {
            var result=Compose.Model(revision.Length==0?revisionId:Guid.Parse(revision),(Definitions)definitions.Value,entities.Select(e=>(Entity)e.Value),assemblies.Select(a=>(Rangekeeper.Records.Assembly)a.Value),relationships.Select(r=>(Relationship)r.Value),provenance?.Value as Provenance);
            if(revision.Length==0)
            {
                var content=result.ToData();content.Remove("metadata");
                var fingerprint=Convert.ToHexString(global::System.Security.Cryptography.SHA256.HashData(global::System.Text.Encoding.UTF8.GetBytes(content.ToJsonString())));
                if(contentFingerprint.Length!=0 && fingerprint!=contentFingerprint)
                {
                    previousRevision=revisionId;revisionId=Guid.NewGuid();
                }
                // Retain lineage on every recomputation, including after reopening.
                // The content fingerprint excludes revision metadata by design.
                var updated=result.ToData();updated["metadata"]!["id"]=revisionId.ToString();
                if(previousRevision is Guid previous)updated["metadata"]!["previous"]=previous.ToString();
                result=new ModelRecord(updated);
                contentFingerprint=fingerprint;
            }
            data.SetData(0,new RecordGoo(result));
        }
        catch(Exception error){AddRuntimeMessage(GH_RuntimeMessageLevel.Error,error.Message);}
    }
}

public sealed class ExportComponent : GH_Component
{
    public ExportComponent():base("RK Canonical Export","Export","Validate and return Model JSON plus a connector-neutral envelope. No file write or publication.","Rangekeeper","Model") { }
    public override Guid ComponentGuid=>new("b2e45ba7-af08-4b49-9612-0d9308ced607");
    protected override Bitmap? Icon=>null;
    protected override void RegisterInputParams(GH_InputParamManager p)
    {
        p.AddGenericParameter("Model","M","Canonical Model",GH_ParamAccess.item);
        p.AddTextParameter("Geometry associations","G","JSON array linking this revision/domain IDs to Rhino and transport IDs",GH_ParamAccess.item,"[]");p[1].Optional=true;
    }
    protected override void RegisterOutputParams(GH_OutputParamManager p)
    { p.AddTextParameter("Model JSON","J","Canonical JSON",GH_ParamAccess.item);p.AddTextParameter("Envelope","E","Versioned transport envelope",GH_ParamAccess.item); }
    protected override void SolveInstance(IGH_DataAccess data)
    {
        RecordGoo input=null!;string associations="[]";
        if(!data.GetData(0,ref input))return;data.GetData(1,ref associations);
        try { var model=(ModelRecord)input.Value;Validation.Validate.Require(model);data.SetData(0,Codec.Encode(model));data.SetData(1,Codec.Envelope(model,JsonNode.Parse(associations)!.AsArray()).ToJsonString()); }
        catch(Exception error){AddRuntimeMessage(GH_RuntimeMessageLevel.Error,error.Message);}
    }
}

public sealed class ValidateComponent : GH_Component
{
    public ValidateComponent():base("RK Validate Model","Validate","Return authoring diagnostics. Python remains the full semantic acceptance boundary.","Rangekeeper","Model") { }
    public override Guid ComponentGuid=>new("b2e45ba7-af08-4b49-9612-0d9308ced608");
    protected override Bitmap? Icon=>null;
    protected override void RegisterInputParams(GH_InputParamManager p)=>p.AddGenericParameter("Model","M","Canonical Model",GH_ParamAccess.item);
    protected override void RegisterOutputParams(GH_OutputParamManager p){p.AddBooleanParameter("Valid","V","Passes local authoring checks",GH_ParamAccess.item);p.AddTextParameter("Diagnostics","D","Source paths and reasons",GH_ParamAccess.list);}
    protected override void SolveInstance(IGH_DataAccess data)
    {
        RecordGoo input=null!;if(!data.GetData(0,ref input))return;
        try { var errors=Validation.Validate.Model((ModelRecord)input.Value);data.SetData(0,errors.Count==0);data.SetDataList(1,errors.Select(e=>e.Path+": "+e.Message)); }
        catch(Exception error){AddRuntimeMessage(GH_RuntimeMessageLevel.Error,error.Message);}
    }
}

/// <summary>Compose owner-local Values without mutable attributes or class patching.</summary>
public sealed class WithValuesComponent : GH_Component
{
    public WithValuesComponent():base("RK With Values","Values","Attach explicit Values to one Entity or Assembly; duplicate keys fail.","Rangekeeper","Model"){}
    public override Guid ComponentGuid=>new("b2e45ba7-af08-4b49-9612-0d9308ced609");
    protected override Bitmap? Icon=>null;
    protected override void RegisterInputParams(GH_InputParamManager p){p.AddGenericParameter("Owner","O","Entity or Assembly",GH_ParamAccess.item);p.AddGenericParameter("Values","V","Owner-local Values",GH_ParamAccess.list);}
    protected override void RegisterOutputParams(GH_OutputParamManager p)=>p.AddGenericParameter("Owner","O","New detached record with the same domain identity",GH_ParamAccess.item);
    protected override void SolveInstance(IGH_DataAccess data)
    {
        RecordGoo owner=null!;var values=new List<RecordGoo>();if(!data.GetData(0,ref owner)||!data.GetDataList(1,values))return;
        try
        {
            if(owner.Value is not Entity && owner.Value is not Rangekeeper.Records.Assembly)throw new ArgumentException("Owner must be Entity or Assembly");
            var node=owner.Value.ToData();var all=(node["characteristics"]?["values"]?.AsArray() ?? new JsonArray()).Select(v=>v!.DeepClone()).ToList();
            all.AddRange(values.Select(v=>((Value)v.Value).ToData()));
            if(all.Select(v=>v["key"]!.GetValue<string>()).Distinct().Count()!=all.Count)throw new ArgumentException("Duplicate Value key");
            node["characteristics"]??=new JsonObject();node["characteristics"]!["values"]=new JsonArray(all.ToArray());
            data.SetData(0,new RecordGoo(owner.Value is Entity?new Entity(node):new Rangekeeper.Records.Assembly(node)));
        }
        catch(Exception error){AddRuntimeMessage(GH_RuntimeMessageLevel.Error,error.Message);}
    }
}

public sealed class ProvenanceComponent : RecordComponent<Provenance> { public ProvenanceComponent():base("RK Provenance","Evidence"){} public override Guid ComponentGuid=>new("b2e45ba7-af08-4b49-9612-0d9308ced610"); }
