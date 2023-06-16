using System;
using System.Collections.Generic;
using System.Linq;
using Objects.Organization;
using Speckle.Core.Models;

namespace Rangekeeper;

public class Assembly : Base, IEntity
{
    public Assembly() { }

    public string entityId { get; }
    
    public string name { get; }

    public string type { get; }

    // public new string collectionType => "Rangekeeper Assembly";

    [DetachProperty] 
    public HashSet<Base> entities { get; } = new (new Assembly.BaseComparer());

    public List<string> entityIds => this.entities
        .Select(obj => { obj
                .TryGetProperty("entityId", out object entityId);
            return (string)entityId; })
        .ToList();

    public List<Relationship> relationships { get; } = new();
    
    public Assembly(string name, string type)
    {
        this.name = name;
        this.type = type;
        this.entityId = Guid.NewGuid().ToString();
        this.entities.Add(this);
    }

    public void AddRelationship(Relationship relationship)
    {
        if (!this.relationships.Contains(relationship))
        {
            this.relationships.Add(relationship);
            this.entities.Add(relationship.source);
            this.entities.Add(relationship.target);
        }
    }
    
    public class BaseComparer : IEqualityComparer<Base>
    {
        public bool Equals(Base entity, Base? other)
        {
            if (other is null) return false;
            if (ReferenceEquals(entity, other)) return true;
            if (!entity.TryGetProperty("entityId", out object entityId) || !other.TryGetProperty("entityId", out object otherId))
            {
                throw new ArgumentException("Error: Base Object is not an Entity as it does not have an 'entityId' property");
            }
            return (string)entityId == (string)otherId;
        }

        public int GetHashCode(Base entity)
        {
            return entity.GetHashCode();
        }
    }
}
