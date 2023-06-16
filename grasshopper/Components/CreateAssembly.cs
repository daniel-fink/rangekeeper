using System;
using System.Collections.Generic;
using System.Linq;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;
using Speckle.Core.Models;

namespace Rangekeeper.Components
{
    public class CreateAssembly : GH_Component
    {
        public CreateAssembly()
            : base(
                "Create Rangekeeper Assembly",
                "CRkA",
                "Create a Rangekeeper Assembly (an Entity that contains and relates other Entities)",
                "Rangekeeper",
                "Entities"
            )
        { }

        // protected override Bitmap Icon => Resources.CreateAssemblyIcon;
        
        public override Guid ComponentGuid => new("F7297015-6047-4003-B205-D4918FE0A63A");
        
        protected override void RegisterInputParams(GH_InputParamManager pManager)
        {
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
            var assembly = new Assembly();

            var sourceGoos = new List<IGH_Goo>();
            var sourceEntities = new List<IEntity>();
            if (DA.GetDataList(0, sourceGoos))
            {
                foreach (var goo in sourceGoos)
                {
                    IEntity ientity;
                    if (goo.CanConvertToBase(out Base? speckleBase, out string? remark))
                    {
                        if (speckleBase is not IEntity) ientity = new Entity(speckleBase);
                        else ientity = (IEntity)speckleBase;
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
            if (DA.GetDataList(1, targetGoos))
            {
                foreach (var goo in targetGoos)
                {
                    IEntity ientity;
                    if (goo.CanConvertToBase(out Base? speckleBase, out string? remark))
                    {
                        if (speckleBase is not IEntity) ientity = new Entity(speckleBase);
                        else ientity = (IEntity)speckleBase;
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
            if (!DA.GetDataList(2, relationshipTypes))
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