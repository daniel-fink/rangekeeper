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
                "Create a Rangekeeper Entity by providing a Speckle Object",
                "Rangekeeper",
                "Rangekeeper"
            )
        { }

        protected override Bitmap Icon => Resources.CreateEntityIcon;
        
        public override Guid ComponentGuid => new("5B115630-2F5A-4E82-BEB2-1E86768B1893");
        
        protected override void RegisterInputParams(GH_InputParamManager pManager)
        {
            pManager.AddGenericParameter(
                "Speckle Object",
                "O",
                "Underlying Speckle Object of the Entity.",
                GH_ParamAccess.item);
        }
        
        protected override void RegisterOutputParams(GH_OutputParamManager pManager)
        {
            pManager.AddParameter(new EntityParam("Entity", "E", "Model Entity", GH_ParamAccess.item));
        }
        
        protected sealed override void SolveInstance(IGH_DataAccess DA)
        {
            IGH_Goo? speckleGoo = null;
            Base? speckleBase = null;
            if (DA.GetData(0, ref speckleGoo))
            {
             if (speckleGoo is not null)
                 if (!speckleGoo.CanConvertToBase(out speckleBase, out string? remark))
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

            var entity = new Entity(speckleBase);

            DA.SetData(0, entity);
        }
    }
}