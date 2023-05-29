using System;
using System.Collections.Generic;
using System.Drawing;
using System.Threading.Tasks;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;
using Speckle.Core.Models;
using Rangekeeper;

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

        // protected override Bitmap Icon => Resources.CreateRangekeeperAssembly;
        
        public override Guid ComponentGuid => new("7CE1F751-0A1D-40F1-9B9C-17F71EB9394D");
        
        protected override void RegisterInputParams(GH_InputParamManager pManager)
        {
            pManager.AddTextParameter(
                "Assembly Name",
                "N",
                "Name of the Assembly",
                GH_ParamAccess.item
            );
            pManager.AddTextParameter(
                "Assembly Type",
                "Ty",
                "Type of Assembly. (It is best to use a standardised vocabulary)",
                GH_ParamAccess.item);
            pManager.AddGenericParameter(
                "Source Speckle Objects",
                "S",
                "Speckle Objects from which a Relationship originates.",
                GH_ParamAccess.list
            );
            pManager.AddGenericParameter(
                "Target Speckle Objects",
                "T",
                "Speckle Objects to which a Relationship is directed.",
                GH_ParamAccess.list
            );
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
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "No Source Objects supplied.");
                return;
            }        
            
            var targets = new List<IGH_Goo>();
            if (!DA.GetDataList(3, targets))
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "No Target Objects supplied.");
                return;
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

            if (!(sourceEntities.Count == targetEntities.Count && targetEntities.Count == relationshipTypes.Count))
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Error: Number of Sources, Targets and Relationships must match.");
                return;
            }

            var assembly = new Assembly(name, type);
            for (int i = 0; i < relationshipTypes.Count; i++)
            {
                assembly.AddRelationship(new Relationship(sourceEntities[i], targetEntities[i], relationshipTypes[i])); 
            }
            
            DA.SetData(0, assembly);
        }
    }
}