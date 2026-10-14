using Grasshopper.Kernel.Types;
using GH_IO.Serialization;
using Rangekeeper.Serialization;

namespace Rangekeeper.Components;

/// <summary>Connector-independent Grasshopper wrapper; canonical exports are detached.</summary>
public sealed class RecordGoo : GH_Goo<WireRecord>
{
    public RecordGoo() { }
    public RecordGoo(WireRecord value) { Value=value; }
    public override bool IsValid => Value is not null;
    public override string TypeName => Value?.GetType().Name ?? "RK record";
    public override string TypeDescription => "Canonical Rangekeeper schema record";
    public override IGH_Goo Duplicate() => new RecordGoo(Value); // Records expose only init setters and detached nested reads.
    public override string ToString() => Value is null ? "Empty RK record" : Codec.Encode(Value);
    public override bool Write(GH_IWriter writer)
    {
        if (Value is null) return false;
        writer.SetString("Kind",Value.GetType().Name);writer.SetString("JSON",Codec.Encode(Value));return true;
    }
    public override bool Read(GH_IReader reader)
    {
        var kind=reader.GetString("Kind");
        // Only generated types in this assembly can be reconstructed. No arbitrary
        // assembly name, callback, or runtime import comes from the saved document.
        var type=typeof(Rangekeeper.Records.Model).Assembly.GetType("Rangekeeper.Records."+kind);
        if(type is null || !typeof(WireRecord).IsAssignableFrom(type)) return false;
        Value=(WireRecord)Activator.CreateInstance(type,System.Text.Json.Nodes.JsonNode.Parse(reader.GetString("JSON"))!.AsObject())!;
        return true;
    }
}
