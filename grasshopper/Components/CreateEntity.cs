using System;
using System.Drawing;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Types;
using Speckle.Core.Models;

namespace Rangekeeper.Components
{
    public class CreateEntity : GH_Component
    {
        public CreateEntity()
            : base(
                "Create Rangekeeper Entity",
                "CRkE",
                "Create a Rangekeeper Entity by providing a Speckle Object, and optional additional properties",
                "Rangekeeper",
                "Entities"
            )
        { }

        // protected override Bitmap Icon => Resources.CreateEntityIcon;
        
        public override Guid ComponentGuid => new("5B115630-2F5A-4E82-BEB2-1E86768B1893");
        
        protected override void RegisterInputParams(GH_InputParamManager pManager)
        {
            pManager.AddTextParameter(
                "Entity Name",
                "N",
                "Name of the Entity",
                GH_ParamAccess.item);
            pManager[0].Optional = true;
            
            pManager.AddTextParameter(
                "Type",
                "Ty",
                "Type of Entity. (It is best to use a standardised vocabulary)",
                GH_ParamAccess.item);
            pManager[1].Optional = true;
            
            pManager.AddGenericParameter(
                "Speckle Object",
                "O",
                "Underlying Speckle Object of the Entity.",
                GH_ParamAccess.item);
        }
        
        protected override void RegisterOutputParams(GH_OutputParamManager pManager)
        {
            pManager.AddParameter(new EntityParam("Entity", "E", "Rangekeeper Entity", GH_ParamAccess.item));
        }
        
        protected sealed override void SolveInstance(IGH_DataAccess DA)
        {
            var name = string.Empty;
            DA.GetData(0, ref name);
            
            var type = string.Empty;
            DA.GetData(1, ref type);

            IGH_Goo? speckleGoo = null;
            DA.GetData(2, ref speckleGoo);
            if (!speckleGoo.CanConvertToBase(out Base? speckleBase, out string? remark))
            {
                this.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, string.Format("Error: Input Object is not a Speckle Object: {0}.", remark));
                return;
            }

            var entity = new Entity(speckleBase);
            entity.name = name;
            entity.type = type;

            DA.SetData(0, entity);
        }
    }
}