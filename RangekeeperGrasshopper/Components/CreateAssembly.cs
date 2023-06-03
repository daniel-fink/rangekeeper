using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Threading.Tasks;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;
using Speckle.Core.Models;
using Rangekeeper;
using RangekeeperGrasshopper;

namespace Rangekeeper.Components
{
    public class CreateAssembly : GH_Component
    {
        public CreateAssembly()
            : base(
                "Create Rangekeeper Assembly",
                "CRA",
                "Create a Rangekeeper Assembly by providing Source and Target Speckle Object(s), with respective Relationship Type(s) as text.",
                "Rangekeeper",
                "Rangekeeper"
            )
        { }

        protected override Bitmap Icon => Resources.CreateAssemblyIcon;
        
        public override Guid ComponentGuid => new("7CE1F751-0A1D-40F1-9B9C-17F71EB9394D");
        
        protected override void RegisterInputParams(GH_InputParamManager pManager)
        {
            pManager.AddTextParameter(
                "Assembly Name",
                "N",
                "Name of the Assembly",
                GH_ParamAccess.item);
            
            pManager.AddTextParameter(
                "Type",
                "Ty",
                "Type of Assembly. (It is best to use a standardised vocabulary)",
                GH_ParamAccess.item);
            
            pManager.AddGenericParameter(
                "Source Speckle Objects",
                "S",
                "Speckle Objects from which a Relationship originates. If this is empty, the Assembly itself will be used as source for all Relationships.",
                GH_ParamAccess.list);
            pManager[2].Optional = true;
            
            pManager.AddGenericParameter(
                "Target Speckle Objects",
                "T",
                "Speckle Objects to which a Relationship is directed. If this is empty, the Assembly itself will be used as target for all Relationships.",
                GH_ParamAccess.list);
            pManager[3].Optional = true;
            
            pManager.AddTextParameter(
                "Relationship Types",
                "R",
                "Relationship Types that describe how Source Speckle Objects are related to Target Speckle Objects. " +
                "(It is best to use a standardised vocabulary.)",
                GH_ParamAccess.list);
        }
        
        protected override void RegisterOutputParams(GH_OutputParamManager pManager)
        {
            pManager.AddParameter(new AssemblyParam("Assembly", "A", "Rangekeeper Assembly", GH_ParamAccess.item));
        }
        
        protected sealed override void SolveInstance(IGH_DataAccess DA)
        {
            var name = string.Empty;
            DA.GetData(0, ref name);
            
            var type = string.Empty;
            DA.GetData(1, ref type);

            var sources = new List<IGH_Goo>();
            if (!DA.GetDataList(2, sources))
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "No Source Objects supplied. Using Assembly itself as source.");
            }        
            
            var targets = new List<IGH_Goo>();
            if (!DA.GetDataList(3, targets))
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "No Target Objects supplied. Using Assembly itself as target.");
            }
            
            var relationshipTypes = new List<string>();
            if (!DA.GetDataList(4, relationshipTypes))
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "No Relationship Types supplied.");
                return;
            }
            
            var sourceEntities = new List<Base>();
            foreach (var source in sources)
            {
                if (source.CanConvertToBase(null, out Base? baseObject, out string? remark))
                {
                    if (baseObject.TryGetProperty("entityId", out object entityId)) sourceEntities.Add(baseObject);
                    else 
                    {
                        this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, string.Format("Error: Source Object does not have an entityId property"));
                        return;
                    }
                }
                else 
                {
                    this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, string.Format("Error: Source Object is not a Speckle Object: {0}.", remark));
                    return;
                }
            }

            var targetEntities = new List<Base>();
            foreach (var target in targets)
            {
                if (target.CanConvertToBase(null, out Base? baseObject, out string? remark))
                {
                    if (baseObject.TryGetProperty("entityId", out object entityId)) targetEntities.Add(baseObject);
                    else 
                    {
                        this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, string.Format("Error: Source Object does not have an entityId property: {0}.", remark));
                        return;
                    }
                }
                else 
                {
                    this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, string.Format("Error: Source Object is not a Speckle Object: {0}.", remark));
                    return;
                }
            }
            
            var assembly = new Assembly(name, type);
            if (sourceEntities.Count == 0)
            {
                sourceEntities.AddRange(Enumerable.Repeat((Base)assembly, targetEntities.Count));
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