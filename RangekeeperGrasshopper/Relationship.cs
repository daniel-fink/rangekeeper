using System;
using Rhino.Commands;
using Speckle.Core.Models;

namespace Rangekeeper;

public class Relationship : Base, IEquatable<Relationship>
{
    public Relationship() { }

    [DetachProperty]
    internal Base source { get; }

    public string sourceId
    {
        get
        {
            if (source.TryGetProperty("entityId", out object entityId)) return (string)entityId;
            else return null;
        }
    }

    [DetachProperty]
    internal Base target { get; }
    
    public string targetId     
    {
        get
        {
            if (target.TryGetProperty("entityId", out object entityId)) return (string)entityId;
            else return null;
        }
    }
    
    public string relationshipType { get; set; }
    
    /// <summary>
    /// Create a new Relationship of a specific type, that relates a source Element's Id to a target Element's Id
    /// Note: this is dissociated from any Assembly.
    /// </summary>
    public Relationship(Base source, Base target, string relationshipType)
    {
        if (!source.TryGetProperty("entityId", out object sourceEntityId) || !target.TryGetProperty("entityId", out object targetEntityId))
        {
            throw new ArgumentException("Error: Base Object is not an Entity as it does not have an 'entityId' property");
        }
        this.source = source;
        this.target = target;
        this.relationshipType = relationshipType;
    }
    
    public bool Equals(Relationship other)
    {
        if (other is null) return false;
        if (ReferenceEquals(this, other)) return true;
        return Equals(this.sourceId, other.sourceId) && Equals(this.targetId, other.targetId) && (relationshipType == other.relationshipType);
    }
}