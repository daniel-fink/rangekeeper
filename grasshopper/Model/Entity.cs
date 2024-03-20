using System;
using System.Collections;
using System.Collections.Generic;
using System.Dynamic;
using System.Linq;
using System.Reflection;
using Objects.Organization;
using Speckle.Core.Models;

namespace Rangekeeper;

public class Entity : Base, IEntity
{
    // public Entity() { }

    public string entityId { get; internal set; }

    public Entity()//string? name, string? type)
    {
        this.SetEntityId();
    }

    internal void SetEntityId(string? guid = null)
    {
        if (guid is null) this.entityId = Guid.NewGuid().ToString();
        else this.entityId = string.Copy(guid);
    }

    public Entity(Base speckleBase) : this()//name, type)
    {
        Base instance = (Base)Activator.CreateInstance(speckleBase.GetType());
        this.id = instance.id;
        this.applicationId = instance.applicationId;
        foreach (KeyValuePair<string, object?> member in speckleBase.GetMembers(DynamicBaseMemberType.Instance | DynamicBaseMemberType.Dynamic | DynamicBaseMemberType.SchemaIgnored))
        {
            if (member.Key == "entityId") continue;
            
            PropertyInfo property = speckleBase.GetType().GetProperty(member.Key);
            if (!(property != (PropertyInfo) null) || property.CanWrite)
            {
                try { this[member.Key] = member.Value; }
                catch { } 
            }
        }
    }

    /// <summary>
    /// Construct a new Entity by copying an Entity instance. Note: the EntityId will be different.
    /// </summary>
    /// <param name="entity"></param>
    public Entity(Entity entity) : this((Base)entity)//, entity.Name, entity.Type)
    { }

    /// <summary>
    /// Duplicates this Entity. Note: its EntityId will be the same as this instance.
    /// </summary>
    /// <returns></returns>
    public Entity Clone()
    {
        var clone = new Entity(this);
        clone.SetEntityId(this.entityId);
        return clone;
    }


    /// <summary>
    /// Entities are defined as having unique EntityId properties
    /// </summary>
    /// <param name="other"></param>
    public bool Equals(IEntity? other)
    {
        if (other is null) return false;
        if (this.entityId == other.entityId) return true;
        else return false;
    }
    
    public class EntityComparer : IEqualityComparer<IEntity>
    {
        public bool Equals(IEntity entity, IEntity? other)
        {
            if (other is null) return false;
            else return entity.Equals(other);
        }
    
        public int GetHashCode(IEntity entity)
        {
            return entity.entityId.GetHashCode();
        }
    }
}
