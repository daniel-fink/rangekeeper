using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Threading.Tasks;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;
using Speckle.Core.Models;
using Rangekeeper;

namespace Rangekeeper.Components
{
    public class AddRelationships : GH_Component
    {
        public AddRelationships()
            : base(
                "Add Relationships to a Rangekeeper Assembly",
                "AR",
                "Add Relationship(s) to a Rangekeeper Assembly by providing Source and Target Speckle Object(s) to an Assembly, with respective Relationship Type(s) as text.",
                "Rangekeeper",
                "Properties"
            )
        { }

        // protected override Bitmap Icon => Resources.AddRelationshipsIcon;
        
        public override Guid ComponentGuid => new("793E9EBC-251F-4A7D-994F-6022A87FE582");
        
        protected override void RegisterInputParams(GH_InputParamManager pManager)
        {
            pManager.AddGenericParameter(
                "Assembly",
                "A",
                "Rangekeeper Assembly",
                GH_ParamAccess.item);

            pManager.AddGenericParameter(
                "Source Rangekeeper Entities",
                "S",
                "Entities from which a Relationship originates",
                GH_ParamAccess.list);
            
            pManager.AddGenericParameter(
                "Target Rangekeeper Entities",
                "T",
                "Entities to which a Relationship is directed",
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
            pManager.AddParameter(new AssemblyParam("Assembly", "A", "Rangekeeper Assembly", GH_ParamAccess.item));
        }
        
        protected sealed override void SolveInstance(IGH_DataAccess DA)
        {
            GH_Assembly? assemblyGoo = null;
            if (!DA.GetData<GH_Assembly>(0, ref assemblyGoo))
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "No Assembly supplied. Cannot add Relationships.");
                return;
            }
            var assembly = assemblyGoo.Value.Copy(true);
            
            this.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "Here line 73");


            var sources = new List<IGH_Goo>();
            if (!DA.GetDataList(1, sources))
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "No Source Objects supplied. Using Assembly itself as source.");
            }        
            
            var targets = new List<IGH_Goo>();
            if (!DA.GetDataList(2, targets))
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "No Target Objects supplied. Using Assembly itself as target.");
            }
            
            var relationshipTypes = new List<string>();
            if (!DA.GetDataList(3, relationshipTypes))
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, "No Relationship Types supplied.");
                return;
            }
            
            var sourceEntities = new List<IEntity>();
            foreach (var source in sources)
            {
                if (source.CanConvertToEntity(out IEntity? ientity, out string? remark)) sourceEntities.Add(ientity);//.Copy(true));//.Copy(true));//.Duplicate());
                else
                {
                    this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, string.Format("Error: Source Object is not a Rangekeeper Entity: {0}.", remark));
                    return;
                }
            }
            
            var targetEntities = new List<IEntity>();
            foreach (var target in targets)
            {
                if (target.CanConvertToEntity(out IEntity? ientity, out string? remark)) targetEntities.Add(ientity);//.Copy(true));//.Duplicate());
                else
                {
                    this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, string.Format("Error: Target Object is not a Rangekeeper Entity: {0}.", remark));
                    return;
                }
            }
            
            this.AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, "Here line 117");

            
            // if (sourceEntities.Count == 0) sourceEntities.AddRange(Enumerable.Repeat(assembly, targetEntities.Count));
            // if (targetEntities.Count == 0) targetEntities.AddRange(Enumerable.Repeat(assembly, sourceEntities.Count));
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
                assembly.AddRelationship(new Relationship(sourceEntities[i], targetEntities[i], relationshipTypes[i]), true); 
            }
            
            DA.SetData(0, assembly);
        }
    }
}