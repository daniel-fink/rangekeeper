using System.Text.Json.Nodes;
using Rangekeeper.Serialization;
using Rangekeeper.Records;
using ModelRecord=Rangekeeper.Records.Model;
using SystemRecord=Rangekeeper.Records.System;

namespace Rangekeeper.Authoring;

/// <summary>Explicit composition. No constructor authenticates, saves, publishes or solves.</summary>
public static class Compose
{
    public static ModelRecord Model(Guid revision, Definitions definitions, IEnumerable<Entity> entities,
        IEnumerable<Assembly> assemblies, IEnumerable<Relationship> relationships, Provenance? provenance=null)
    {
        var result=new ModelRecord {
            Metadata=new Metadata { Id=revision, SchemaVersion="0.7.0" },
            Definitions=definitions,
            System=new SystemRecord { Entities=entities.ToArray(), Assemblies=assemblies.ToArray(), Relationships=relationships.ToArray() }
        };
        if(provenance is not null) { var data=result.ToData();data["provenance"]=provenance.ToData();result=new ModelRecord(data); }
        Validation.Validator.Require(result);
        return result;
    }
    public static T Clone<T>(T source, bool reuseIdentity) where T:WireRecord
    {
        var data=source.ToData();
        if (!reuseIdentity)
        {
            if (data["id"] is null) throw new ArgumentException("Clone requires an identified record");
            // Only this object's identity changes. References remain explicit;
            // composition validates them, rather than silently cloning a graph.
            data["id"]=Guid.NewGuid().ToString();
        }
        return Codec.Decode<T>(data.ToJsonString());
    }
    public static T Decode<T>(string json) where T:WireRecord
    {
        var value=Codec.Decode<T>(json);
        var errors=Validation.Validator.Check(value);
        if(errors.Count!=0) throw new ArgumentException(string.Join("; ",errors.Select(e=>e.Message)));
        return value;
    }
}
