using System;

namespace Rangekeeper;

public interface IEntity : IEquatable<IEntity>
{
    public string entityId { get; }
    
    // public string? Name { get; }
    //
    // public string? Type { get; }
    //
    // public Dictionary<string, object?> GetAttributes();
    //
    // public Dictionary<string, double?> GetMeasurements();
    //
    // public Dictionary<string, object?> GetEvents();

    public Entity Clone();
}

