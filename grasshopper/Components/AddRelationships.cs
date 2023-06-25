using System;
using System.Collections.Generic;
using System.Linq;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;
using Speckle.Core.Models;

namespace Rangekeeper.Components
{
    public class AddRelationships : GH_Component
    {
        public AddRelationships()
            : base(
                "Add Relationships",
                "ARkR",
                "Add Relationships to an Entity (or existing Assembly)",
                "Rangekeeper",
                "Rangekeeper"
            )
        { }

        // protected override Bitmap Icon => Resources.CreateAssemblyIcon;
        
        public override Guid ComponentGuid => new("F7297015-6047-4003-B205-D4918FE0A63A");
        
        protected override void RegisterInputParams(GH_InputParamManager pManager)
        {
            pManager.AddGenericParameter(
                "Entity",
                "E",
                "The Speckle Object, Entity, or Assembly for containing and relating other Entities",
                GH_ParamAccess.item);
            
            pManager.AddGenericParameter(
                "Source Entities",
                "S",
                "Speckle Objects from which a Relationship originates",
                GH_ParamAccess.list);
            
            pManager.AddGenericParameter(
                "Target Entities",
                "T",
                "Speckle Objects to which a Relationship is directed",
                GH_ParamAccess.list);
            
            pManager.AddTextParameter(
                "Relationship Types",
                "R",
                "Relationship Types that describe how Source Entities are related to Target Entities. " +
                "(It is recommended to use a standardised vocabulary.) " +
                "Note: If only one Relationship Type is provided, it will be used for all Relationships.",
                GH_ParamAccess.list);
        }
        
        protected override void RegisterOutputParams(GH_OutputParamManager pManager)
        {
            pManager.AddParameter(new AssemblyParam("Assembly", "A", "Model Assembly", GH_ParamAccess.item));
        }
        
        protected sealed override void SolveInstance(IGH_DataAccess DA)
        {
            IGH_Goo? speckleGoo = null;
            Base? entityBase = null;
            if (DA.GetData(0, ref speckleGoo))
            {
                if (speckleGoo is not null)
                    if (!speckleGoo.CanConvertToBase(out entityBase, out string? remark))
                    {
                        this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, remark);
                        return;
                    }
            }
            else
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, string.Format("Error: Input Object was not provided."));
                return;
            }

            Assembly assembly;
            if (entityBase is not IEntity) assembly = new Assembly(new Entity(entityBase));
            else if (entityBase is Assembly assemblyBase) assembly = assemblyBase.Clone();
            else if (entityBase is Entity entity) assembly = new Assembly(entity, true);
            else
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, string.Format("Error: Input Object could not be converted to an Assembly."));
                return;
            }
            
            var sourceGoos = new List<IGH_Goo>();
            var sourceEntities = new List<IEntity>();
            if (DA.GetDataList(1, sourceGoos))
            {
                foreach (var goo in sourceGoos)
                {
                    IEntity ientity;
                    if (goo.CanConvertToBase(out Base? sourceBase, out string? remark))
                    {
                        if (sourceBase.Equals(entityBase) | ReferenceEquals(sourceBase, entityBase)) ientity = assembly;
                        else if (sourceBase is not IEntity) ientity = new Entity(sourceBase);
                        else ientity = (IEntity)sourceBase;
                    }
                    else
                    {
                        this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, remark);
                        return;
                    }
                    sourceEntities.Add(ientity);
                }
            }
            else
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, string.Format("Error: Source Objects were not provided."));
                return;
            }
            
            var targetGoos = new List<IGH_Goo>();
            var targetEntities = new List<IEntity>();
            if (DA.GetDataList(2, targetGoos))
            {
                foreach (var goo in targetGoos)
                {
                    IEntity ientity;
                    if (goo.CanConvertToBase(out Base? targetBase, out string? remark))
                    {
                        if (targetBase.Equals(entityBase) | ReferenceEquals(targetBase, entityBase)) ientity = assembly;
                        else if (targetBase is not IEntity) ientity = new Entity(targetBase);
                        else ientity = (IEntity)targetBase;
                    }
                    else
                    {
                        this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, remark);
                        return;
                    }
                    targetEntities.Add(ientity);
                }
            }
            else
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, string.Format("Error: Target Objects were not provided."));
                return;
            }
            
            var relationshipTypes = new List<string>();
            if (!DA.GetDataList(3, relationshipTypes))
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "No Relationship Types supplied.");
                return;
            }
            
            if (relationshipTypes.Count == 1)
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "Note: One (1) Relationship Type supplied. Using this for all Relationships.");
                relationshipTypes = Enumerable.Repeat(relationshipTypes[0], sourceEntities.Count).ToList();
            }
            
            if (!(sourceEntities.Count == targetEntities.Count && targetEntities.Count == relationshipTypes.Count))
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Error: Number of Sources, Targets and Relationships must match.");
                return;
            }
            
            for (int i = 0; i < relationshipTypes.Count; i++)
            {
                assembly.AddRelationship(new Relationship(sourceEntities[i], targetEntities[i], relationshipTypes[i])); 
            }

            DA.SetData(0, assembly);
        }
    }
}