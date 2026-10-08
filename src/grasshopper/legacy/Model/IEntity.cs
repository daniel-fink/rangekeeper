using System;

namespace Rangekeeper;

public interface IEntity : IEquatable<IEntity>
{
    public string entityId { get; }

    public Entity Clone();
}

