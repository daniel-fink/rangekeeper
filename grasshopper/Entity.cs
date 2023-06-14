using System;
using System.Collections.Generic;
using System.Dynamic;
using System.Linq;
using System.Reflection;
using Objects.Organization;
using Speckle.Core.Models;

namespace Rangekeeper;

public class Entity : Base, IEntity
{
    public Entity() { }

    public string entityId { get; internal set; }
    
    public string? name { get; set; }

    public string? type { get; set; }

    public Dictionary<string, object?> attributes { get; } = new ();

    public Dictionary<string, double?> measurements { get; } = new();

    public Dictionary<string, object?> events { get; } = new();

    public Entity(string? name, string? type)
    {
        this.name = name ?? string.Empty;
        this.type = type ?? string.Empty;
        this.SetEntityId(null);
    }

    internal void SetEntityId(string? guid)
    {
        if (guid is null) this.entityId = Guid.NewGuid().ToString();
        else this.entityId = guid;
    }

    public Entity(Base speckleBase)
    {
        Base instance = (Base)Activator.CreateInstance(speckleBase.GetType());
        this.id = instance.id;
        this.applicationId = instance.applicationId;
        foreach (KeyValuePair<string, object> member in speckleBase.GetMembers(DynamicBaseMemberType.Instance | DynamicBaseMemberType.Dynamic | DynamicBaseMemberType.SchemaIgnored))
        {
            PropertyInfo property = speckleBase.GetType().GetProperty(member.Key);
            if (!(property != (PropertyInfo) null) || property.CanWrite)
            {
                try { this[member.Key] = member.Value; }
                catch { }
            }
        }
    }

    public Entity(Entity entity, bool clone = false) : this((Base)entity)
    {
        this.name = entity.name;
        this.type = entity.type;
        
        if (clone) this.SetEntityId(entity.entityId);
        else this.SetEntityId(null);

        foreach (KeyValuePair<string, object?> attribute in entity.attributes) this.attributes.Add(attribute.Key, attribute.Value.CloneViaSerialization());
        foreach (KeyValuePair<string, double?> measurement in entity.measurements) this.measurements.Add(measurement.Key, measurement.Value.CloneViaSerialization());
        foreach (KeyValuePair<string, object?> eventKvp in entity.events) this.events.Add(eventKvp.Key, eventKvp.Value.CloneViaSerialization());
    }

    // public Entity(Base speckleBase)
    // {
    //     if (speckleBase.TryGetProperty("name", out object? name, out string? remarkName)) this.name = name.ToString();
    //     else this.name = string.Empty;
    //     
    //     if (speckleBase.TryGetProperty("type", out object? type, out string? remarkType)) this.type = type.ToString();
    //     else this.type = string.Empty;
    //     
    //     // if (speckleBase.TryGetProperty("entityId", out object? entityId, out string? remarkEntityId)) this.entityId = entityId.ToString();
    //     // else this.entityId = Guid.NewGuid().ToString();
    //     this.SetEntityId(null);
    //
    //     Base instance = (Base)Activator.CreateInstance(speckleBase.GetType());
    //     this.id = instance.id;
    //     this.applicationId = instance.applicationId;
    //     foreach (KeyValuePair<string, object> member in speckleBase.GetMembers(DynamicBaseMemberType.Instance | DynamicBaseMemberType.Dynamic | DynamicBaseMemberType.SchemaIgnored))
    //     {
    //         PropertyInfo property = speckleBase.GetType().GetProperty(member.Key);
    //         if (!(property != (PropertyInfo) null) || property.CanWrite)
    //         {
    //             try { this[member.Key] = member.Value; }
    //             catch { }
    //         }
    //     }
    // }

    public IEntity Copy(bool clone = false) => new Entity(this, clone);

    public bool AddAttribute(string key, object? value)
    {
        if (!this.attributes.ContainsKey(key))
        {
            this.attributes.Add(key, value);
            return true;
        }
        else return false;
    }
    
    public bool RemoveAttribute(string key)
    {
        return this.attributes.Remove(key);
    }
    
    public bool AddMeasurement(string key, double? value)
    {
        if (!this.measurements.ContainsKey(key))
        {
            this.measurements.Add(key, value);
            return true;
        }
        else return false;
    }
    
    public bool RemoveMeasurement(string key)
    {
        return this.measurements.Remove(key);
    }    
    
    public bool AddEvent(string key, object? value) => throw new NotImplementedException();
    public bool RemoveEvent(string key) => throw new NotImplementedException();

    /// <summary>
    /// Entities are defined as having unique entityId properties
    /// </summary>
    /// <param name="other"></param>
    /// <returns></returns>
    public bool Equals(IEntity other)
    {
        if (other is null) return false;
        if (this.entityId == other.entityId) return true;
        else return false;
    }
    
    public class BaseComparer : IEqualityComparer<IEntity>
    {
        public bool Equals(IEntity entity, IEntity? other)
        {
            if (other is null) return false;
            if (ReferenceEquals(entity, other)) return true;
            if (entity.Equals(other)) return true;
            else return false;
        }

        public int GetHashCode(IEntity entity)
        {
            return entity.GetHashCode();
        }
    }
}
