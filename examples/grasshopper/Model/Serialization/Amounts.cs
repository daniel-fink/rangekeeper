using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Rangekeeper.Serialization;

/// <summary>
/// Currency amounts (ADR-023): canonical decimal text on the wire, System.Decimal here.
/// A magnitude in other units stays a JSON number. This unsupported example rejects
/// an amount that System.Decimal cannot hold exactly.
/// </summary>
public static class Amounts
{
    private static readonly Regex Canonical = new(
        @"^(0|-?(0\.[0-9]*[1-9]|[1-9][0-9]*(\.[0-9]*[1-9])?))$", RegexOptions.CultureInvariant);

    /// <summary>Read a currency amount from its canonical text.</summary>
    public static decimal ToDecimal(JsonNode magnitude)
    {
        if (magnitude is not JsonValue value || !value.TryGetValue<string>(out var text))
            throw new JsonException("A currency amount is decimal text, not a number");
        if (!Canonical.IsMatch(text))
            throw new JsonException($"Currency amount {text} is not canonical text");
        var fraction = text.Contains('.') ? text.Length - text.IndexOf('.') - 1 : 0;
        if (fraction > 28 || !decimal.TryParse(text, NumberStyles.AllowLeadingSign | NumberStyles.AllowDecimalPoint,
                CultureInfo.InvariantCulture, out var result))
            throw new JsonException($"Currency amount {text} does not fit System.Decimal");
        return result;
    }

    /// <summary>Write the canonical text of a currency amount.</summary>
    public static JsonNode ToNode(decimal amount)
    {
        var text = amount.ToString("0.############################", CultureInfo.InvariantCulture);
        return JsonValue.Create(text == "-0" ? "0" : text)!;
    }
}
