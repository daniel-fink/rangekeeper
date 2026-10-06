using System.Text.Json;
using System.Text.Json.Nodes;

namespace Rangekeeper.Serialization;

/// <summary>Deterministic JSON object ordering; array order and presence are preserved.</summary>
public static class Codec
{
    internal static readonly JsonSerializerOptions Options = CreateOptions();
    private static JsonSerializerOptions CreateOptions()
    {
        var result = new JsonSerializerOptions();
        result.Converters.Add(new RecordConverterFactory());
        result.Converters.Add(new IntegerConverter());
        return result;
    }
    /// <summary>Decode detached fields. Duplicate object keys fail before interpretation.</summary>
    public static T Decode<T>(string json) where T : WireRecord
    {
        using var document = JsonDocument.Parse(json);
        void Check(JsonElement item)
        {
            if (item.ValueKind == JsonValueKind.Object)
            {
                var keys = new HashSet<string>(StringComparer.Ordinal);
                foreach (var property in item.EnumerateObject())
                {
                    if (!keys.Add(property.Name)) throw new JsonException("Duplicate JSON key: " + property.Name);
                    Check(property.Value);
                }
            }
            else if (item.ValueKind == JsonValueKind.Array)
                foreach (var child in item.EnumerateArray()) Check(child);
        }
        Check(document.RootElement);
        return JsonSerializer.Deserialize<T>(json, Options) ?? throw new JsonException("Expected a record");
    }
    public static string Encode(WireRecord record) => Sort(record.ToData())!.ToJsonString(Options);
    private static JsonNode? Sort(JsonNode? node) => node switch
    {
        JsonObject obj => new JsonObject(obj.OrderBy(p => p.Key, StringComparer.Ordinal).Select(p => new KeyValuePair<string,JsonNode?>(p.Key, Sort(p.Value)))),
        JsonArray array => new JsonArray(array.Select(Sort).ToArray()),
        _ => node?.DeepClone()
    };
    /// <summary>Return a checked detached transport envelope. Does not publish or write.</summary>
    public static JsonObject Envelope(Records.Model model, JsonArray associations)
    {
        Validation.Validate.Require(model);
        var data = model.ToData();
        var revision = Guid.Parse(data["metadata"]!["id"]!.GetValue<string>());
        var identities = new HashSet<Guid>();
        foreach (var collection in new[] { "entities", "assemblies" })
            foreach (var owner in data["system"]?[collection]?.AsArray() ?? new JsonArray())
                identities.Add(Guid.Parse(owner!["id"]!.GetValue<string>()));
        foreach (var (raw, index) in associations.Select((raw, index) => (raw, index)))
        {
            var path = "/rk_associations/" + index;
            if (raw is not JsonObject association ||
                association.Any(p => !TransportContract.AssociationFields.Contains(p.Key)) ||
                TransportContract.RequiredAssociationFields.Any(key => !association.ContainsKey(key)))
                throw new ArgumentException(path + ": invalid association fields");
            if (Guid.Parse(association["model_revision"]!.GetValue<string>()) != revision)
                throw new ArgumentException(path + ": wrong Model revision");
            if (!identities.Contains(Guid.Parse(association["domain_id"]!.GetValue<string>())))
                throw new ArgumentException(path + ": unknown domain identity");
            if (association.ContainsKey("rhino_id")) Guid.Parse(association["rhino_id"]!.GetValue<string>());
            foreach (var key in new[] { "application_id", "content_id" })
                if (association.ContainsKey(key) && string.IsNullOrEmpty(association[key]!.GetValue<string>()))
                    throw new ArgumentException(path + ": empty " + key);
        }
        return new()
        {
            [TransportContract.FormatField] = TransportContract.Format,
            [TransportContract.ModelField] = Encode(model),
            [TransportContract.AssociationsField] = associations.DeepClone()
        };
    }
}
