using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Objects.Organization;
using Speckle.Core.Models;

namespace Rangekeeper;

public class Assembly : Entity
{
    /// <summary>
    /// The set of relationships that define this Assembly
    /// </summary>
    internal HashSet<Relationship> _relationships { get; } = new();
    public List<Relationship> relationships => new (this._relationships);

    /// <summary>
    /// The set of Entities that this Assembly refers to
    /// </summary>
    internal HashSet<IEntity> _entities => new (this._relationships.SelectMany(relationship => new[] { relationship.source, relationship.target }), new EntityComparer());

    /// <summary>
    /// The set of EntityIds that this Assembly refers to
    /// </summary>
    // internal HashSet<string> _entityIds => new (this._entities.Select(entity => entity.entityId));
    
    public IEntity? GetEntity(string entityId)
    {
        return this._entities.FirstOrDefault(entity => entity.entityId == entityId);
    }

    public List<IEntity>? GetEntities(IEnumerable<string>? entityIds = null) //=> new (this._entities);
    {
        if (entityIds is null) return new(this._entities);
        else return this._entities.Where(entity => entityIds.Contains(entity.entityId)).ToList();
    }

    /// <summary>
    /// Construct an Assembly
    /// </summary>
    /// <param name="name"></param>
    /// <param name="type"></param>
    public Assembly() : base()//name, type)
    { }

    /// <summary>
    /// Construct an Assembly from an Entity, with the option to clone it (ie, retain the EntityId)
    /// </summary>
    /// <param name="entity"></param>
    /// <param name="clone"></param>
    public Assembly(Entity entity, bool clone = false) : base(entity) //, entity.Name, entity.Type)
    {
        if (clone)
        {
            this.SetEntityId(entity.entityId);
        }
    }

    /// <summary>
    /// Construct a new Assembly by copying one.
    /// Note: this does not copy the Relationships, nor Entities of the original Assembly.
    /// </summary>
    /// <param name="assembly"></param>
    public Assembly(Assembly assembly) : base(assembly)//, assembly.Name, assembly.Type)
    {
        this._relationships = new(assembly.relationships);
    }

    public bool AddRelationship(Relationship relationship)
    {
        return this._relationships.Add(relationship);
    }

    /// <summary>
    /// Duplicate an Assembly and all its Entities, with the same EntityIds.
    /// </summary>
    /// <returns></returns>
    public new Assembly Clone()
    {
        var clone = new Assembly(this, true);
        foreach (var relationship in this._relationships) clone.AddRelationship(relationship.Clone());
        return clone;
    }
}
