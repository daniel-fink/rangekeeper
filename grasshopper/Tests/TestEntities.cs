using Xunit.Abstractions;
using Speckle.Core.Models;
using Rangekeeper;


namespace Tests;

public class TestEntities
{
    private readonly ITestOutputHelper output;
    public TestEntities(ITestOutputHelper testOutputHelper) { output = testOutputHelper; }

    [Fact]
    public void SetId()
    {
        var entityA = new Entity();
        entityA["name"] = "entityA";
        entityA["type"] = "typeA";
        entityA["foo"] = "bar";

        var entityB = new Entity() { ["name"] = "entityB" };
        entityB["type"] = "typeA";
        var entityC = new Entity(entityA);
        var entityD = entityA.Clone();
        var entityE = entityA.ShallowCopy();
        
        Assert.False(entityA.Equals(entityB));
        Assert.False(entityA.Equals(entityC));
        Assert.True(entityA.Equals(entityD));
        Assert.False(ReferenceEquals(entityA, entityD));
        Assert.False(entityA.Equals(entityE));
    }

     [Fact]
     public void TestProperties()
     {
         var entity = new Entity()
         {
             ["name"] = "entityA",
             ["type"] = "typeA"
         };
         entity["foo"] = "bar";
         entity["quux"] = 42;
         entity["pi"] = Double.Pi;

         var attribMember = entity.GetMembers(DynamicBaseMemberType.All).FirstOrDefault(member => member.Key == "foo").Value;
         Assert.Equal("bar", entity["foo"]);
         Assert.Equal(3, Math.Floor(Convert.ToDouble(entity["pi"])));
     }
     
     [Fact]
     public void TestAssemblies()
     {
         var entityA = new Entity()
         {
             ["name"] = "entityA",
             ["type"] = "typeA"
         };     
         entityA["foo"] = "bar";
         
         var entityB = new Entity()
         {
             ["name"] = "entityB",
             ["type"] = "typeA"
         };
         
         var entityC = new Entity(entityA);
         var entityD = entityA.Clone();
         var entityE = entityA.ShallowCopy();
         
         var assemblyA = new Assembly();
         assemblyA.AddRelationship(new Relationship(entityA, entityB, "relationshipTypeA"));
         assemblyA.AddRelationship(new Relationship(entityB, entityC, "relationshipTypeB"));
         assemblyA.AddRelationship(new Relationship(entityA, entityC, "relationshipTypeB"));
         assemblyA.AddRelationship(new Relationship(entityD, entityA, "relationshipTypeA"));
         
         Assert.True(entityA.Equals(entityD));

         output.WriteLine(assemblyA.SerializeToJson());
         output.WriteLine(assemblyA.GetEntities().SerializeToJson());
         
         Assert.Equal(entityA, assemblyA.GetEntity(entityA.entityId));
         Assert.Equal(3, assemblyA.GetEntities().Count);
         Assert.Equal(4, assemblyA.relationships.Count);
         
         var assemblyB = new Assembly(assemblyA);
         Assert.False(assemblyA.Equals(assemblyB));

         var assemblyC = (Assembly)assemblyA.Clone();
         var assemblyZ = new Assembly(assemblyA, true);

         Assert.True(assemblyA.Equals(assemblyC));
         Assert.True(assemblyA.Equals(assemblyZ));
         Assert.False(ReferenceEquals(assemblyA, assemblyC));
         Assert.False(ReferenceEquals(assemblyA, assemblyZ));
         
         Assert.True(assemblyA.GetEntity(entityA.entityId).Equals(assemblyC.GetEntity(entityA.entityId)));
         Assert.False(
             ReferenceEquals(assemblyA.GetEntity(entityA.entityId),
             assemblyC.GetEntity(entityA.entityId)));
         
         Assert.Equal(
             ((Entity)assemblyA.GetEntity(entityA.entityId))["foo"],
             ((Entity)assemblyC.GetEntity(entityA.entityId))["foo"]);
     }
}