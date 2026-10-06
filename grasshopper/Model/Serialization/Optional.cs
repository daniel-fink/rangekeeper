namespace Rangekeeper.Serialization;

/// <summary>A wire field's three states: omitted, explicit null, or a value.</summary>
public readonly struct Optional<T>
{
    private readonly T? value;
    public bool IsPresent { get; }
    public bool IsNull { get; }
    public T Value => IsPresent && !IsNull ? value! : throw new InvalidOperationException("Field has no value");
    private Optional(bool present, bool isNull, T? item) { IsPresent=present; IsNull=isNull; value=item; }
    public static Optional<T> Missing => default;
    public static Optional<T> Null => new(true, true, default);
    public static Optional<T> From(T value) => value is null ? Null : new(true, false, value);
    public static implicit operator Optional<T>(T value) => From(value);
}
