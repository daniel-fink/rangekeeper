using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization;
using System.Numerics;

namespace Rangekeeper.Serialization;

/// <summary>Own a detached wire snapshot. Construction performs no IO or solving.</summary>
public abstract class WireRecord
{
    private readonly JsonObject data;
    protected WireRecord() { data = new(); }
    protected WireRecord(JsonObject source) { data = (JsonObject)source.DeepClone(); }
    public JsonObject ToData() => (JsonObject)data.DeepClone();
    protected T Read<T>(string key) => data[key] is JsonNode node
        ? node.Deserialize<T>(Codec.Options)! : throw new InvalidOperationException($"Required field {key} is absent/null");
    protected Optional<T> ReadOptional<T>(string key) => !data.ContainsKey(key) ? Optional<T>.Missing
        : data[key] is null ? Optional<T>.Null : Optional<T>.From(Read<T>(key));
    protected void Write<T>(string key, T value) => data[key] = JsonSerializer.SerializeToNode(value, Codec.Options);
    protected void WriteOptional<T>(string key, Optional<T> value)
    {
        if (!value.IsPresent) data.Remove(key);
        else if (value.IsNull) data[key] = null;
        else Write(key, value.Value);
    }
}

internal sealed class RecordConverterFactory : JsonConverterFactory
{
    public override bool CanConvert(Type type) => typeof(WireRecord).IsAssignableFrom(type);
    public override JsonConverter CreateConverter(Type type, JsonSerializerOptions options) =>
        (JsonConverter)Activator.CreateInstance(typeof(RecordConverter<>).MakeGenericType(type))!;
    private sealed class RecordConverter<T> : JsonConverter<T> where T : WireRecord
    {
        public override T Read(ref Utf8JsonReader reader, Type type, JsonSerializerOptions options) =>
            (T)Activator.CreateInstance(type, JsonNode.Parse(ref reader)!.AsObject())!;
        public override void Write(Utf8JsonWriter writer, T value, JsonSerializerOptions options) => value.ToData().WriteTo(writer, options);
    }
}

internal sealed class IntegerConverter : JsonConverter<BigInteger>
{
    public override BigInteger Read(ref Utf8JsonReader reader, Type type, JsonSerializerOptions options) => BigInteger.Parse(JsonDocument.ParseValue(ref reader).RootElement.GetRawText(), System.Globalization.CultureInfo.InvariantCulture);
    public override void Write(Utf8JsonWriter writer, BigInteger value, JsonSerializerOptions options) => writer.WriteRawValue(value.ToString(System.Globalization.CultureInfo.InvariantCulture));
}
