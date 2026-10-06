using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using Json.Schema;
using Rangekeeper.Serialization;

namespace Rangekeeper.Validation;

public sealed record Diagnostic(string Path, string Message);

/// <summary>Shared structural schema plus local identity/reference authoring checks.</summary>
public static class Validator
{
    private static readonly JsonObject Slots = ReadResource("slots.json");
    private static readonly Dictionary<string, JsonSchema> Schemas = new();
    private static JsonObject ReadResource(string suffix)
    {
        var assembly = typeof(Validator).Assembly;
        using var stream = assembly.GetManifestResourceStream(assembly.GetManifestResourceNames().Single(n => n.EndsWith(suffix)))!;
        return JsonNode.Parse(stream)!.AsObject();
    }
    private static JsonSchema Schema(string kind)
    {
        lock (Schemas)
        {
            if (Schemas.TryGetValue(kind, out var existing)) return existing;
            var node = ReadResource("schema.json");
            node["$ref"] = "#/$defs/" + kind;
            // Each root has an isolated registry; validation never fetches schemas.
            var schema = JsonSchema.FromText(node.ToJsonString(), new BuildOptions { SchemaRegistry = new() });
            Schemas.Add(kind, schema);
            return schema;
        }
    }
    /// <summary>Check structure against the embedded schema without network resolution.</summary>
    public static IReadOnlyList<Diagnostic> Check(WireRecord record)
    {
        var data = record.ToData();
        using var document = JsonDocument.Parse(data.ToJsonString());
        var evaluated = Schema(record.GetType().Name).Evaluate(document.RootElement, new EvaluationOptions { OutputFormat = OutputFormat.List, RequireFormatValidation = true });
        if (evaluated.IsValid) return Array.Empty<Diagnostic>();
        return new[] { new Diagnostic("/", JsonSerializer.Serialize(evaluated)) };
    }
    /// <summary>Check structure and local ownership; Python validates units and mathematics.</summary>
    public static IReadOnlyList<Diagnostic> Check(Records.Model model)
    {
        var diagnostics = new List<Diagnostic>(Check((WireRecord)model));
        if (diagnostics.Count != 0) return diagnostics;
        var catalogue = new Dictionary<Guid, (string Kind, string Path)>();
        var references = new List<(Guid Id, string[] Kinds, string Path)>();
        void Visit(JsonObject data, string kind, string path)
        {
            if (data["id"] is JsonValue identity && kind != "Metadata")
            {
                var id = Guid.Parse(identity.GetValue<string>());
                if (!catalogue.TryAdd(id, (kind, path))) diagnostics.Add(new(path + "/id", $"Duplicate identity {id}; first at {catalogue[id].Path}"));
            }
            foreach (var field in Slots[kind]!.AsObject())
            {
                if (!data.TryGetPropertyValue(field.Key, out var raw) || raw is null) continue;
                var slot = field.Value!.AsObject();
                var options = slot["options"]!.AsArray();
                if (slot["mapping"]!.GetValue<bool>()) continue; // Opaque keyed content is schema-checked, not domain membership.
                var elements = slot["many"]!.GetValue<bool>() ? raw.AsArray().Select((v, i) => (Value: v, Path: path + "/" + field.Key + "/" + i)) : new[] { (Value: (JsonNode?)raw, Path: path + "/" + field.Key) };
                foreach (var element in elements)
                {
                    if (element.Value is JsonObject obj)
                    {
                        var child = options.FirstOrDefault(o => o!["category"]!.GetValue<string>() == "record");
                        if (child is not null) Visit(obj, child["kind"]!.GetValue<string>(), element.Path);
                    }
                    else if (element.Value is JsonValue scalar)
                    {
                        var reference = options.FirstOrDefault(o => o!["category"]!.GetValue<string>() == "uuid" && o["kind"]!.GetValue<string>() != "UUID");
                        if (reference is not null && !(kind == "Metadata" && field.Key == "previous")) references.Add((Guid.Parse(scalar.GetValue<string>()), options.Where(o => o!["category"]!.GetValue<string>() == "uuid").Select(o => o!["kind"]!.GetValue<string>()).ToArray(), element.Path));
                    }
                }
            }
            if (kind is "Characteristics" or "Formulation")
            {
                var keys = new HashSet<string>();
                foreach (var value in data["values"]?.AsArray() ?? new JsonArray())
                    if (!keys.Add(value!["key"]!.GetValue<string>())) diagnostics.Add(new(path + "/values", "Duplicate owner-local Value key"));
            }
        }
        Visit(model.ToData(), "Model", "");
        foreach (var reference in references)
        {
            if (!catalogue.TryGetValue(reference.Id, out var target)) diagnostics.Add(new(reference.Path, $"Missing {string.Join("/", reference.Kinds)} reference {reference.Id}"));
            else if (!reference.Kinds.Contains(target.Kind) && !(reference.Kinds.Contains("Entity") && target.Kind == "Assembly")) diagnostics.Add(new(reference.Path, $"Reference resolves to {target.Kind}, expected {string.Join("/", reference.Kinds)}"));
        }
        return diagnostics;
    }
    /// <summary>Reject invalid authoring before export or composition.</summary>
    public static void Require(Records.Model model)
    {
        var errors = Check(model);
        if (errors.Count != 0) throw new ArgumentException(string.Join(Environment.NewLine, errors.Select(e => e.Path + ": " + e.Message)));
    }
}
