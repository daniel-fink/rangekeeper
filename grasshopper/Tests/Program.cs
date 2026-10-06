using System.Text.Json.Nodes;
using Rangekeeper.Records;
using Rangekeeper.Serialization;
using Rangekeeper.Authoring;
using Rangekeeper.Validation;

static void Require(bool predicate,string reason) { if (!predicate) throw new Exception(reason); }
var model=Codec.Decode<Model>(File.ReadAllText(args[0]));
Validator.Require(model);
var before=Codec.Encode(model);
var movementId=Guid.NewGuid();
var movement=new Movement {Id=movementId,Date=new DateOnly(2026,1,1),Magnitude=0};
Require(!movement.Key.IsPresent,"omitted matching key was invented");
Require(Codec.Decode<Movement>(Codec.Encode(movement)).Id==movementId,"Movement UUID changed");
var reference=new Reference {Target=movementId};
Require(Codec.Decode<Reference>(Codec.Encode(reference)).Target==movementId,"Reference UUID changed");
Require(Validator.Check(new Movement(new JsonObject { ["date"]="2026-01-01" })).Count>0,"missing Movement UUID accepted");
var wrongReference=model.ToData();
wrongReference["system"]!["formulations"]!.AsArray().Add(new JsonObject {
    ["id"]=Guid.NewGuid().ToString(), ["expressions"]=new JsonArray(new JsonObject {
        ["id"]=Guid.NewGuid().ToString(), ["kind"]="reference",
        ["target"]=new JsonObject { ["target"]=model.System.Value.Entities.Value[0].Id.ToString() }
    })
});
Require(Validator.Check(new Model(wrongReference)).Any(x=>x.Message.Contains("expected Value/Movement")),"wrong Reference kind accepted");
var raw=model.ToData();raw["metadata"]!["name"]="detached";
Require(Codec.Encode(model)==before,"export mutated Model");
var value=new Value { Id=Guid.NewGuid(),Key="zero",Kind="measurement",Quantity=new Quantity {Magnitude=0,Units="dimensionless"} };
Require(!value.Measure.IsPresent,"omission lost");
var nullable=new Value {Id=value.Id,Key="null",Kind="measurement",Quantity=Optional<Quantity>.Null};
Require(nullable.Quantity.IsPresent && nullable.Quantity.IsNull,"null lost");
Require(Codec.Decode<Value>(Codec.Encode(value)).Quantity.Value.Magnitude==0,"zero lost");
Require(Compose.Clone(value,true).Id==value.Id,"reuse identity changed");
Require(Compose.Clone(value,false).Id!=value.Id,"new identity reused");
var nested=model.System.Value.ToData();nested["entities"]!.AsArray().Clear();
Require(Codec.Encode(model)==before,"nested export mutated Model");
var broken=model.ToData();var entities=broken["system"]!["entities"]!.AsArray();entities.Add(entities[0]!.DeepClone());
Require(Validator.Check(new Model(broken)).Any(x=>x.Message.Contains("Duplicate identity")),"duplicate identity accepted");
try { Codec.Decode<Value>("{\"key\":\"a\",\"key\":\"b\"}");throw new Exception("Duplicate key accepted"); }
catch(global::System.Text.Json.JsonException) { }
var envelope=Codec.Envelope(model,new JsonArray());
Require(envelope[TransportContract.ModelField]!.GetValue<string>()==before,"envelope changed content");
try { Codec.Envelope(model,new JsonArray(new JsonObject { ["model_revision"]=Guid.NewGuid().ToString(),["domain_id"]=Guid.NewGuid().ToString() }));throw new Exception("Wrong revision accepted"); }
catch(ArgumentException) { }
File.WriteAllText(args[1],Codec.Encode(model));
Console.WriteLine("C# presence, identity, nested detachment, duplicate checks and round trip passed");
