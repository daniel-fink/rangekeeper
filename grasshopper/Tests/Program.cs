using System.Text.Json.Nodes;
using Rangekeeper.Records;
using Rangekeeper.Serialization;
using Rangekeeper.Authoring;
using Rangekeeper.Validation;

static void Require(bool predicate,string reason) { if (!predicate) throw new Exception(reason); }
var model=Codec.Decode<Model>(File.ReadAllText(args[0]));
Validate.Require(model);
var before=Codec.Encode(model);
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
Require(Validate.Model(new Model(broken)).Any(x=>x.Message.Contains("Duplicate identity")),"duplicate identity accepted");
try { Codec.Decode<Value>("{\"key\":\"a\",\"key\":\"b\"}");throw new Exception("Duplicate key accepted"); }
catch(global::System.Text.Json.JsonException) { }
var envelope=Codec.Envelope(model,new JsonArray());
Require(envelope[TransportContract.ModelField]!.GetValue<string>()==before,"envelope changed content");
try { Codec.Envelope(model,new JsonArray(new JsonObject { ["model_revision"]=Guid.NewGuid().ToString(),["domain_id"]=Guid.NewGuid().ToString() }));throw new Exception("Wrong revision accepted"); }
catch(ArgumentException) { }
File.WriteAllText(args[1],Codec.Encode(model));
Console.WriteLine("C# presence, identity, nested detachment, duplicate checks and round trip passed");
