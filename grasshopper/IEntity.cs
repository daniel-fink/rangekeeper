using System;

namespace Rangekeeper;

public interface IEntity : IEquatable<IEntity>
{
    public string entityId { get; }
    
    public string? name { get; }
    
    public string? type { get; }

    public IEntity Copy(bool clone);

    public bool AddAttribute(string key, object? value);

    public bool RemoveAttribute(string key);

    public bool AddMeasurement(string key, double? value);

    public bool RemoveMeasurement(string key);
    
    public bool AddEvent(string key, object? value);

    public bool RemoveEvent(string key);
}