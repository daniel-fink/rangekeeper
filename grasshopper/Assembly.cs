using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Objects.Organization;
using Speckle.Core.Models;

namespace Rangekeeper;

public class Assembly : Entity
{
    public Assembly() { }

    [DetachProperty]
    public HashSet<IEntity> entities { get; } = new (new Assembly.BaseComparer());

    public List<string> entityIds => this.entities.Select(entity => entityId).ToList();

    public List<Relationship> relationships { get; } = new();
    
    public Assembly(string name, string type) : base(name, type)
    {
        this.entities.Add(this);
    }

    public Assembly(Assembly assembly, bool clone = false) : base(assembly, clone)
    {
        if (clone)
        {
            foreach (var entity in assembly.entities) this.entities.Add(entity.Copy(true));
            foreach (var relationship in assembly.relationships) this.AddRelationship(relationship.CloneViaSerialization());
        }

        else
        {
            var copiedEntities = new List<IEntity>();
            foreach (var entity in assembly.entities) copiedEntities.Add(entity.Copy(false));
            
            // Create map from old entityId to new entityId:
            var idMap = new Dictionary<string, string>();
            var originalEntities = assembly.entities.ToList();
            
            for (int i = 0; i < assembly.entities.Count; i++) idMap.Add(originalEntities[i].entityId, copiedEntities[i].entityId);
            
            // Update relationships:
            foreach (var relationship in assembly.relationships)
            {
                var source = copiedEntities.Find(entity => entity.entityId == idMap[relationship.sourceId]);
                var target = copiedEntities.Find(entity => entity.entityId == idMap[relationship.targetId]);
                
                this.AddRelationship(new Relationship(source, target, relationship.type));
            }
        }
    }
    // {
    //     if (assembly.TryGetProperty("name", out object? name, out string? remarkName)) this.name = name.ToString();
    //     else this.name = string.Empty;
    //     
    //     if (assembly.TryGetProperty("type", out object? type, out string? remarkType)) this.type = type.ToString();
    //     else this.type = string.Empty;
    //
    //     this.SetEntityId(null);
    //     
    //     foreach (var entity in assembly.entities) this.entities.Add(entity);
    //     foreach (var relationship in assembly.relationships) this.relationships.Add(relationship);
    //
    //     Base instance = (Base)Activator.CreateInstance(assembly.GetType());
    //     this.id = instance.id;
    //     this.applicationId = instance.applicationId;
    //     foreach (KeyValuePair<string, object> member in assembly.GetMembers(DynamicBaseMemberType.Instance | DynamicBaseMemberType.Dynamic | DynamicBaseMemberType.SchemaIgnored))
    //     {
    //         PropertyInfo property = assembly.GetType().GetProperty(member.Key);
    //         if (!(property != (PropertyInfo) null) || property.CanWrite)
    //         {
    //             try { this[member.Key] = member.Value; }
    //             catch { }
    //         }
    //     }
    // }

    public new Assembly Copy(bool clone = false) => new (this, clone);

    public void AddRelationship(Relationship relationship, bool cloneEntities = false)
    {
        if (!this.relationships.Contains(relationship))
        {
            this.relationships.Add(relationship);
            if (cloneEntities)
            {
                this.entities.Add(relationship.source.Copy(true));
                this.entities.Add(relationship.target.Copy(true));
            }
            else
            {
                this.entities.Add(relationship.source.Copy(false));
                this.entities.Add(relationship.target.Copy(false));
            }
        }
    }
}
