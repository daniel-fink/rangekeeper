using System;
using Speckle.Core.Models;

namespace Rangekeeper;

public class Relationship : Base, IEquatable<Relationship>
{
    public Relationship() { }

    [DetachProperty]
    public IEntity source { get; }

    // public string sourceId => this.source.entityId;

    [DetachProperty]
    public IEntity target { get; }

    // public string targetId => this.target.entityId;

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

    /// <summary>
    /// Clones a Relationship, including cloning the source and target Entities.
    /// </summary>
    /// <returns></returns>
    public Relationship Clone()
    {
        return new Relationship(this.source.Clone(), this.target.Clone(), this.type);
    }

    public bool Equals(Relationship? other)
    {
        if (other is null) return false;
        if (ReferenceEquals(this, other)) return true;
        return Equals(this.source.entityId, other.source.entityId) && Equals(this.target.entityId, other.target.entityId) && (this.type == other.type);
    }
}