using System;
using Speckle.Core.Models;

namespace Rangekeeper;

public class Relationship : Base, IEquatable<Relationship>
{
    public Relationship() { }

    [DetachProperty]
    internal IEntity source { get; }

    public string sourceId => source.entityId;

    [DetachProperty]
    internal IEntity target { get; }

    public string targetId => target.entityId;

    public string type { get; set; }
    
    /// <summary>
    /// Create a new Relationship of a specific type, that relates a source Element's Id to a target Element's Id
    /// Note: this is dissociated from any Assembly.
    /// </summary>
    public Relationship(IEntity source, IEntity target, string type)
    {
        if (source is null || target is null || string.IsNullOrEmpty(type)) throw new ArgumentNullException();
        this.source = source;
        this.target = target;
        this.type = type;
    }
    
    public bool Equals(Relationship other)
    {
        if (other is null) return false;
        if (ReferenceEquals(this, other)) return true;
        return Equals(this.sourceId, other.sourceId) && Equals(this.targetId, other.targetId) && (this.type == other.type);
    }
}